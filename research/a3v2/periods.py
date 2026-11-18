"""A3 v2.1 reporting-period normalisation and compatibility (deterministic, no LLM).

v2.0 compared end dates only, so a nine-month or trailing-twelve-month figure
ending on the claim's date passed as MATCH, and 21/72 dev-v0.2 claims had no
resolved period at all (every check then said UNKNOWN and let evidence through).
This module gives every claim and every evidence unit a period with a start,
an end, a duration and a kind (duration / instant), and compares them:

    EXACT_MATCH                           same kind, same end (+-10 days) and same
                                          duration; or the prior-year comparison window
    COMPATIBLE_AFTER_VERIFIED_DERIVATION  a deterministic derivation (sum of filed
                                          single-quarter facts, or a filed YTD fact)
                                          produced exactly the claim's window
    MISMATCH                              different duration, different date, or
                                          instant vs duration
    UNKNOWN                               the claim's or the evidence's period could
                                          not be established -- never treated as a match

Sources, in order. Claim: dates and period words in the claim text, then the
`reporting_period` field; fiscal quarters are mapped to dates with the
company's own SEC filings (fiscal year / fiscal period of each 10-Q / 10-K
filed on or before the cutoff). Evidence: an XBRL fact's own start / end; for
a filing passage, period words in the key quote, then in the passage, then the
filing's default (a 10-K covers its fiscal year). No reference label is read."""

import json
import re
from datetime import date, timedelta
from functools import lru_cache

from engine.corpus import facts_path

PERIODS_VERSION = "a3v2-periods-1.0"
# 1.1 (A3 v2.1.1): A2-numeric derived values get their window from their source
# XBRL facts; a key quote's own year references are checked against the claim;
# key quotes are classified HISTORICAL_FACT / FORWARD_LOOKING / MIXED_OR_UNCLEAR.
# Every 1.1 rule is gated on the period's version, so 1.0 behaviour is unchanged.
PERIODS_VERSION_V11 = "a3v2-periods-1.1"
VERSIONS = {"1.0": PERIODS_VERSION, "1.1": PERIODS_VERSION_V11}
TOL = 10  # days
DERIVATION_PREFIX = "PeriodDerivation"

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"], start=1)}
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_DATE = r"((?:january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2}, \d{4})"

# duration words -> months; "TTM" is 12 months ending at a quarter end that is not the fiscal year end
MARKERS = [
    (re.compile(r"\b(trailing|last) twelve months\b|\bttm\b|\bltm\b"), 12, "TTM"),
    (re.compile(r"\btwelve months ended\b"), 12, "TWELVE_MONTHS"),
    (re.compile(r"\bnine months\b|\bfirst nine months\b|\bnine-month\b"), 9, "YTD9"),
    (re.compile(r"\bsix months\b|\bfirst half\b|\bh1\b|\bsix-month\b"), 6, "YTD6"),
    (re.compile(r"\bsecond half\b|\bh2\b"), 6, "H2"),
    (re.compile(r"\bthree months\b|\bquarter\b|\bq[1-4]\b|\bquarterly\b"), 3, "QUARTER"),
    (re.compile(r"\b(fiscal )?year ended\b|\bfiscal (year )?20\d\d\b|\bfull[- ]year\b|\bannual\b"), 12, "FISCAL_YEAR"),
]


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _close(a: str | None, b: str | None, tol: int = TOL) -> bool:
    return bool(a and b) and abs((_d(a) - _d(b)).days) <= tol


def _months(start: str, end: str) -> int:
    return max(1, round(((_d(end) - _d(start)).days + 1) / 30.44))


def _shift(d: str, years: int = -1) -> str:
    x = _d(d)
    try:
        return x.replace(year=x.year + years).isoformat()
    except ValueError:
        return (x + timedelta(days=365 * years)).isoformat()


