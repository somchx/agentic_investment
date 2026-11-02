"""Tool layer: wraps the domain logic built so far (reason_engine,
earnings_release, xbrl_extract) as discrete, independently-callable tools
with explicit name/description/input schemas -- the "Financial Data API",
"Calculator", "Rule Engine" etc. rows from PROPOSAL.md section 5.

This is the seam between the deterministic pipeline and an LLM-driven
agent: agent.py's rule-based planner calls these functions directly, and
the same TOOL_SPECS list is shaped for the Anthropic Messages API's
tool-use format, so the real LLM agent (agent.run_with_llm) calls the exact
same functions.

Every tool returns a plain JSON-serializable dict -- deliberately not the
richer Fact/Evaluation dataclasses used internally -- because that's what
actually crosses a tool-call boundary to an LLM (or to a caller that only
has the tool's declared schema to go on).
"""

from earnings_release import get_release_figure, list_earnings_release_filings
from filing_context import get_filing_narrative, latest_10q_accession
from models import Reason
from reason_engine import _latest_quarter_on_or_before, evaluate_margin_level, evaluate_yoy_growth
from sec_client import get_company_facts
from xbrl_extract import (
    extract_instant_facts,
    extract_instant_facts_for_tag,
    extract_quarterly_facts,
    extract_quarterly_facts_for_tag,
    facts_as_of,
    latest_version_per_quarter,
)

REASON_DEFS = {
    "revenue_growth": Reason(
        "R1", "", "Revenue", ">", 0.10, kind="yoy_growth",
        description="Revenue growth must exceed 10% YoY",
    ),
    "operating_margin": Reason(
        "R2", "", "OperatingIncome", ">=", 0.20, kind="margin_level",
        denominator_metric="Revenue",
        description="Operating margin must stay at or above 20%",
    ),
    "debt_growth": Reason(
        "R3", "", "LongTermDebt", "<", 0.15, kind="yoy_growth", instant=True,
        description="Long-term debt must not grow more than 15% YoY",
    ),
}


def _evaluation_to_dict(ev) -> dict:
    return {
        "status": ev.status,
        "computed_value": ev.computed_value,
        "derivations": [f.derivation for f in ev.supporting_evidence if f.derivation],
        # Period the number describes (current quarter; numerator's for a
        # margin) -- what corroborating evidence must match (Evidence Gate).
        "evaluated_period": ev.supporting_evidence[0].period_end if ev.supporting_evidence else None,
        "explanation": ev.explanation,
        "supporting_evidence": [f.label() for f in ev.supporting_evidence],
        "conflicting_evidence": [f.label() for f in ev.conflicting_evidence],
    }


def get_reason_def(reason_key: str, ticker: str | None = None) -> Reason | None:
    """Look up a Reason by key -- built-in first (REASON_DEFS, applies to
    every ticker), then a custom DB-backed one (see db.save_reason).
    Returns None if found in neither place.

    `reason_key` is globally unique (the DB's primary key), so once it's
    known no user/ticker scoping is needed to evaluate it -- scoping
    matters for *listing* (a user should only see their own custom
    reasons) and *deleting* (only the owner can), both enforced at the
    db.py/webapp.py layer, not here. `ticker` is accepted for backward
    compatibility but no longer required to find a custom reason.

    Kept as a thin lookup separate from _evaluate_reason so callers that
    just need the Reason's metadata (e.g. a UI listing) don't have to fetch
    SEC facts to get it.
    """
    if reason_key in REASON_DEFS:
        return REASON_DEFS[reason_key]
    import db
    row = db.get_reason_by_key(reason_key)
    if row and not row["is_builtin"]:
        return Reason(
            reason_id=row["reason_key"], company="", metric=row["metric"],
            comparison=row["comparison"], threshold=row["threshold"],
            kind=row["kind"], denominator_metric=row["denominator_metric"] or "",
            description=row["description"], instant=bool(row["instant"]),
            is_custom=row.get("is_custom", True),
        )
    return None


