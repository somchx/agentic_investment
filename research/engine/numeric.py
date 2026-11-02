"""Deterministic financial verification of numeric assertions.

The LLM states WHAT a claim asserts numerically (metric, period, comparison,
threshold, stated value) as structured `numeric_assertions`; this module,
with no LLM involved, computes the actual figures from SEC XBRL facts filed
on or before the claim's cutoff and decides each assertion TRUE / FALSE /
UNVERIFIABLE. Fact extraction reuses the application's xbrl_extract
(tag-migration merge, restatement versions, MSFT Q4 = FY - 9M derivation),
so the research pipeline and the demo app compute the same numbers.

Checks performed per assertion:
- concept:  the metric is one this module can compute
- period:   the requested period (or the latest one) exists at the cutoff,
            with the requested basis (quarter / annual / instant)
- units:    a ratio threshold must be a ratio (0.10, not 10)
- value:    a stated figure must match the computed one within rounding
- relation: the comparison (>, <, increase, decrease ...) holds
"""

import json
import os
from datetime import date, timedelta
from functools import lru_cache

from . import BACKEND_CORE  # noqa: F401

from evidence_ledger import EvidenceLedger, EvidenceUnit  # noqa: E402
from xbrl_extract import (  # noqa: E402
    INSTANT_METRIC_TAGS, METRIC_TAGS, _extract_instant_from_tags, _extract_quarterly_from_tags, extract_annual_facts)

from .corpus import facts_path

NUMERIC_VERSION = "numeric-1.0"
RECONCILE_VERSION = "numeric-reconcile-1.0"

FLOW_TAGS = {
    "Revenue": METRIC_TAGS["Revenue"],
    "OperatingIncome": METRIC_TAGS["OperatingIncome"],
    "NetIncome": ["NetIncomeLoss"],
    "GrossProfit": ["GrossProfit"],
    "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
    "CapitalExpenditure": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
INSTANT_TAGS = {
    "LongTermDebt": INSTANT_METRIC_TAGS["LongTermDebt"],
    "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue"],
}
RATIOS = {
    "OperatingMargin": ("OperatingIncome", "Revenue"),
    "GrossMargin": ("GrossProfit", "Revenue"),
    "NetMargin": ("NetIncome", "Revenue"),
}
METRICS = sorted([*FLOW_TAGS, *INSTANT_TAGS, *RATIOS])
MEASURES = ("level", "yoy_growth")
BASES = ("quarter", "annual", "instant")
COMPARISONS = (">", ">=", "<", "<=", "increase", "decrease", "approximately")

ASSERTION_SCHEMA = {
    "type": "object",
    "properties": {
        "metric": {"type": "string", "enum": METRICS},
        "measure": {"type": "string", "enum": list(MEASURES),
                    "description": "level = the value itself (USD, or a ratio for *Margin); yoy_growth = change vs the same period one year earlier (ratio for USD metrics, ratio points for margins)"},
        "period_basis": {"type": "string", "enum": list(BASES)},
        "period_end": {"type": ["string", "null"], "description": "YYYY-MM-DD fiscal period end the claim refers to; null = latest reported"},
        "comparison": {"type": "string", "enum": list(COMPARISONS)},
        "threshold": {"type": ["number", "null"], "description": "ratios as decimals (10% = 0.10); USD in dollars"},
        "stated_value": {"type": ["number", "null"], "description": "a figure the claim itself states, same units as threshold"},
    },
    "required": ["metric", "measure", "period_basis", "comparison"],
}

RATIO_TOL = 0.006   # stated ratio vs computed: rounding to a whole percent plus slack
USD_REL_TOL = 0.015  # stated amount vs computed: rounding to e.g. $95B


@lru_cache(maxsize=8)
def company_facts(ticker: str) -> dict:
    """Frozen read of the cached companyfacts file (no TTL refresh)."""
    with open(facts_path(ticker)) as f:
        return json.load(f)


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _facts(ticker: str, metric: str, basis: str, cutoff: str) -> list[dict]:
    fj = company_facts(ticker)
    cik = str(fj.get("cik")).zfill(10)
    if basis == "instant":
        raw = _extract_instant_from_tags(fj, cik, metric, INSTANT_TAGS[metric])
    elif basis == "quarter":
        raw = _extract_quarterly_from_tags(fj, cik, metric, FLOW_TAGS[metric])
    else:
        raw, covered = [], set()
        for tag in FLOW_TAGS[metric]:
            tag_facts = [f for f in extract_annual_facts(fj, cik, tag, custom=True) if (f.accession_number, f.period_end) not in covered]
            raw += tag_facts
            covered |= {(f.accession_number, f.period_end) for f in tag_facts}
    out = []
    for f in raw:
        if not f.filed or f.filed > cutoff or f.form not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
            continue
        out.append({"metric": metric, "period_start": None if basis == "instant" else f.period_start, "period_end": f.period_end,
                    "value": f.value, "unit": f.unit, "form": f.form, "accession_number": f.accession_number, "filed": f.filed,
                    "source_url": f.source_url, "derived": bool(f.derivation), "derivation": f.derivation})
    return out