def _parse_date(text: str) -> str | None:
    m = re.match(r"([a-z]+) (\d{1,2}), (\d{4})", text.strip().lower())
    return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))).isoformat() if m else None


# ------------------------------------------------------------ fiscal calendar

@lru_cache(maxsize=64)
def fiscal_calendar(ticker: str, cutoff: str) -> tuple:
    """((fy, fp, end, form), ...) for each 10-K / 10-Q filed on or before the
    cutoff: fiscal year / period from the filing's XBRL facts, period end =
    the filing's report date in SEC's submissions index (dei facts such as a
    later share-count date must not move it)."""
    from engine.corpus import CorpusUnavailable, list_filings
    try:
        with open(facts_path(ticker)) as f:
            fj = json.load(f)
        report = {r["accession_number"]: r["report_date"] for r in list_filings(ticker)
                  if r["form"] in ("10-K", "10-Q") and r["filed"] <= cutoff and r.get("report_date")}
    except (OSError, ValueError, CorpusUnavailable):
        return ()
    by_accn = {}
    for concept in fj.get("facts", {}).get("us-gaap", {}).values():
        for unit in concept.get("units", {}).values():
            for v in unit:
                if v.get("accn") in report and v.get("fy") and v.get("fp") and v.get("form") in ("10-K", "10-Q"):
                    by_accn.setdefault(v["accn"], (v["fy"], v["fp"]))
    rows = {}
    for accn, (fy, fp) in by_accn.items():
        rows.setdefault((fy, fp), report[accn])
    return tuple(sorted(((fy, fp, end, "10-K" if fp == "FY" else "10-Q") for (fy, fp), end in rows.items()), key=lambda r: r[2]))


def _period_end(cal: tuple, fy: int, fp: str) -> str | None:
    hit = [r[2] for r in cal if r[0] == fy and r[1] == fp]
    return hit[0] if hit else None


def _fy_end_projected(cal: tuple, fy: int) -> str | None:
    """Fiscal year end; projected one year on from the previous year's when
    the year has not been reported by the cutoff."""
    end = _period_end(cal, fy, "FY")
    if end:
        return end
    prev = _period_end(cal, fy - 1, "FY")
    return _shift(prev, 1) if prev else None


def _fy_start(cal: tuple, fy: int) -> str | None:
    prev = _period_end(cal, fy - 1, "FY")
    if prev:
        return (_d(prev) + timedelta(days=1)).isoformat()
    end = _fy_end_projected(cal, fy)
    return (_d(_shift(end, -1)) + timedelta(days=1)).isoformat() if end else None


def _quarter_end(cal: tuple, fy: int, q: int) -> tuple[str | None, bool]:
    """(end, projected)"""
    if q == 4:
        end = _period_end(cal, fy, "FY")
        return (end, False) if end else (_fy_end_projected(cal, fy), True)
    end = _period_end(cal, fy, f"Q{q}")
    if end:
        return end, False
    prev = _period_end(cal, fy - 1, f"Q{q}")
    return (_shift(prev, 1), True) if prev else (None, True)


def _calendar_aligned(cal: tuple) -> bool:
    ends = [r[2] for r in cal if r[1] == "FY"]
    return bool(ends) and all(abs((_d(e) - date(_d(e).year, 12, 31)).days) <= TOL or abs((_d(e) - date(_d(e).year + 1, 1, 1)).days) <= TOL
                              for e in ends[-2:])


def _fy_for_end(cal: tuple, end: str) -> int | None:
    """Fiscal year whose window contains `end`."""
    fys = sorted({r[0] for r in cal})
    for fy in fys + [fys[-1] + 1] if fys else []:
        s, e = _fy_start(cal, fy), _fy_end_projected(cal, fy)
        if s and e and _d(s) - timedelta(days=TOL) <= _d(end) <= _d(e) + timedelta(days=TOL):
            return fy
    return None


