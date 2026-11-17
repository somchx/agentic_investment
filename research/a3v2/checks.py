"""Deterministic evidence checks (no LLM): existence, verbatim quote, company
and filing identity, point-in-time cutoff, reporting period and XBRL value.

The period check compares the evidence unit's period end (an XBRL fact's own
period, or a passage's filing report date) with the claim's period. A filing
report date is a proxy: a 10-K passage can quote last year's column too.
Comparison columns are therefore allowed explicitly (COMPARISON), and an
annual claim may use an interim filing of the same fiscal year only as
partial-period context (PARTIAL_PERIOD)."""

import re
from datetime import date, timedelta

from engine.error_analysis import value_in_quote
from engine.reference import stated_period_end

from evidence_ledger import _norm  # noqa: E402  (backend core, on sys.path via engine)

from .schemas import ClaimPeriod, EvidenceCheck

PERIOD_TOLERANCE_DAYS = 10
MIN_QUOTE_CHARS = 12
_FY = re.compile(r"^FY(\d{4})$")
# SEC HTML uses typographic quotes and dashes; models usually type ASCII. v1's
# validator compared them raw, so e.g. NVDA-14 E8 ("customers’") was flagged
# QUOTE_NOT_IN_PASSAGE although the quote is in the passage.
_TYPOGRAPHIC = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def qnorm(text: str | None) -> str:
    return _norm((text or "").translate(_TYPOGRAPHIC))


def _shift_year(d: str, years: int = -1) -> str:
    x = date.fromisoformat(d)
    try:
        return x.replace(year=x.year + years).isoformat()
    except ValueError:  # 29 February
        return (x - timedelta(days=365)).isoformat()


def _close(a: str | None, b: str | None, tol: int = PERIOD_TOLERANCE_DAYS) -> bool:
    return bool(a and b) and abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= tol


def claim_period(claim, filings: list[dict]) -> ClaimPeriod:
    """The period a claim is about. A date stated in the claim text wins
    ("quarter ended September 30, 2026"); otherwise a fiscal-year label
    ("FY2025") resolves to the eligible 10-K whose report date falls in that
    year (AAPL FY2025 -> 2025-09-27, NVDA FY2026 -> 2026-01-25)."""
    stated = stated_period_end(claim.claim)
    if stated:
        return {"period_end": stated, "basis": "quarter" if "quarter" in claim.claim.lower() else None,
                "comparison_end": _shift_year(stated), "source": "stated_date"}
    m = _FY.match((claim.reporting_period or "").strip())
    if m:
        tenk = [f for f in filings if f.get("form", "").startswith("10-K") and (f.get("report_date") or "")[:4] == m.group(1)]
        if tenk:
            end = max(f["report_date"] for f in tenk)
            return {"period_end": end, "basis": "annual", "comparison_end": _shift_year(end), "source": "fiscal_year_10k"}
    return {"period_end": None, "basis": None, "comparison_end": None, "source": "unknown"}


def period_status(unit_period_end: str | None, period: ClaimPeriod) -> str:
    end = period["period_end"]
    if not end or not unit_period_end:
        return "UNKNOWN"
    if _close(unit_period_end, end):
        return "MATCH"
    if _close(unit_period_end, period["comparison_end"]):
        return "COMPARISON"
    if period["basis"] == "annual" and period["comparison_end"] and period["comparison_end"] < unit_period_end < end:
        return "PARTIAL_PERIOD"
    return "OTHER_PERIOD"


def unit_period_end(unit) -> str | None:
    return getattr(unit, "period_end", None) if unit is not None else None


def check_evidence(ledger, claim, period: ClaimPeriod, evidence_id: str, quote: str | None = None) -> EvidenceCheck:
    """All deterministic checks of one evidence unit; `quote` (if given) is
    checked verbatim for passages and by value for XBRL / derived figures."""
    unit = ledger.get(evidence_id)
    if unit is None:
        return {"evidence_id": evidence_id, "exists": False, "kind": None, "company_ok": None, "filed_by_cutoff": None,
                "period_status": "UNKNOWN", "quote_status": "NOT_CHECKED", "issues": ["UNKNOWN_EVIDENCE_ID"]}
    issues = []
    company_ok = not unit.ticker or unit.ticker == claim.company
    if not company_ok:
        issues.append("TICKER_MISMATCH")
    filed_ok = not unit.filed or unit.filed <= claim.as_of_date
    if not filed_ok:
        issues.append("FUTURE_EVIDENCE")
    if unit.kind in ("filing_passage", "xbrl_fact") and not unit.accession_number:
        issues.append("NO_FILING_IDENTITY")
    pstat = period_status(unit_period_end(unit), period)
    if pstat == "OTHER_PERIOD":
        issues.append("PERIOD_MISMATCH")
    qstat = "NOT_CHECKED"
    if quote is not None:
        q = quote or ""
        if unit.kind == "filing_passage":
            if len(qnorm(q)) < MIN_QUOTE_CHARS:
                qstat = "TOO_SHORT"
            elif qnorm(q) in qnorm(unit.excerpt):
                qstat = "VERIFIED"
            else:
                qstat = "NOT_IN_PASSAGE"
        elif unit.kind in ("xbrl_fact", "derived_metric"):
            # an empty quote is fine: the figure is rendered from the fact itself
            qstat = "VERIFIED" if not q.strip() or any(value_in_quote(v, q) for v in unit.values or []) else "XBRL_VALUE_NOT_IN_QUOTE"
        if qstat not in ("VERIFIED", "NOT_CHECKED"):
            issues.append(qstat if qstat != "NOT_IN_PASSAGE" else "QUOTE_NOT_IN_PASSAGE")
    return {"evidence_id": evidence_id, "exists": True, "kind": unit.kind, "company_ok": company_ok, "filed_by_cutoff": filed_ok,
            "period_status": pstat, "quote_status": qstat, "issues": issues}


def check_citations(ledger, claim, period: ClaimPeriod, items: list) -> tuple[list[dict], list[dict]]:
    """Split cited (evidence_id, quote) items into (kept, excluded). An item is
    excluded on any deterministic failure, incl. a period that is neither the
    claim's period, its comparison period nor (annual claims) the same fiscal
    year."""
    kept, excluded = [], []
    for it in items or []:
        if not isinstance(it, dict):
            excluded.append({"evidence_id": "", "quote": str(it)[:200], "issues": ["MALFORMED_ITEM"]})
            continue
        c = check_evidence(ledger, claim, period, str(it.get("evidence_id") or ""), it.get("quote") or "")
        row = {"evidence_id": c["evidence_id"], "quote": it.get("quote") or "", "issues": c["issues"], "period_status": c["period_status"]}
        (excluded if c["issues"] else kept).append(row)
    return kept, excluded