def _versions_by_period(facts: list[dict]) -> dict[str, list[dict]]:
    by = {}
    for f in facts:
        by.setdefault(f["period_end"], []).append(f)
    for v in by.values():
        v.sort(key=lambda f: f["filed"])
    return by


def _pick(by: dict[str, list[dict]], period_end: str | None) -> tuple[dict | None, list[dict]]:
    if not by:
        return None, []
    if period_end:
        near = [p for p in by if abs(_days(period_end, p)) <= 10]
        if not near:
            return None, []
        p = min(near, key=lambda x: abs(_days(period_end, x)))
    else:
        p = max(by)
    versions = by[p]
    latest = versions[-1]
    conflicts = [v for v in versions[:-1] if latest["value"] and abs(v["value"] - latest["value"]) / abs(latest["value"]) > 0.005]
    return latest, conflicts


def _prior(by: dict[str, list[dict]], current_end: str) -> dict | None:
    target = date.fromisoformat(current_end) - timedelta(days=365)
    cands = [p for p in by if p != current_end and abs((date.fromisoformat(p) - target).days) <= 35]
    if not cands:
        return None
    return by[min(cands, key=lambda p: abs((date.fromisoformat(p) - target).days))][-1]


def _series(ticker: str, metric: str, basis: str, cutoff: str) -> dict[str, list[dict]]:
    return _versions_by_period(_facts(ticker, metric, basis, cutoff))


def _value_at(ticker: str, metric: str, basis: str, cutoff: str, period_end: str | None) -> tuple[float | None, list[dict], list[dict], str | None]:
    """(value, facts used, conflicting versions, resolved period_end)"""
    if metric in RATIOS:
        num, den = RATIOS[metric]
        n, n_conf = _pick(_series(ticker, num, basis, cutoff), period_end)
        if n is None:
            return None, [], [], None
        d, d_conf = _pick(_series(ticker, den, basis, cutoff), n["period_end"])
        if d is None or not d["value"] or d["period_end"] != n["period_end"]:
            return None, [n], [], n["period_end"]
        return n["value"] / d["value"], [n, d], n_conf + d_conf, n["period_end"]
    f, conf = _pick(_series(ticker, metric, basis, cutoff), period_end)
    return (f["value"], [f], conf, f["period_end"]) if f else (None, [], [], None)


def _prior_value(ticker: str, metric: str, basis: str, cutoff: str, current_end: str) -> tuple[float | None, list[dict]]:
    if metric in RATIOS:
        num, den = RATIOS[metric]
        n = _prior(_series(ticker, num, basis, cutoff), current_end)
        d = _prior(_series(ticker, den, basis, cutoff), current_end)
        if not n or not d or not d["value"] or n["period_end"] != d["period_end"]:
            return None, []
        return n["value"] / d["value"], [n, d]
    f = _prior(_series(ticker, metric, basis, cutoff), current_end)
    return (f["value"], [f]) if f else (None, [])


def _holds(comparison: str, x: float, threshold: float | None) -> bool | None:
    if comparison in (">", ">=", "<", "<="):
        if threshold is None:
            return None
        return {">": x > threshold, ">=": x >= threshold, "<": x < threshold, "<=": x <= threshold}[comparison]
    return None


def _cite(ledger: EvidenceLedger, ticker: str, f: dict) -> str:
    return ledger.add(EvidenceUnit(
        kind="xbrl_fact", ticker=ticker, accession_number=f["accession_number"], form=f["form"], filed=f["filed"],
        period_start=f.get("period_start"), period_end=f["period_end"], source_url=f.get("source_url"),
        locator=f"{f['metric']} {f.get('period_start') or ''}..{f['period_end']}", values=[f["value"]], unit=f.get("unit")))