def _window(cal: tuple, fy: int, end: str, months: int) -> str:
    """Start of a `months`-long window ending at `end` inside the fiscal calendar."""
    if months == 12 and _close(end, _fy_end_projected(cal, fy)):
        return _fy_start(cal, fy) or (_d(_shift(end, -1)) + timedelta(days=1)).isoformat()
    ends = sorted({r[2] for r in cal} | {end})
    earlier = [e for e in ends if (_d(end) - _d(e)).days > 20]
    for e in reversed(earlier):
        if abs(_months((_d(e) + timedelta(days=1)).isoformat(), end) - months) == 0:
            return (_d(e) + timedelta(days=1)).isoformat()
    x = _d(end)
    m = x.month - months
    y = x.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return (date(y, m, 1) if x.day >= 28 else date(y, m, min(x.day, 28)) + timedelta(days=1)).isoformat()


# ------------------------------------------------------------ claim period

def _mk(kind, end, months, cal, fy, label, source, notes, start=None):
    if kind == "instant":
        return {"version": PERIODS_VERSION, "kind": "instant", "start": None, "end": end, "months": 0, "label": label,
                "fiscal_year": fy, "source": source, "comparison": {"start": None, "end": _shift(end)}, "notes": notes,
                "period_end": end, "comparison_end": _shift(end), "basis": "instant"}
    start = start or _window(cal, fy, end, months)
    return {"version": PERIODS_VERSION, "kind": "duration", "start": start, "end": end, "months": months, "label": label,
            "fiscal_year": fy, "source": source, "comparison": {"start": _shift(start), "end": _shift(end)}, "notes": notes,
            "period_end": end, "comparison_end": _shift(end), "basis": "annual" if months == 12 else ("quarter" if months == 3 else f"{months}m")}


def unknown(notes: list[str]) -> dict:
    return {"version": PERIODS_VERSION, "kind": None, "start": None, "end": None, "months": None, "label": None, "fiscal_year": None,
            "source": "unknown", "comparison": {"start": None, "end": None}, "notes": notes, "period_end": None,
            "comparison_end": None, "basis": None}


def normalize_claim_period(claim, version: str = PERIODS_VERSION) -> dict:
    """The claim's reporting period (see _normalize), stamped with the rule version."""
    p = _normalize(claim)
    p["version"] = version
    if version != PERIODS_VERSION:
        p["orientation"] = "forward" if FORWARD.search(" ".join((claim.claim or "").lower().split())) else "historical"
        p["years"] = sorted(_years_of(p))
    return p


def _years_of(p: dict) -> set[int]:
    """Calendar and fiscal years a claim period (and its prior-year comparison) speaks about."""
    ys = set()
    for a, b in ((p.get("start"), p.get("end")), (p["comparison"].get("start"), p["comparison"].get("end"))):
        if b:
            ys |= set(range(_d(a or b).year, _d(b).year + 1))
    if p.get("fiscal_year"):
        ys |= {p["fiscal_year"], p["fiscal_year"] - 1}
    return ys


