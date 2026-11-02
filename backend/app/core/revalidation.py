"""Thesis Revalidation view data -- a purely mechanical, point-in-time read
of one purchase reason over time. No LLM, and nothing here feeds back into
any status: it re-runs the same frozen-rule evaluation (reason_engine) at
each filing date since the purchase and reports what was knowable then.

Per reason it returns:
- timeline: one point per filing date from the purchase onward, with the
  status/value as of that date and the exact facts (form, filed date,
  accession, EDGAR link) the number was computed from;
- delta: the raw amounts behind the latest number, and their change since
  the purchase-date evaluation;
- monitor: what the next filing would have to show for the rule to hold,
  and an estimated next checkpoint.
"""

from datetime import date, timedelta

from reason_engine import evaluate_margin_level, evaluate_yoy_growth
from tools import load_reason_facts, reason_from_frozen_def
from xbrl_extract import latest_version_per_quarter

# "Historical Context Before Purchase": the same rule replayed at filings
# before the purchase, flagged before_purchase. Context for the trend only --
# not Thesis Revalidation, since the thesis wasn't tied to a purchase yet.
_CONTEXT_POINTS_BEFORE_PURCHASE = 4

# Quarterly filers publish roughly every three months; used only to label an
# *estimated* next checkpoint, never to decide anything.
_QUARTER = timedelta(days=91)


def _fact_dict(f) -> dict:
    return {
        "metric": f.metric, "period_end": f.period_end, "value": f.value, "unit": f.unit,
        "form": f.form, "filed": f.filed, "accession_number": f.accession_number, "url": f.source_url,
    }


def _evaluate(reason, facts, denom_facts, as_of: str):
    if reason.kind == "margin_level":
        return evaluate_margin_level(reason, facts, denom_facts, as_of)
    return evaluate_yoy_growth(reason, facts, as_of)


def _point(ev) -> dict:
    sources = [_fact_dict(f) for f in ev.supporting_evidence]
    return {
        "as_of": ev.as_of_date,
        "status": ev.status,
        "value": ev.computed_value,
        # The period the number describes (current quarter for growth/margin).
        "period_end": sources[0]["period_end"] if sources else None,
        "explanation": ev.explanation,
        "sources": sources,
        "conflicting_versions": len(ev.conflicting_evidence),
    }


def _monitor(reason, facts, latest_point: dict) -> dict:
    """What the next quarter must show, plus an estimated next checkpoint."""
    out: dict = {"comparison": reason.comparison, "threshold": reason.threshold, "kind": reason.kind}
    sources = latest_point.get("sources") or []
    if sources:
        last_filed = max(s["filed"] for s in sources)
        out["estimated_next_filing"] = (date.fromisoformat(last_filed) + _QUARTER).isoformat()
        out["last_period_end"] = sources[0]["period_end"]
    if reason.kind != "yoy_growth" or len(sources) < 2:
        return out
    # Next quarter is compared with the quarter one year before it: the one
    # right after the prior-year quarter used now.
    prior_end = date.fromisoformat(sources[1]["period_end"])
    target = prior_end + _QUARTER
    by_quarter = latest_version_per_quarter(facts)
    candidates = [q for q in by_quarter if abs(date.fromisoformat(q) - target) <= timedelta(days=20)]
    if not candidates:
        return out
    base_q = min(candidates, key=lambda q: abs(date.fromisoformat(q) - target))
    base = max(by_quarter[base_q], key=lambda f: f.filed)
    out["next_base"] = _fact_dict(base)
    # The rule holds next quarter iff value (comparison) base * (1 + threshold).
    out["required_value"] = base.value * (1 + reason.threshold)
    return out


def build_reason_revalidation(ticker: str, frozen_def: dict, purchase_date: str) -> dict:
    reason = reason_from_frozen_def(frozen_def)
    loaded = load_reason_facts(ticker, reason)
    if isinstance(loaded, dict):
        return {"error": loaded["error"]}
    _company, facts, denom_facts = loaded

    filed_dates = sorted({f.filed for f in facts} | {f.filed for f in (denom_facts or [])})
    before = [d for d in filed_dates if d < purchase_date]
    dates = before + [purchase_date] + [d for d in filed_dates if d > purchase_date]

    points: list[dict] = []
    for as_of in dates:
        point = _point(_evaluate(reason, facts, denom_facts, as_of))
        point["before_purchase"] = as_of < purchase_date
        point["is_purchase_date"] = as_of == purchase_date
        # A filing that doesn't change the evaluated period or value adds nothing
        # new -- except the purchase-date point, which always stays.
        if points and not point["is_purchase_date"] and (point["period_end"], point["value"], point["status"]) == (
            points[-1]["period_end"], points[-1]["value"], points[-1]["status"]
        ):
            continue
        points.append(point)
    purchase_idx = next(i for i, p in enumerate(points) if p["is_purchase_date"])
    timeline = points[max(0, purchase_idx - _CONTEXT_POINTS_BEFORE_PURCHASE):]

    first, latest = timeline[purchase_idx - max(0, purchase_idx - _CONTEXT_POINTS_BEFORE_PURCHASE)], timeline[-1]
    delta = None
    if latest["sources"] and first["sources"]:
        delta = {
            # Growth: [current quarter, same quarter a year earlier]; margin: [numerator, denominator].
            "now": latest["sources"],
            "at_purchase": first["sources"],
        }
    return {
        "reason_key": frozen_def.get("reason_key"),
        "description": frozen_def.get("description"),
        "comparison": reason.comparison,
        "threshold": reason.threshold,
        "kind": reason.kind,
        "snapshot": {
            "status": frozen_def.get("status_at_purchase"),
            "value": frozen_def.get("computed_value_at_purchase"),
        },
        "timeline": timeline,
        "now": latest,
        "delta": delta,
        "monitor": _monitor(reason, facts, latest),
    }