def verify_assertion(ticker: str, cutoff: str, a: dict, ledger: EvidenceLedger) -> dict:
    out = {"assertion": a, "status": "UNVERIFIABLE", "issues": [], "computed": None, "evidence_ids": []}
    metric, measure, basis, comp = a.get("metric"), a.get("measure"), a.get("period_basis"), a.get("comparison")
    threshold, stated = a.get("threshold"), a.get("stated_value")
    if metric not in METRICS:
        out["issues"].append(f"UNKNOWN_CONCEPT:{metric}")
        return out
    if measure not in MEASURES or comp not in COMPARISONS or basis not in BASES:
        out["issues"].append("MALFORMED_ASSERTION")
        return out
    is_instant = metric in INSTANT_TAGS
    if is_instant != (basis == "instant"):
        out["issues"].append(f"BASIS_MISMATCH:{metric} is {'a balance (instant)' if is_instant else 'a flow (quarter/annual)'}")
        return out
    ratio_result = metric in RATIOS or measure == "yoy_growth"
    for name, v in (("threshold", threshold), ("stated_value", stated)):
        if ratio_result and v is not None and abs(v) >= 5:
            out["issues"].append(f"UNIT_MISMATCH:{name} {v} looks like a percent; ratios are decimals (10% = 0.10)")
    if out["issues"]:
        return out

    value, used, conflicts, period = _value_at(ticker, metric, basis, cutoff, a.get("period_end"))
    if value is None:
        out["issues"].append("PERIOD_NOT_AVAILABLE" + (f":{a.get('period_end')}" if a.get("period_end") else ""))
        return out
    computed = {"period_end": period, "basis": basis, "level": value, "unit": "ratio" if metric in RATIOS else "USD",
                "facts": [{k: f[k] for k in ("metric", "period_start", "period_end", "value", "filed", "form", "accession_number", "derived")} for f in used],
                "conflicting_versions": len(conflicts)}
    prior_value, prior_used = _prior_value(ticker, metric, basis, cutoff, period)
    change = None
    if prior_value is not None:
        change = (value - prior_value) if metric in RATIOS else ((value - prior_value) / abs(prior_value) if prior_value else None)
        computed["prior_level"] = prior_value
        computed["prior_period_end"] = prior_used[0]["period_end"] if prior_used else None
        computed["yoy_change"] = change
        computed["yoy_change_unit"] = "ratio_points" if metric in RATIOS else "ratio"
    out["computed"] = computed

    ids = [_cite(ledger, ticker, f) for f in used + prior_used]
    target = value if measure == "level" else change
    derived_vals = [v for v in (value, prior_value, change) if v is not None]
    ids.insert(0, ledger.add(EvidenceUnit(
        kind="derived_metric", ticker=ticker, source="research numeric verifier over SEC XBRL facts",
        accession_number=used[0]["accession_number"], form=used[0]["form"], filed=max(f["filed"] for f in used + prior_used),
        period_end=period, locator=f"{metric} {measure} {basis} @ {period}", values=derived_vals,
        unit=computed["unit"] if measure == "level" else computed.get("yoy_change_unit"))))
    out["evidence_ids"] = ids
    if conflicts:
        out["issues"].append(f"RESTATED_VERSIONS:{len(conflicts)}")

    if target is None:
        out["issues"].append("PRIOR_YEAR_NOT_AVAILABLE")
        return out
    checks = []
    if comp in ("increase", "decrease"):
        base = change if measure == "level" else target
        if base is None:
            out["issues"].append("PRIOR_YEAR_NOT_AVAILABLE")
            return out
        checks.append(base > 0 if comp == "increase" else base < 0)
    elif comp == "approximately":
        if stated is None and threshold is None:
            out["issues"].append("NO_VALUE_TO_COMPARE")
            return out
    else:
        held = _holds(comp, target, threshold)
        if held is None:
            out["issues"].append("THRESHOLD_MISSING")
            return out
        checks.append(held)
    ref = stated if stated is not None else (threshold if comp == "approximately" else None)
    if ref is not None:
        tol = RATIO_TOL if ratio_result else abs(target) * USD_REL_TOL
        match = abs(target - ref) <= tol
        if not match:
            out["issues"].append(f"STATED_VALUE_MISMATCH:stated {ref:g} vs computed {target:.6g}")
        checks.append(match)
    out["status"] = "TRUE" if all(checks) else "FALSE"
    return out


def verify_assertions(ticker: str, cutoff: str, assertions: list[dict], ledger: EvidenceLedger, max_assertions: int = 6) -> list[dict]:
    return [verify_assertion(ticker, cutoff, a, ledger) for a in (assertions or [])[:max_assertions]]


def reconcile_label(llm_label: str, claim_type: str | None, checks: list[dict]) -> tuple[str, str]:
    """Deterministic final label after numeric verification -> (label, rule).

    - no checkable assertion             -> LLM label unchanged
    - any assertion FALSE                -> CONTRADICTED (a stated number / relation is wrong)
    - purely numeric claim, all TRUE     -> SUPPORTED
    - interpretive/mixed claim, all TRUE -> LLM label unchanged (a number moving does not establish its cause)
    - otherwise (some UNVERIFIABLE)      -> LLM label unchanged, flagged in the trace
    """
    if not checks:
        return llm_label, "NOT_APPLICABLE"
    statuses = [c["status"] for c in checks]
    if "FALSE" in statuses:
        return "CONTRADICTED", "NUMERIC_FALSE"
    if all(s == "TRUE" for s in statuses):
        return ("SUPPORTED", "NUMERIC_ALL_TRUE") if claim_type == "numeric" else (llm_label, "NUMERIC_TRUE_QUALITATIVE_UNCHANGED")
    return llm_label, "NUMERIC_PARTIALLY_UNVERIFIABLE"