def _normalize(claim) -> dict:
    """The claim's reporting period from its text, then its reporting_period field."""
    cal = fiscal_calendar(claim.company, claim.as_of_date)
    notes = []
    if not cal:
        return unknown(["no fiscal calendar for the company at the cutoff"])
    aligned = _calendar_aligned(cal)
    t = " ".join((claim.claim or "").lower().split())

    def fiscal_or_calendar_year(year: int, explicit_fiscal: bool):
        if explicit_fiscal or aligned:
            return year
        notes.append(f"calendar year {year} on a non-calendar fiscal year")
        return None

    # 1. a balance at a date
    m = re.search(r"\b(?:as of|by|at) " + _DATE, t)
    if m and not re.search(r"\b(quarter|months|year) ended\b", t):
        end = _parse_date(m.group(1))
        return _mk("instant", end, 0, cal, _fy_for_end(cal, end), f"instant {end}", "text_date", notes)
    m = re.search(r"\b(?:balance sheet ended|at the end of) (fiscal )?(\d{4})\b", t)
    if m:
        fy = fiscal_or_calendar_year(int(m.group(2)), bool(m.group(1)))
        end = _period_end(cal, fy, "FY") if fy else None
        if end:
            return _mk("instant", end, 0, cal, fy, f"instant FY{fy} end", "text_fiscal", notes)
    # 2. a duration ending on a stated date
    for pat, months in ((r"\b(?:quarter|three months) ended ", 3), (r"\b(?:six months|first half) ended ", 6),
                        (r"\bnine months ended ", 9), (r"\b(?:fiscal year|year|twelve months) ended ", 12)):
        m = re.search(pat + _DATE, t)
        if m:
            end = _parse_date(m.group(1))
            fy = _fy_for_end(cal, end)
            return _mk("duration", end, months, cal, fy, f"{months}M ended {end}", "text_date", notes)
    # 3. fiscal / calendar quarter, half, nine months, year
    m = re.search(r"\b(first|second|third|fourth)[- ]quarter(?: of)?( fiscal)? (\d{4})\b", t) or \
        re.search(r"\bq([1-4])( fiscal)? (\d{4})\b", t)
    if m:
        q = ORD.get(m.group(1)) or int(m.group(1))
        year, fiscal = int(m.group(3)), bool(m.group(2))
        if fiscal or aligned:
            end, proj = _quarter_end(cal, year, q)
            if end:
                if proj:
                    notes.append(f"Q{q} FY{year} not reported by the cutoff; end projected from the prior year")
                return _mk("duration", end, 3, cal, year, f"Q{q} FY{year}", "projected" if proj else "text_fiscal", notes)
        else:
            cal_end = date(year, 3 * q, 31 if q in (1, 4) else 30).isoformat()
            hit = [r for r in cal if r[1] != "FY" and _close(r[2], cal_end)] + [r for r in cal if r[1] == "FY" and _close(r[2], cal_end)]
            if hit:
                return _mk("duration", hit[0][2], 3, cal, hit[0][0], f"calendar Q{q} {year}", "text_calendar", notes)
            return unknown(notes + [f"calendar Q{q} {year} does not coincide with a fiscal quarter of this company"])
    m = re.search(r"\b(first|second) half of( fiscal)? (\d{4})\b", t)
    if m:
        fy = fiscal_or_calendar_year(int(m.group(3)), bool(m.group(2)))
        if fy:
            end, proj = _quarter_end(cal, fy, 2 if m.group(1) == "first" else 4)
            if end:
                start = _fy_start(cal, fy) if m.group(1) == "first" else None
                if m.group(1) == "second":
                    q2, _ = _quarter_end(cal, fy, 2)
                    start = (_d(q2) + timedelta(days=1)).isoformat() if q2 else None
                return _mk("duration", end, 6, cal, fy, f"{'H1' if m.group(1) == 'first' else 'H2'} FY{fy}",
                           "projected" if proj else "text_fiscal", notes, start=start)
    m = re.search(r"\bfirst nine months of( fiscal)? (\d{4})\b", t) or re.search(r"\bin( fiscal)? (\d{4}) through the end of september\b", t)
    if m:
        fy = fiscal_or_calendar_year(int(m.group(2)), bool(m.group(1)))
        end = _quarter_end(cal, fy, 3)[0] if fy else None
        if end:
            return _mk("duration", end, 9, cal, fy, f"9M FY{fy}", "text_fiscal", notes, start=_fy_start(cal, fy))
    m = re.search(r"\bin( fiscal)? (\d{4}) through the end of (\w+)\b", t)
    if m and m.group(3) in MONTHS:
        fy = fiscal_or_calendar_year(int(m.group(2)), bool(m.group(1)))
        hit = [r for r in cal if fy and r[0] == fy and _d(r[2]).month == MONTHS[m.group(3)]]
        if hit:
            start = _fy_start(cal, fy)
            return _mk("duration", hit[0][2], _months(start, hit[0][2]), cal, fy, f"YTD FY{fy} to {hit[0][2]}", "text_fiscal", notes, start=start)
    m = re.search(r"\bfiscal (?:year )?(\d{4})\b", t)
    if m:
        fy = int(m.group(1))
        end = _fy_end_projected(cal, fy)
        if end:
            return _mk("duration", end, 12, cal, fy, f"FY{fy}", "text_fiscal", notes)
    m = re.search(r"\b(20\d\d)\b", t)
    if m:
        fy = fiscal_or_calendar_year(int(m.group(1)), False)
        end = _fy_end_projected(cal, fy) if fy else None
        if end:
            return _mk("duration", end, 12, cal, fy, f"FY{fy} (calendar year)", "text_calendar", notes)
    # 4. the reporting_period field
    rp = (claim.reporting_period or "").strip().upper()
    m = re.match(r"^(FY)?(\d{4})(?: (Q[1-4]|H[12]))?$", rp)
    if m:
        fiscal, year, part = bool(m.group(1)), int(m.group(2)), m.group(3)
        if not fiscal and not aligned:
            return unknown(notes + [f"reporting_period {rp}: calendar label on a non-calendar fiscal year"])
        notes.append(f"period from reporting_period {rp}")
        if not part:
            end = _fy_end_projected(cal, year)
            return _mk("duration", end, 12, cal, year, f"FY{year}", "reporting_period", notes) if end else unknown(notes)
        if part.startswith("Q"):
            end, proj = _quarter_end(cal, year, int(part[1]))
            return _mk("duration", end, 3, cal, year, f"{part} FY{year}", "reporting_period", notes) if end else unknown(notes)
        end, proj = _quarter_end(cal, year, 2 if part == "H1" else 4)
        start = _fy_start(cal, year) if part == "H1" else None
        return _mk("duration", end, 6, cal, year, f"{part} FY{year}", "reporting_period", notes, start=start) if end else unknown(notes)
    return unknown(notes + ["no period in the claim text or reporting_period"])


