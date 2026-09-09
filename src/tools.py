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
from reason_engine import evaluate_margin_level, evaluate_yoy_growth
from sec_client import get_company_facts
from xbrl_extract import extract_instant_facts, extract_quarterly_facts, latest_version_per_quarter

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
        "R3", "", "LongTermDebt", "<", 0.15, kind="yoy_growth",
        description="Long-term debt must not grow more than 15% YoY",
    ),
}


def _evaluation_to_dict(ev) -> dict:
    return {
        "status": ev.status,
        "computed_value": ev.computed_value,
        "explanation": ev.explanation,
        "supporting_evidence": [f.label() for f in ev.supporting_evidence],
        "conflicting_evidence": [f.label() for f in ev.conflicting_evidence],
    }


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
    if reason_key not in REASON_DEFS:
        return {"error": f"unknown reason_key '{reason_key}', expected one of {list(REASON_DEFS)}"}

    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)
    reason = REASON_DEFS[reason_key]

    if reason.metric == "LongTermDebt":
        facts = extract_instant_facts(facts_json, cik, "LongTermDebt")
        denom_facts = None
    else:
        facts = extract_quarterly_facts(facts_json, cik, reason.metric)
        denom_facts = (
            extract_quarterly_facts(facts_json, cik, reason.denominator_metric)
            if reason.kind == "margin_level" else None
        )

    if not facts:
        return {"error": f"no {reason.metric} facts found for {ticker}"}

    if as_of is None:
        as_of = max(f.filed for f in facts)

    if reason.kind == "margin_level":
        ev = evaluate_margin_level(reason, facts, denom_facts, as_of)
    else:
        ev = evaluate_yoy_growth(reason, facts, as_of)

    return company_name, reason, as_of, ev


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


def get_secondary_evidence(ticker: str, reason_key: str) -> dict:
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
    """
    if reason_key not in SECONDARY_EVIDENCE_METRICS:
        return {"error": f"unknown reason_key '{reason_key}', expected one of {list(SECONDARY_EVIDENCE_METRICS)}"}
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]

    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)

    if metric == "LongTermDebt":
        facts = extract_instant_facts(facts_json, cik, "LongTermDebt")
    else:
        facts = extract_quarterly_facts(facts_json, cik, metric)
    facts_by_quarter = latest_version_per_quarter(facts)

    releases = list_earnings_release_filings(ticker, cik)
    if not releases:
        return {"error": f"no earnings-release 8-Ks found for {ticker}"}

    latest_filing = max(releases, key=lambda f: f.filed)
    rf = get_release_figure(cik, latest_filing, metric)

    if rf.period_end is None or rf.value is None:
        return {
            "ticker": ticker, "metric": metric, "checked": False,
            "reason": "could not parse latest earnings release for this metric",
        }

    versions = facts_by_quarter.get(rf.period_end)
    if not versions:
        return {
            "ticker": ticker, "metric": metric, "checked": False,
            "reason": f"no 10-Q/10-K fact for period {rf.period_end}",
        }

    filing_value = versions[-1].value
    diff = abs(rf.value - filing_value) / abs(filing_value) if filing_value else None
    return {
        "ticker": ticker,
        "metric": metric,
        "checked": True,
        "period_end": rf.period_end,
        "earnings_release_value": rf.value,
        "filed_value": filing_value,
        "diff_pct": diff,
        "conflict": diff is not None and diff > 0.005,
    }


def get_filing_context(ticker: str, reason_key: str) -> dict:
    """Tool: read the actual narrative text from the company's primary
    10-Q/10-K (MD&A section) discussing this reason's metric -- e.g. why
    long-term debt grew, not just that it did. This is what lets an agent
    tell a real financing/acquisition event apart from a restatement or a
    tag-definition mismatch, which check_reason_status's numbers alone
    can't distinguish. See filing_context.py and README.md for how this
    was verified (GOOGL, META, AMZN) and a real case/tag bug it surfaced.
    """
    if reason_key not in SECONDARY_EVIDENCE_METRICS:
        return {"error": f"unknown reason_key '{reason_key}', expected one of {list(SECONDARY_EVIDENCE_METRICS)}"}
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]

    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    accn = latest_10q_accession(ticker)
    snippets = get_filing_narrative(cik, accn, metric)

    return {
        "ticker": ticker,
        "reason_key": reason_key,
        "metric": metric,
        "found": bool(snippets),
        "narrative_excerpts": snippets[:2],
    }


TOOL_SPECS = [
    {
        "name": "check_reason_status",
        "description": (
            "Evaluate one numeric investment reason (revenue_growth, "
            "operating_margin, or debt_growth) for a company as of a given "
            "date (or the most recent filing if omitted). Returns the "
            "Supported/Weakened/Broken/Not-enough-data status, the computed "
            "value, and the cited evidence."
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
                "as_of": {
                    "type": "string",
                    "description": "ISO date to simulate as 'today' (point-in-time). Omit for latest.",
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
            "classifies it)."
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
                "as_of": {
                    "type": "string",
                    "description": "ISO date to simulate as 'today' (point-in-time). Omit for latest.",
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
            "filed figure."
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
            "the reviewer to look into."
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
