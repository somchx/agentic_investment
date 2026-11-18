"""A3-side checks of A2's numeric verification (A3 v2.2, items ก and ง). No LLM call.

A2 is left exactly as it is (the baseline). A3's job is to review A2's answer,
so these checks decide when A3 should NOT inherit A2's deterministic numeric
conclusion, and add one figure A2 cannot compute.

N1  numeric validity -- A2's decisive numeric rule (NUMERIC_FALSE / NUMERIC_ALL_TRUE) is not
    used when
      FUTURE_PERIOD   the claim's (historical) period ends after the evidence cutoff: nothing
                      filed can report it, so the answer is INSUFFICIENT_EVIDENCE
      PERIOD_MISMATCH the deciding check computed a period ending > PERIOD_TOL_DAYS away from
                      the claim's period (A2 fell back to the latest available period)
      SCOPE_MISMATCH  the claim is restricted to a segment or region (decidability record) but
                      A2's metrics are consolidated company totals
    The label then comes from the reviewer's valid deciding findings when they all point one
    way, else INSUFFICIENT_EVIDENCE.
N2  window free cash flow -- a claim that free cash flow rose / fell over its period is checked
    with FCF = operating cash flow - capital expenditure over exactly that window (filed fact for
    the window, else the sum of filed quarters) against the same window a year earlier. A
    contradicted conjunct makes the claim CONTRADICTED; a confirmed one never makes it SUPPORTED
    on its own (other parts of the claim may be untested).
"""
import re
from datetime import date, timedelta

NUMERIC_CHECKS_VERSION = "a3v2-numeric-checks-0.1"
PERIOD_TOL_DAYS = 10
NUMERIC_DECISIVE = {"NUMERIC_FALSE": "CONTRADICTED", "NUMERIC_ALL_TRUE": "SUPPORTED"}
_FCF = re.compile(r"free cash flow", re.I)
_UP = re.compile(r"\b(improv\w*|increas\w*|grew|grow\w*|rose|rise\w*|higher|expand\w*)\b", re.I)
_DOWN = re.compile(r"\b(declin\w*|decreas\w*|fell|fall\w*|lower|shrank|shrink\w*|deteriorat\w*|weaken\w*)\b", re.I)


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def numeric_validity(rule: str | None, checks: list[dict], claim_period: dict | None, cutoff: str, record: dict | None) -> list[str]:
    """Issues that make A2's decisive numeric conclusion unusable for A3 (empty = usable or not decisive)."""
    if rule not in NUMERIC_DECISIVE:
        return []
    p = claim_period or {}
    issues = []
    if p.get("end") and p.get("orientation", "historical") == "historical" and p.get("kind") == "duration" and p["end"] > cutoff:
        issues.append("FUTURE_PERIOD")
    want = "FALSE" if rule == "NUMERIC_FALSE" else "TRUE"
    deciding = [c for c in checks or [] if c.get("status") == want]
    if p.get("end") and p.get("source") not in (None, "unknown", "default"):
        ends = [(c.get("computed") or {}).get("period_end") for c in deciding]
        if ends and all(e and abs((_d(e) - _d(p["end"])).days) > PERIOD_TOL_DAYS for e in ends):
            issues.append("PERIOD_MISMATCH")
    scope = (record or {}).get("scope") or {}
    if scope.get("segment") or scope.get("region"):
        issues.append("SCOPE_MISMATCH")
    return issues


def label_from_findings(findings: list[dict]) -> str:
    rel = {f.get("relation") for f in findings if f.get("validation_status") == "VALID" and f.get("relation") in ("ENTAILS", "CONTRADICTS")}
    return {frozenset({"ENTAILS"}): "SUPPORTED", frozenset({"CONTRADICTS"}): "CONTRADICTED"}.get(frozenset(rel), "INSUFFICIENT_EVIDENCE")


def _window_value(ticker: str, metric: str, start: str, end: str, cutoff: str, months: int) -> tuple[float | None, list[dict]]:
    """Same rule as a3v2.periods.derive_for_claim, without registering evidence: a filed fact for exactly the
    window, else the sum of filed single quarters that tile it."""
    from engine.numeric import _facts
    from .periods import TOL, _close, _direct_fact
    f = _direct_fact(ticker, metric, start, end, cutoff)
    if f:
        return f["value"], [f]
    if not months or months % 3 or months <= 3:
        return None, []
    qs = sorted((q for q in _facts(ticker, metric, "quarter", cutoff)
                 if _d(start) - timedelta(days=TOL) <= _d(q["period_start"]) and _d(q["period_end"]) <= _d(end) + timedelta(days=TOL)),
                key=lambda q: (q["period_end"], q["filed"]))
    latest = {}
    for q in qs:
        latest[q["period_end"]] = q
    qs = list(latest.values())
    if len(qs) != months // 3 or not _close(qs[0]["period_start"], start) or not _close(qs[-1]["period_end"], end):
        return None, []
    return sum(q["value"] for q in qs), qs


