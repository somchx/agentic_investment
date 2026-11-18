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


# Quote check 1.1 (A3 v2.2 preparation; not used by v2.0-v2.1.1, which keep exact
# substring matching). A model often quotes a table by stitching rows ("Revenue
# $ 139,996 $ 120,810 16% Operating expenses 31,100 ...", skipping a row) or by
# joining excerpts with "...". Such a quote is accepted when
#   FRAGMENTS  every "..."-separated fragment (>= MIN_QUOTE_CHARS) is in the passage, in order, or
#   NUMBERS    it carries >= 2 figures (bare years do not count), all of them appear in the passage in the same order,
#              and at least half of its words (>= 4 letters) appear in the passage.
# Anything else stays NOT_IN_PASSAGE.
QUOTE_CHECK_V11 = "a3v2-quote-check-1.1"
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z]{4,}")


_YEAR = re.compile(r"^(19|20)\d\d$")


def _figures(text: str) -> list[str]:
    """Figures of >= 2 digits; bare years (1900-2099) are labels, not figures."""
    out = [f.replace(",", "") for f in _FIGURE.findall(text or "") if len(f.replace(",", "").replace(".", "")) >= 2]
    return [f for f in out if not _YEAR.match(f)]


def _in_order(needles: list[str], hay: list[str]) -> bool:
    it = iter(hay)
    return all(any(n == h for h in it) for n in needles)


def tolerant_quote_status(quote: str, passage: str) -> str:
    """VERIFIED | VERIFIED_FRAGMENTS | VERIFIED_NUMBERS | TOO_SHORT | NOT_IN_PASSAGE (quote check 1.1)."""
    q, p = qnorm(quote), qnorm(passage)
    if len(q) < MIN_QUOTE_CHARS:
        return "TOO_SHORT"
    if q in p:
        return "VERIFIED"
    parts = [x.strip() for x in re.split(r"\.\.\.|\u2026", q) if x.strip()]
    if len(parts) > 1 and all(len(x) >= MIN_QUOTE_CHARS for x in parts):
        pos = 0
        for x in parts:
            pos = p.find(x, pos)
            if pos < 0:
                break
            pos += len(x)
        else:
            return "VERIFIED_FRAGMENTS"
    figs = _figures(q)
    words = [w.lower() for w in _WORD.findall(q)]
    if len(figs) >= 2 and _in_order(figs, _figures(p)) and (not words or sum(w in p for w in words) * 2 >= len(words)):
        return "VERIFIED_NUMBERS"
    return "NOT_IN_PASSAGE"


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
    compat = None
    if period.get("version"):  # A3 v2.1: normalised period and duration-aware compatibility
        from .periods import PERIODS_VERSION_V11, compatibility, evidence_period, temporal_class
        ev = evidence_period(unit, quote, period, ledger)
        compat = {**compatibility(period, ev), "evidence_period": ev}
        if period["version"] == PERIODS_VERSION_V11:
            compat["temporal"] = temporal_class(quote) if unit.kind == "filing_passage" and quote else (
                "HISTORICAL_FACT" if unit.kind != "filing_passage" else "NOT_CHECKED")
        pstat = compat["status"]
        if pstat == "MISMATCH":
            issues.append("PERIOD_MISMATCH")
    else:
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
    out = {"evidence_id": evidence_id, "exists": True, "kind": unit.kind, "company_ok": company_ok, "filed_by_cutoff": filed_ok,
           "period_status": pstat, "quote_status": qstat, "issues": issues}
    if compat is not None:
        out["period_compatibility"] = compat
    return out


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


_DECIDING = ("ENTAILS", "CONTRADICTS")
_NON_RESULT = ("FORWARD_LOOKING_OR_RISK", "MANAGEMENT_INTENT", "OTHER_CONTEXT", "DEFINITION")


def revalidate_quotes_v11(findings: list[dict], excerpt_of, period: dict) -> tuple[list[dict], list[str]]:
    """Quote check 1.1 applied to validated findings, for the guard only: a finding downgraded only because its
    key quote was not found verbatim is re-checked with `tolerant_quote_status`; if it now passes, the rest of the
    reviewer's validation chain (period, temporal class, non-result evidence) is re-applied from the recorded
    per-evidence checks. `excerpt_of(evidence_id)` returns the passage text. The reviewer's own findings, and so the
    reconciliation request, are unchanged."""
    out, restored = [], []
    historical = (period or {}).get("orientation") == "historical"
    for f in findings:
        if f.get("validation_status") != "KEY_QUOTE_NOT_IN_EVIDENCE":
            out.append(f)
            continue
        q = [c for c in f.get("checks") or [] if c.get("quote_status") == "VERIFIED" or
             tolerant_quote_status(f.get("key_quote") or "", excerpt_of(c.get("evidence_id")) or "") in ("VERIFIED", "VERIFIED_FRAGMENTS", "VERIFIED_NUMBERS")]
        if not q:
            out.append(f)
            continue
        rel = f["declared_relation"]
        temporal = [(c.get("period_compatibility") or {}).get("temporal") for c in q]
        status = ("PERIOD_MISMATCH" if any(c.get("period_status") == "MISMATCH" for c in q) else
                  "PERIOD_UNKNOWN" if any(c.get("period_status") == "UNKNOWN" for c in q) else
                  "FORWARD_LOOKING_FOR_HISTORICAL_CLAIM" if historical and rel in _DECIDING and "FORWARD_LOOKING" in temporal else
                  "TEMPORAL_MIXED_OR_UNCLEAR" if historical and rel in _DECIDING and "MIXED_OR_UNCLEAR" in temporal else "VALID")
        relation, down = rel, None
        if rel in _DECIDING and status != "VALID":
            relation, down = "RELATED_NOT_DECIDING", status
        elif rel in _DECIDING and f.get("evidence_type") in _NON_RESULT:
            relation, down = "RELATED_NOT_DECIDING", f"NON_RESULT_EVIDENCE:{f['evidence_type']}"
        out.append({**f, "relation": relation, "validation_status": status, "downgraded_reason": down, "quote_check": "1.1"})
        restored.append(f"{f['finding_id']}:{status}")
    return out, restored