# ------------------------------------------------------------ evidence period

# --------------------------------------------------- statement-level time (1.1)

FORWARD = re.compile(r"\b(we|the company|management) (anticipate|expect|plan|intend|project|believe|estimate)s?\b|\banticipat(e|es|ed|ing)\b|"
                     r"\b(is|are) (expected|projected|anticipated|forecast) to\b|\bwill\b|\boutlook\b|\bforecast\b|\bguidance\b|"
                     r"\bgoing forward\b|\bin the future\b|\bnext (year|quarter)\b|\bpositioned (for|to)\b|\bwe aim\b|\bseek to\b")
HISTORICAL = re.compile(r"\b(increased|decreased|grew|declined|rose|fell|was|were|had|reported|recorded|totaled|totalled|improved|"
                        r"reflected|resulted|generated|incurred|completed|reduced|expanded|contracted|narrowed|widened|limited|drove|offset)\b")
YEAR = re.compile(r"\b(?:fiscal |fy ?)?((?:19|20)\d\d)\b")


def temporal_class(quote: str | None) -> str:
    """HISTORICAL_FACT: states what happened (past-tense result words, no
    expectation words), or a bare figure. FORWARD_LOOKING: only expectation
    words. MIXED_OR_UNCLEAR: both. Sentence-level, from the key quote only."""
    t = " ".join((quote or "").lower().split())
    fwd, hist = bool(FORWARD.search(t)), bool(HISTORICAL.search(t))
    if fwd and not hist:
        return "FORWARD_LOOKING"
    if fwd and hist:
        return "MIXED_OR_UNCLEAR"
    return "HISTORICAL_FACT"


def quote_years(quote: str | None) -> list[int]:
    return sorted({int(y) for y in YEAR.findall((quote or "").lower())})