def fcf_direction_check(claim_text: str, ticker: str, cutoff: str, claim_period: dict | None) -> dict:
    """N2. {'status': TRUE | FALSE | NOT_APPLICABLE | UNVERIFIABLE, 'current', 'prior', 'change', 'inputs'}."""
    text = claim_text or ""
    m = _FCF.search(text)
    if not m:
        return {"status": "NOT_APPLICABLE"}
    tail = text[m.end():m.end() + 60]  # the verb that follows "free cash flow"
    up, down = bool(_UP.search(tail)), bool(_DOWN.search(tail))
    p = claim_period or {}
    if up == down or p.get("kind") != "duration" or not p.get("start") or not (p.get("comparison") or {}).get("start"):
        return {"status": "NOT_APPLICABLE" if up == down else "UNVERIFIABLE"}
    vals, inputs = {}, []
    for role, (s, e) in (("current", (p["start"], p["end"])), ("prior", (p["comparison"]["start"], p["comparison"]["end"]))):
        ocf, fo = _window_value(ticker, "OperatingCashFlow", s, e, cutoff, p.get("months"))
        capex, fc = _window_value(ticker, "CapitalExpenditure", s, e, cutoff, p.get("months"))
        if ocf is None or capex is None:
            return {"status": "UNVERIFIABLE", "missing": f"{role} {s}..{e}"}
        vals[role] = ocf - capex
        inputs += fo + fc
    change = vals["current"] - vals["prior"]
    holds = change > 0 if up else change < 0
    return {"status": "TRUE" if holds else "FALSE", "direction": "up" if up else "down", "current": vals["current"],
            "prior": vals["prior"], "change": change, "inputs": inputs, "version": NUMERIC_CHECKS_VERSION}


def apply_numeric_checks(final: str, rule: str | None, validity: list[str], fcf: dict, findings: list[dict],
                         record: dict | None) -> tuple[str, str | None]:
    """N1 then N2 on top of the guard + decidability result. Returns (label, reason or None)."""
    reason = None
    if validity and final == NUMERIC_DECISIVE.get(rule):
        new = "INSUFFICIENT_EVIDENCE" if "FUTURE_PERIOD" in validity else label_from_findings(findings)
        if new == "SUPPORTED" and (record or {}).get("predicate_type") == "EVALUATIVE" and (record or {}).get("criterion_source") != "CLAIM_STATES":
            new = "INSUFFICIENT_EVIDENCE"  # same downgrade as D-sup
        if new != final:
            final, reason = new, "N1_" + "+".join(validity)
    if (fcf or {}).get("status") == "FALSE" and final != "CONTRADICTED":
        final, reason = "CONTRADICTED", ((reason + "+") if reason else "") + "N2_FCF_FALSE"
    return final, reason


# ---- E1 evidence coverage (advisor requirement, A3.15): a final SUPPORTED / CONTRADICTED needs a validated basis
COVERAGE_VERSION = "a3v2-coverage-0.1"
_REL = {"SUPPORTED": "ENTAILS", "CONTRADICTED": "CONTRADICTS"}


def evidence_basis(final: str, findings: list[dict], rule: str | None, validity: list[str], deterministic: bool) -> list[str]:
    """What backs a decisive final label: a VALID reviewer finding in that direction (after quote check 1.1), A2's
    decisive numeric rule pointing the same way and not invalidated by N1, or an A3 deterministic check (N1/N2/C)."""
    basis = []
    if any(f.get("validation_status") == "VALID" and f.get("relation") == _REL.get(final) for f in findings):
        basis.append("VALID_FINDING")
    if NUMERIC_DECISIVE.get(rule) == final and not validity:
        basis.append("A2_NUMERIC_RULE")
    if deterministic:
        basis.append("A3_DETERMINISTIC_CHECK")
    return basis


def apply_coverage(final: str, basis: list[str]) -> tuple[str, str | None]:
    if final in _REL and not basis:
        return "INSUFFICIENT_EVIDENCE", "E1_NO_VALIDATED_BASIS"
    return final, None