def _evaluate_reason(ticker: str, reason_key: str, as_of: str | None):
    """Shared fetch-facts-and-evaluate step behind both check_reason_status
    (Rule Engine: arithmetic + threshold judgment) and calculate_metric
    (Metric Calculator: arithmetic alone). Factored out so the two tools
    can't drift apart on how the number itself is computed -- both call the
    exact same reason_engine functions, they just report different slices
    of the same Evaluation.

    Returns (company_name, reason, as_of, Evaluation) on success, or a dict
    with an "error" key on failure (unknown reason_key / no facts found).
    """
    reason = get_reason_def(reason_key, ticker)
    if reason is None:
        return {"error_code": "INVALID_REASON_KEY", "error": f"unknown reason_key '{reason_key}' for ticker '{ticker}'"}
    return _evaluate_reason_obj(ticker, reason, as_of)


def _evaluate_reason_obj(ticker: str, reason: Reason, as_of: str | None):
    """Same fetch-facts-and-evaluate step as _evaluate_reason, but given an
    already-resolved Reason object instead of looking one up by key. This
    is what lets evaluate_frozen_reason (below) evaluate a *frozen* rule
    definition -- e.g. one captured in a Purchase snapshot -- without ever
    touching the live `reasons` table, so editing or deleting that reason
    later can't silently change what a past purchase is tracked against
    (Code Audit Session 3, item 2)."""
    loaded = load_reason_facts(ticker, reason)
    if isinstance(loaded, dict):  # error case
        return loaded
    company_name, facts, denom_facts = loaded

    if as_of is None:
        as_of = max(f.filed for f in facts)

    if reason.kind == "margin_level":
        ev = evaluate_margin_level(reason, facts, denom_facts, as_of)
    else:
        ev = evaluate_yoy_growth(reason, facts, as_of)

    return company_name, reason, as_of, ev


def load_reason_facts(ticker: str, reason: Reason):
    """All filed facts a reason is computed from (numerator, and denominator
    for a margin), unfiltered by date -- callers apply the point-in-time
    cutoff per evaluation date. Returns (company_name, facts, denom_facts),
    or an error dict when the metric has no facts for this company."""
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)

    # Custom reasons reference one exact raw XBRL tag (picked from a real
    # per-company tag list, see xbrl_extract.list_available_tags) rather
    # than a curated METRIC_TAGS entry -- built-in reasons keep using the
    # curated multi-tag lookup (handles tag migration over time, e.g.
    # Apple's SalesRevenueNet -> RevenueFromContractWithCustomer...).
    quarterly_fn = extract_quarterly_facts_for_tag if reason.is_custom else extract_quarterly_facts
    instant_fn = extract_instant_facts_for_tag if reason.is_custom else extract_instant_facts

    if reason.instant:
        facts = instant_fn(facts_json, cik, reason.metric)
        denom_facts = (
            instant_fn(facts_json, cik, reason.denominator_metric)
            if reason.kind == "margin_level" else None
        )
    else:
        facts = quarterly_fn(facts_json, cik, reason.metric)
        denom_facts = (
            quarterly_fn(facts_json, cik, reason.denominator_metric)
            if reason.kind == "margin_level" else None
        )

    if not facts:
        return {"error_code": "EVIDENCE_NOT_FOUND", "error": f"no {reason.metric} facts found for {ticker}"}
    return company_name, facts, denom_facts


def check_reason_status(ticker: str, reason_key: str, as_of: str | None = None) -> dict:
    """Tool: evaluate one numeric investment reason for a company as of a date
    (defaults to the most recent filing available). This is the "Calculator /
    Rule Engine" step -- it does the growth/margin arithmetic and applies the
    reason's threshold.
    """
    result = _evaluate_reason(ticker, reason_key, as_of)
    if isinstance(result, dict):  # error case
        return result
    company_name, reason, as_of, ev = result

    return {
        "ticker": ticker,
        "company": company_name,
        "reason": reason.description,
        "as_of": as_of,
        **_evaluation_to_dict(ev),
    }