def _numeric_window(unit, ledger) -> dict | None:
    """Window of an A2 numeric-verifier value ('<Metric> <measure> <basis> @ <end>'):
    the start of the same-end XBRL facts it was computed from, which the
    verifier registered in the same ledger. None when that provenance is not there."""
    m = re.match(r"^(\w+) (\w+) (quarter|annual|instant) @ (\d{4}-\d{2}-\d{2})$", unit.locator or "")
    if not m or ledger is None:
        return None
    from engine.numeric import RATIOS
    metric, basis, end = m.group(1), m.group(3), m.group(4)
    parts = list(RATIOS.get(metric, (metric,)))
    if basis == "instant":
        found = [u for u in ledger.units.values() if u.kind == "xbrl_fact" and (u.locator or "").split(" ")[0] in parts and _close(u.period_end, end)]
        return {"kind": "instant", "start": None, "end": end, "months": [0], "source": "numeric_derivation",
                "provenance": [u.evidence_id for u in found]} if found else None
    starts = {}
    for u in ledger.units.values():
        if u.kind == "xbrl_fact" and (u.locator or "").split(" ")[0] in parts and u.period_start and _close(u.period_end, end):
            starts.setdefault((u.locator or "").split(" ")[0], set()).add(u.period_start)
    if set(starts) != set(parts) or len({s for v in starts.values() for s in v}) != 1:
        return None  # a component is missing, or the components disagree on the window
    start = next(iter(starts[parts[0]]))
    months = _months(start, end)
    if months != {"quarter": 3, "annual": 12}[basis]:
        return None
    return {"kind": "duration", "start": start, "end": end, "months": [months], "source": "numeric_derivation", "provenance": sorted(parts)}


def _markers(text: str) -> list[tuple[int, str]]:
    t = " ".join((text or "").lower().split())
    out = []
    for pat, months, name in MARKERS:
        if pat.search(t):
            out.append((months, name))
    if any(n == "TTM" for _, n in out):  # "trailing twelve months" also matches "twelve months ended"
        out = [x for x in out if x[1] != "TWELVE_MONTHS"]
    return out


def evidence_period(unit, quote: str | None = None, claim_period: dict | None = None, ledger=None) -> dict:
    """Period of one evidence unit. XBRL facts carry their own window; a
    passage is dated by its filing and given a duration by period words in
    the key quote, then the passage, then the filing's default."""
    if unit is None:
        return {"kind": None, "source": "missing"}
    derived = unit.kind == "derived_metric" and (unit.locator or "").startswith(DERIVATION_PREFIX)
    v11 = bool(claim_period) and claim_period.get("version") == PERIODS_VERSION_V11
    if v11 and unit.kind == "derived_metric" and not derived and not unit.period_start:
        w = _numeric_window(unit, ledger)
        return w or {"kind": None, "end": unit.period_end, "source": "derived_without_verified_provenance"}
    if unit.kind in ("xbrl_fact", "derived_metric"):
        if not unit.period_end:
            return {"kind": None, "source": "no_period"}
        if not unit.period_start or unit.period_start == unit.period_end:
            if unit.kind == "derived_metric" and not derived:
                return {"kind": None, "end": unit.period_end, "source": "derived_without_window"}
            return {"kind": "instant", "start": None, "end": unit.period_end, "months": [0], "source": "xbrl"}
        return {"kind": "duration", "start": unit.period_start, "end": unit.period_end,
                "months": [_months(unit.period_start, unit.period_end)], "source": "derivation" if derived else "xbrl"}
    if unit.kind != "filing_passage" or not unit.period_end:
        return {"kind": None, "source": "not_dated"}
    if claim_period and claim_period.get("kind") == "instant":
        return {"kind": "instant", "start": None, "end": unit.period_end, "months": [0], "source": "filing_report_date"}
    years = quote_years(quote) if v11 else []
    for scope, text in (("quote", quote), ("passage", unit.excerpt)):
        mk = _markers(text) if text else []
        if mk:
            return {"kind": "duration", "start": None, "end": unit.period_end, "months": sorted({m for m, _ in mk}),
                    "markers": [n for _, n in mk], "source": f"{scope}_marker", "form": unit.form, "quote_years": years}
    if (unit.form or "").startswith("10-K"):
        return {"kind": "duration", "start": None, "end": unit.period_end, "months": [12], "markers": [], "source": "filing_default_10K",
                "form": unit.form, "quote_years": years}
    return {"kind": None, "end": unit.period_end, "markers": [], "source": "10Q_passage_without_period_words", "form": unit.form}