def reason_from_frozen_def(frozen_def: dict) -> Reason:
    """Build the Reason a frozen purchase snapshot (or a raw `reasons` row)
    describes -- see evaluate_frozen_reason for why both shapes occur."""
    if "is_custom" in frozen_def:
        is_custom = bool(frozen_def["is_custom"])
    elif "is_builtin" in frozen_def:
        is_custom = not frozen_def["is_builtin"]
    else:
        is_custom = False
    return Reason(
        reason_id=frozen_def.get("reason_key", ""), company="", metric=frozen_def["metric"],
        comparison=frozen_def["comparison"], threshold=frozen_def["threshold"],
        kind=frozen_def["kind"], denominator_metric=frozen_def.get("denominator_metric") or "",
        description=frozen_def.get("description", ""), instant=bool(frozen_def.get("instant", False)),
        is_custom=is_custom,
    )


def evaluate_frozen_reason(ticker: str, frozen_def: dict, as_of: str | None = None) -> dict:
    """Evaluate a reason from an explicit, frozen rule definition (metric,
    comparison, threshold, kind, denominator_metric, instant) instead of a
    live reason_key lookup. Same return shape as check_reason_status.

    This is what portfolio tracking (api/portfolio.py) and Continuous
    Monitoring (monitor.py) must call for a purchase that has a reason
    snapshot -- if the live `reasons` row for that reason_key is later
    edited (different threshold) or deleted, check_reason_status(ticker,
    reason_key) would silently start evaluating a different rule than the
    one that actually justified the purchase. Confirmed as a real gap in
    an external code audit (Session 3, item 2) and reproduced: buy under
    "margin >= 20%", edit the rule to "margin >= 25%", and the old
    tracking silently re-graded the historical purchase against 25%.

    Whether `metric` is a built-in curated name (e.g. "Revenue", resolved
    via METRIC_TAGS' multi-tag migration list) or one exact raw XBRL tag a
    user picked for a custom reason must be known to pick the right
    extraction path. Hardcoding `is_custom=True` here (the bug this
    docstring note replaces) silently broke every frozen snapshot of a
    BUILT-IN reason -- the curated name was looked up as if it were a
    literal tag, found nothing, and both purchase recording and portfolio
    tracking failed outright for the 3 built-in reasons. Reproduced live:
    `POST /api/positions` with reason_key="revenue_growth" returned 400
    "no Revenue facts found" for a real, data-backed ticker.

    Two call shapes both have to work here: a raw `reasons` DB row (used
    when first computing the snapshot at purchase time, carrying
    `is_builtin`) and the frozen snapshot dict itself on every later
    re-evaluation (positions.py now stores `is_custom` directly in it) --
    so both keys are checked rather than assuming one caller's shape.
    """
    reason = reason_from_frozen_def(frozen_def)
    result = _evaluate_reason_obj(ticker, reason, as_of)
    if isinstance(result, dict):  # error case
        return result
    company_name, reason, as_of, ev = result

    return {
        "ticker": ticker,
        "company": company_name,
        "reason": reason.description,
        "as_of": as_of,
        **_evaluation_to_dict(ev),
    }


def calculate_metric(ticker: str, reason_key: str, as_of: str | None = None) -> dict:
    """Tool: the arithmetic step alone (growth rate or margin), with no
    threshold judgment attached -- the Metric Calculator as its own
    independently-callable tool, separate from the Rule Engine's
    Supported/Weakened/Broken classification (check_reason_status).

    Same underlying computation as check_reason_status (via
    _evaluate_reason, not a re-implementation) -- this exists for an agent
    that wants "what's the number" without also getting a verdict on it,
    e.g. to sanity-check a figure before deciding how to interpret it.
    """
    result = _evaluate_reason(ticker, reason_key, as_of)
    if isinstance(result, dict):  # error case
        return result
    company_name, reason, as_of, ev = result

    return {
        "ticker": ticker,
        "company": company_name,
        "metric": reason.metric,
        "kind": reason.kind,
        "as_of": as_of,
        "computed_value": ev.computed_value,
        "explanation": ev.explanation,
        "supporting_evidence": [f.label() for f in ev.supporting_evidence],
    }


SECONDARY_EVIDENCE_METRICS = {
    "revenue_growth": "Revenue",
    "operating_margin": "OperatingIncome",
    "debt_growth": "LongTermDebt",
}


def get_secondary_evidence(ticker: str, reason_key: str, as_of: str | None = None) -> dict:
    """Tool: compare the most recent earnings-release (8-K) figure for the
    metric behind `reason_key` against the corresponding 10-Q/10-K value.
    This is the "News Search / dual-source evidence" step for Contribution
    2 -- an independent second-sourced number for the same quarter, not
    derived from the same filing as the primary evaluation.

    Originally this only ever checked Revenue regardless of which reason
    was uncertain (named check_earnings_release_conflict) -- an LLM agent
    run against GOOGL's Broken debt reason correctly noticed it couldn't
    actually verify debt that way. Generalized to take reason_key and pick
    the right metric, once earnings_release.py could parse OperatingIncome
    and LongTermDebt from the press release too (see README.md).

    `as_of` restricts the candidate 8-Ks to those filed on or before that
    date -- without it, this always grabbed the globally latest 8-K
    regardless of what point in time was being evaluated, which would leak
    look-ahead bias into any point-in-time investigation (e.g. re-checking
    a purchase snapshot as of its purchase date).
    """
    if reason_key not in SECONDARY_EVIDENCE_METRICS:
        return {
            "error_code": "INVALID_REASON_KEY",
            "error": f"unknown reason_key '{reason_key}', expected one of {list(SECONDARY_EVIDENCE_METRICS)}",
        }
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]

    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)

    if metric == "LongTermDebt":
        facts = extract_instant_facts(facts_json, cik, "LongTermDebt")
    else:
        facts = extract_quarterly_facts(facts_json, cik, metric)
    facts_by_quarter = latest_version_per_quarter(facts)
    # The period the rule is actually evaluated on at this point in time: the
    # latest quarter with a filed fact on or before as_of (same selection as
    # reason_engine). A release for any other period does not corroborate it.
    pit_by_quarter = latest_version_per_quarter(facts_as_of(facts, as_of)) if as_of else facts_by_quarter
    target_period = _latest_quarter_on_or_before(pit_by_quarter, as_of) if as_of else max(facts_by_quarter, default=None)

    releases = list_earnings_release_filings(ticker, cik)
    if as_of is not None:
        releases = [f for f in releases if f.filed <= as_of]
    if not releases:
        return {
            "error_code": "EVIDENCE_NOT_FOUND",
            "error": f"no earnings-release 8-Ks found for {ticker}" + (f" as of {as_of}" if as_of else ""),
        }

    latest_filing = max(releases, key=lambda f: f.filed)
    rf = get_release_figure(cik, latest_filing, metric)

    if rf.period_end is None or rf.value is None:
        return {
            "ticker": ticker, "metric": metric, "checked": False,
            "period_matches": False, "target_period": target_period,
            "release_period_end": rf.period_end, "as_of": as_of,
            "reason": "could not parse latest earnings release for this metric",
        }

    if target_period is None or rf.period_end != target_period:
        # Not evidence for the period being concluded on -- reported as such so
        # the Evidence Gate cannot count it (and the agent can't present it as
        # corroboration).
        return {
            "ticker": ticker, "metric": metric, "checked": False,
            "period_matches": False,
            "target_period": target_period,
            "release_period_end": rf.period_end,
            "reason": (
                f"latest earnings release parsed as period {rf.period_end}, not the evaluated "
                f"period {target_period} -- it does not corroborate the evaluated figure"
            ),
            "as_of": as_of,
        }

    versions = pit_by_quarter.get(rf.period_end)
    if not versions:
        return {
            "ticker": ticker, "metric": metric, "checked": False,
            "period_matches": False, "target_period": target_period,
            "release_period_end": rf.period_end, "as_of": as_of,
            "reason": f"no eligible 10-Q/10-K fact for period {rf.period_end}",
        }

    filing_value = versions[-1].value
    diff = abs(rf.value - filing_value) / abs(filing_value) if filing_value else None
    return {
        "ticker": ticker,
        "metric": metric,
        "checked": True,
        "period_matches": True,
        "target_period": target_period,
        "period_end": rf.period_end,
        "earnings_release_value": rf.value,
        "filed_value": filing_value,
        "filed_derivation": versions[-1].derivation,
        "diff_pct": diff,
        "conflict": diff is not None and diff > 0.005,
        "as_of": as_of,
    }