def compatibility(claim_period: dict, ev: dict) -> dict:
    """{'status', 'role', 'reason'} for one evidence period against the claim's."""
    def out(status, reason, role=None):
        return {"status": status, "role": role, "reason": reason}
    if not claim_period or not claim_period.get("kind"):
        return out("UNKNOWN", "CLAIM_PERIOD_UNKNOWN")
    if not ev.get("kind"):
        return out("UNKNOWN", "EVIDENCE_PERIOD_UNKNOWN:" + ev.get("source", "?"))
    if claim_period.get("version") == PERIODS_VERSION_V11 and ev.get("quote_years"):
        # a statement names its own years: it must name one the claim (or its comparison) covers
        if not set(ev["quote_years"]) & set(claim_period.get("years") or []):
            return out("MISMATCH", "QUOTE_REFERS_TO_OTHER_YEAR:" + "/".join(str(y) for y in ev["quote_years"]))
    role = "current" if _close(ev["end"], claim_period["end"]) else ("comparison" if _close(ev["end"], claim_period["comparison"]["end"]) else None)
    if claim_period["kind"] == "instant":
        if ev["kind"] != "instant":
            return out("MISMATCH", "DURATION_EVIDENCE_FOR_A_BALANCE_CLAIM")
        return out("EXACT_MATCH", "SAME_DATE", role) if role else out("MISMATCH", "OTHER_DATE")
    if ev["kind"] == "instant":
        return out("MISMATCH", "BALANCE_EVIDENCE_FOR_A_DURATION_CLAIM")
    if role is None:
        return out("MISMATCH", "OTHER_PERIOD_END")
    want = claim_period["months"]
    months = ev.get("months") or []
    if ev.get("start"):  # exact window
        ws = claim_period["start"] if role == "current" else claim_period["comparison"]["start"]
        same = _close(ev["start"], ws) and months == [want]
        if not same:
            return out("MISMATCH", f"DURATION_DIFFERS:{months[0]}M_vs_{want}M" if months and months[0] != want else "WINDOW_START_DIFFERS")
        return out("COMPATIBLE_AFTER_VERIFIED_DERIVATION" if ev["source"] in ("derivation", "numeric_derivation") else "EXACT_MATCH",
                   "SAME_WINDOW", role)
    if "TTM" in (ev.get("markers") or []) and want == 12 and not _close(claim_period["end"], ev["end"]):
        return out("MISMATCH", "TTM_IS_NOT_THE_FISCAL_YEAR")
    if "TTM" in (ev.get("markers") or []) and want != 12:
        return out("MISMATCH", f"TTM_vs_{want}M")
    if want not in months:
        return out("MISMATCH", f"DURATION_DIFFERS:{'/'.join(str(m) for m in months)}M_vs_{want}M")
    if ev["source"] == "passage_marker" and len(months) > 1:
        return out("UNKNOWN", "PASSAGE_STATES_SEVERAL_DURATIONS")  # the key quote must name the period
    return out("EXACT_MATCH", "SAME_END_AND_DURATION", role)


def is_decisive(status: str) -> bool:
    return status in ("EXACT_MATCH", "COMPATIBLE_AFTER_VERIFIED_DERIVATION")


# ------------------------------------------------------------ derivations