def get_filing_context(ticker: str, reason_key: str, as_of: str | None = None) -> dict:
    """Tool: read the actual narrative text from the company's primary
    10-Q/10-K (MD&A section) discussing this reason's metric -- e.g. why
    long-term debt grew, not just that it did. This is what lets an agent
    tell a real financing/acquisition event apart from a restatement or a
    tag-definition mismatch, which check_reason_status's numbers alone
    can't distinguish. See filing_context.py and README.md for how this
    was verified (GOOGL, META, AMZN) and a real case/tag bug it surfaced.

    `as_of` picks the 10-Q/10-K that was actually the latest one filed at
    that point in time, instead of always reading whatever the single most
    recent filing is today -- see latest_10q_accession's docstring.
    """
    if reason_key not in SECONDARY_EVIDENCE_METRICS:
        return {
            "error_code": "INVALID_REASON_KEY",
            "error": f"unknown reason_key '{reason_key}', expected one of {list(SECONDARY_EVIDENCE_METRICS)}",
        }
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]

    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    try:
        accn = latest_10q_accession(ticker, as_of)
    except RuntimeError as e:
        return {"error_code": "EVIDENCE_NOT_FOUND", "error": str(e)}
    snippets = get_filing_narrative(cik, accn, metric)

    return {
        "ticker": ticker,
        "reason_key": reason_key,
        "metric": metric,
        "found": bool(snippets),
        "narrative_excerpts": snippets[:2],
        "as_of": as_of,
    }


TOOL_SPECS = [
    {
        "name": "check_reason_status",
        "description": (
            "Evaluate one numeric investment reason (revenue_growth, "
            "operating_margin, or debt_growth) for a company. Returns the "
            "Supported/Weakened/Broken/Not-enough-data status, the computed "
            "value, and the cited evidence, all as of this investigation's "
            "fixed analysis date -- there is no way to change that date "
            "per tool call; every tool call in this investigation uses the "
            "same one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"},
                "reason_key": {
                    "type": "string",
                    "enum": list(REASON_DEFS.keys()),
                    "description": "Which of the three Phase 1 numeric reasons to check",
                },
            },
            "required": ["ticker", "reason_key"],
        },
    },
    {
        "name": "calculate_metric",
        "description": (
            "Compute the growth rate or margin behind a reason (revenue_growth, "
            "operating_margin, or debt_growth) WITHOUT applying its Supported/"
            "Weakened/Broken threshold -- just the number, its explanation, and "
            "the evidence it's based on. Use this if you want to double-check "
            "a figure in isolation; for the full status judgment use "
            "check_reason_status instead (it computes the same number and also "
            "classifies it). As with every tool here, this always evaluates as "
            "of this investigation's fixed analysis date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"},
                "reason_key": {
                    "type": "string",
                    "enum": list(REASON_DEFS.keys()),
                    "description": "Which of the three Phase 1 numeric reasons' metric to compute",
                },
            },
            "required": ["ticker", "reason_key"],
        },
    },
    {
        "name": "get_secondary_evidence",
        "description": (
            "Compare the company's most recent preliminary earnings-release "
            "(8-K) figure against the final 10-Q/10-K value, for the specific "
            "metric behind the given reason (revenue_growth -> Revenue, "
            "operating_margin -> OperatingIncome, debt_growth -> LongTermDebt). "
            "Use this when that reason's status looks uncertain and a second, "
            "independently-sourced number would help confirm or contradict the "
            "filed figure. As with every tool here, this always evaluates as of "
            "this investigation's fixed analysis date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"},
                "reason_key": {
                    "type": "string",
                    "enum": list(SECONDARY_EVIDENCE_METRICS.keys()),
                    "description": "Which reason's underlying metric to cross-check",
                },
            },
            "required": ["ticker", "reason_key"],
        },
    },
    {
        "name": "get_filing_context",
        "description": (
            "Read the narrative text from the company's primary 10-Q/10-K "
            "(MD&A section) discussing the metric behind a reason -- e.g. "
            "why long-term debt grew, not just that it did. Use this when a "
            "reason's status is Broken (or otherwise looks severe) and you "
            "want to understand the cause -- a real financing/acquisition "
            "event vs. a restatement vs. a tag-definition mismatch -- before "
            "deciding whether to recommend human review and what to tell "
            "the reviewer to look into. As with every tool here, this always "
            "reads the filing that was current as of this investigation's "
            "fixed analysis date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker, e.g. AAPL"},
                "reason_key": {
                    "type": "string",
                    "enum": list(SECONDARY_EVIDENCE_METRICS.keys()),
                    "description": "Which reason's underlying metric to investigate",
                },
            },
            "required": ["ticker", "reason_key"],
        },
    },
]

# A dedicated "final answer" tool, forced as the last step of the loop
# in agent.py's run_with_llm. Free-text final reports turned out to be
# unreliable to parse programmatically (a comparison run against
# compare_planners.py's prose-matching found a real report that said
# "Human Review Needed: **YES**" get misread as "no review needed" by a
# regex looking for the word "recommended") -- structured output removes
# that ambiguity entirely instead of trying to parse it more cleverly.
# Server-side tool: Anthropic runs the search itself and appends the result
# blocks to the same response (see agent.py's run_with_llm) -- unlike the
# other tools above, this is never dispatched by our own code.
#
# Deliberately NOT wired into TOOL_SPECS or run_rule_based's deterministic
# planner: this is a genuine methodological risk, not just another tool.
# Live web search returns TODAY's information, not what was knowable as of
# the analysis date -- using it to help decide a reason's status would
# reintroduce exactly the look-ahead bias the whole point-in-time XBRL
# pipeline exists to prevent. It's offered to the LLM agent only, scoped
# narrowly by the system prompt (see agent.py) to qualitative context for
# the rationale text -- never as evidence for the Supported/Weakened/Broken
# classification itself, which must stay derived from check_reason_status /
# calculate_metric's point-in-time SEC data.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 2}


FINALIZE_REPORT_TOOL = {
    "name": "finalize_report",
    "description": (
        "Submit your final, structured conclusion for every reason you checked. "
        "Call this exactly once, after you've gathered all the evidence you need."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "reason_key": {"type": "string", "enum": list(REASON_DEFS.keys())},
                        "status": {
                            "type": "string",
                            "enum": ["Supported", "Weakened", "Broken", "Not enough data"],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": (
                                "How confident you are in this status given the evidence "
                                "actually gathered -- 'low' when the evidence was thin, "
                                "conflicting, or you're inferring rather than reading a "
                                "direct number. Independent of human_review_recommended: "
                                "a low-confidence Supported can still be fine to not "
                                "escalate, and a high-confidence Broken can still warrant "
                                "review because of its severity."
                            ),
                        },
                        "human_review_recommended": {"type": "boolean"},
                        "rationale": {"type": "string", "description": "One or two sentences why."},
                    },
                    "required": ["reason_key", "status", "confidence", "human_review_recommended", "rationale"],
                },
            },
        },
        "required": ["reasons"],
    },
}