def derive_for_claim(ledger, claim, period: dict, metric: str) -> list[dict]:
    """Facts for the claim's window (and its prior-year comparison) that no
    retrieved unit states directly: a filed fact with exactly that window
    (e.g. a six-month YTD cash flow), else the sum of filed single-quarter
    facts covering it. Flow metrics only; ratios are not additive. Each result
    is registered as a derived_metric unit with its formula and source facts."""
    from engine.numeric import FLOW_TAGS, _facts
    from evidence_ledger import EvidenceUnit  # noqa: E402
    if metric not in FLOW_TAGS or period.get("kind") != "duration" or period["months"] in (None, 0):
        return []
    cut = claim.as_of_date
    out = []
    for role, (start, end) in (("current", (period["start"], period["end"])),
                               ("comparison", (period["comparison"]["start"], period["comparison"]["end"]))):
        if not start or not end:
            continue
        direct = _direct_fact(claim.company, metric, start, end, cut)
        if direct:
            inputs, formula, value = [direct], f"{metric}[{direct['period_start']}..{direct['period_end']}] (filed fact)", direct["value"]
        elif period["months"] % 3 == 0 and period["months"] > 3:
            qs = sorted((f for f in _facts(claim.company, metric, "quarter", cut)
                         if _d(start) - timedelta(days=TOL) <= _d(f["period_start"]) and _d(f["period_end"]) <= _d(end) + timedelta(days=TOL)),
                        key=lambda f: (f["period_end"], f["filed"]))
            latest = {}
            for f in qs:
                latest[f["period_end"]] = f
            qs = list(latest.values())
            if len(qs) != period["months"] // 3 or not _close(qs[0]["period_start"], start) or not _close(qs[-1]["period_end"], end):
                continue
            inputs, value = qs, sum(f["value"] for f in qs)
            formula = " + ".join(f"{metric}[{f['period_start']}..{f['period_end']}]" for f in qs)
        else:
            continue
        excerpt = (f"{metric} for {start}..{end} = {value:,.0f} ({formula}); source facts: "
                   + "; ".join(f"{f['period_start']}..{f['period_end']} {f['value']:,.0f} ({f['form']} {f['accession_number']} filed {f['filed']})" for f in inputs))
        eid = ledger.add(EvidenceUnit(kind="derived_metric", ticker=claim.company, source="a3v2 period derivation over SEC XBRL facts",
                                      accession_number=inputs[-1]["accession_number"], form=inputs[-1]["form"],
                                      filed=max(f["filed"] for f in inputs), period_start=start, period_end=end,
                                      locator=f"{DERIVATION_PREFIX} {metric} {start}..{end} ({PERIODS_VERSION})",
                                      excerpt=excerpt, values=[value], unit=inputs[0].get("unit") or "USD"))
        out.append({"evidence_id": eid, "metric": metric, "role": role, "start": start, "end": end, "value": value, "formula": formula,
                    "inputs": [{k: f[k] for k in ("period_start", "period_end", "value", "accession_number", "form", "filed")} for f in inputs]})
    return out


def _direct_fact(ticker: str, metric: str, start: str, end: str, cutoff: str) -> dict | None:
    from engine.numeric import FLOW_TAGS
    try:
        with open(facts_path(ticker)) as f:
            fj = json.load(f)
    except (OSError, ValueError):
        return None
    best = None
    for tag in FLOW_TAGS[metric]:
        for unit, vals in (fj.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units") or {}).items():
            for v in vals:
                if not v.get("start") or v.get("form") not in ("10-Q", "10-K") or not v.get("filed") or v["filed"] > cutoff:
                    continue
                if _close(v["start"], start) and _close(v["end"], end) and (best is None or v["filed"] > best["filed"]):
                    best = {"period_start": v["start"], "period_end": v["end"], "value": v["val"], "accession_number": v["accn"],
                            "form": v["form"], "filed": v["filed"], "unit": unit, "tag": tag}
        if best:
            return best
    return None