# Single-reason version of FINALIZE_REPORT_TOOL, for baseline1.py/baseline2.py
# which each evaluate exactly one (ticker, reason_key) per call rather than a
# whole company's reason set. Same structured-output rationale as above:
# forcing a schema removes the free-text-parsing ambiguity that bit
# compare_planners.py's first version.
FINALIZE_SINGLE_REASON_TOOL = {
    "name": "finalize_answer",
    "description": (
        "Submit your structured conclusion for this one reason. Call this "
        "exactly once as your final answer, not a free-text summary."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["Supported", "Weakened", "Broken", "Not enough data"],
            },
            "computed_value": {
                "type": ["number", "null"],
                "description": "The growth rate or margin you're basing this on, as a decimal (e.g. 0.15 for 15%), or null if you don't have one.",
            },
            "human_review_recommended": {"type": "boolean"},
            "rationale": {"type": "string", "description": "One or two sentences why."},
        },
        "required": ["status", "computed_value", "human_review_recommended", "rationale"],
    },
}

# Decision Journal / "Attack the Thesis" (Contribution 2 extension): the
# investor states WHY they bought, frozen at purchase time alongside the
# usual rule snapshot, and this tool set lets an agent try to build the
# bear case against that stated thesis specifically -- not just report the
# frozen rule's status. Deliberately NOT reusing the general TOOL_SPECS:
# the ticker/reason/purchase-date are fixed for one specific purchase (set
# in agent.run_thesis_attack's dispatch closures, never LLM-supplied), so
# these take no arguments at all -- there's no `ticker`/`reason_key` for
# the model to get wrong or point at a different position.
THESIS_ATTACK_TOOL_SPECS = [
    {
        "name": "get_frozen_reason_status",
        "description": (
            "Re-derive the frozen rule's status exactly as it was evaluated at the "
            "purchase date -- the baseline the investor's thesis is based on. Takes no "
            "arguments; the ticker, rule, and date are fixed for this review."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_secondary_evidence",
        "description": (
            "Cross-check the metric behind this reason against a second, independent "
            "source (preliminary earnings release vs. the filed figure), as of the "
            "purchase date. Takes no arguments."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_filing_context",
        "description": (
            "Read the company's own narrative explanation (MD&A) for this metric, as of "
            "the purchase date -- the best place to find qualitative counter-evidence a "
            "number alone won't show. Takes no arguments."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

FINALIZE_THESIS_REVIEW_TOOL = {
    "name": "finalize_thesis_review",
    "description": (
        "Submit your final adversarial review of the investor's thesis. Call this "
        "exactly once, after genuinely trying to find counter-evidence -- not as a "
        "rubber stamp."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "thesis_status": {
                "type": "string",
                "enum": ["Still Holds", "Weakened", "Broken"],
                "description": "Your honest verdict after actively trying to attack the thesis.",
            },
            "counter_evidence": {
                "type": "string",
                "description": (
                    "The strongest evidence found AGAINST the thesis, or 'None found' if "
                    "a genuine search turned up nothing -- never fabricate doubt that "
                    "isn't there."
                ),
            },
            "supporting_evidence": {
                "type": "string",
                "description": "What still supports the thesis, for balance.",
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "human_review_recommended": {"type": "boolean"},
            "rationale": {"type": "string", "description": "One or two sentences explaining the verdict."},
        },
        "required": [
            "thesis_status", "counter_evidence", "supporting_evidence",
            "confidence", "human_review_recommended", "rationale",
        ],
    },
}

# Mr. Bull / Mr. Bear Cross-Debate: a second, more structured extension of
# the same Decision Journal idea as run_thesis_attack, but with two
# dedicated roles (build the strongest case FOR the thesis, and separately
# the strongest case AGAINST it) that then rebut each other once each --
# instead of one agent asked to be adversarial toward itself. Reuses the
# same zero-argument, purchase-date-locked tools as the single-sided
# attack (agent.run_bull_bear_debate supplies the dispatch closures).
FINALIZE_DEBATE_CASE_TOOL = {
    "name": "finalize_case",
    "description": (
        "Submit your structured case for your assigned side (Bull or Bear). Call this "
        "exactly once, after genuinely digging for evidence -- not a restatement of the "
        "thesis or a generic list of risks."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 bullet-point arguments for your side, each grounded in evidence you actually gathered.",
            },
            "strongest_evidence": {
                "type": "string",
                "description": "The single strongest piece of evidence for your case, cited specifically.",
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["key_points", "strongest_evidence", "confidence"],
    },
}
