"""Contribution 2, real conflict source: preliminary 8-K earnings-release
numbers vs the final numbers in the 10-Q/10-K filed shortly after.

Earnings press releases (SEC Item 2.02 8-Ks) are not part of the XBRL
company-facts feed used elsewhere in this project, so they need to be
located and text-parsed separately:

  1. list the company's 8-K filings that report "Results of Operations"
     (Item 2.02) via the submissions API
  2. find the EX-99.1 exhibit (the actual press release) inside each filing
  3. parse the headline Revenue / Operating Income figures out of the
     "Condensed Consolidated Statements of Operations" table
  4. compare against the corresponding Fact already extracted from the 10-Q
     via xbrl_extract.py

This gives the Agent a second, independently-sourced number for the same
quarter -- exactly the kind of dual-sourced evidence Contribution 2 needs to
have anything to reconcile. Whether the two numbers actually differ in
practice is an empirical question this module is built to answer, not
assume.
"""

import re
from dataclasses import dataclass
from datetime import date

from sec_client import get_document_text, get_filing_index_html, get_submissions

MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

# Keyword(s) to look for on the income-statement line for each metric, in
# priority order (press releases vary in wording between companies).
METRIC_KEYWORDS = {
    "Revenue": ["Total net sales", "Net sales", "Total revenue", "Net revenues", "Revenue"],
    "OperatingIncome": ["Operating income", "Income from operations"],
    "LongTermDebt": ["Term debt", "Long-term debt", "Long term debt"],
}

# LongTermDebt lives in the balance sheet, not the income statement -- it
# needs a different date anchor ("... BALANCE SHEETS ... <date1> <date2>",
# not "Three Months Ended <date>"), and the same line item usually appears
# twice (the current portion under current liabilities, then the
# non-current portion under non-current liabilities -- confirmed against
# Apple's Q2 FY2026 release: "Term debt 8,310 12,350" under current
# liabilities, "Term debt 74,404 78,328" under non-current; the extracted
# XBRL LongTermDebt fact for the same period was $74,404M, matching the
# *second* occurrence, not the first).
INSTANT_METRICS = {"LongTermDebt"}


@dataclass(frozen=True)
class EarningsReleaseFiling:
    accession_number: str
    filed: str  # date the 8-K itself was filed -- when this number became public
    exhibit_filename: str


@dataclass(frozen=True)
class ReleaseFigure:
    metric: str
    period_end: str | None  # None if no quarter-end date could be tied to the matched value
    value: float | None  # None if the metric wasn't found in the exhibit text
    filing: EarningsReleaseFiling


def list_earnings_release_filings(ticker: str, cik: str) -> list[EarningsReleaseFiling]:
    """Every 8-K filing tagged with Item 2.02 (Results of Operations)."""
    submissions = get_submissions(ticker)
    recent = submissions["filings"]["recent"]

    out = []
    for form, accn, filed, items in zip(
        recent["form"], recent["accessionNumber"], recent["filingDate"], recent["items"]
    ):
        if form != "8-K" or "2.02" not in items:
            continue
        exhibit = _find_ex99_filename(cik, accn)
        if exhibit:
            out.append(EarningsReleaseFiling(accn, filed, exhibit))
    return out


def _find_ex99_filename(cik: str, accession_number: str) -> str | None:
    html = get_filing_index_html(cik, accession_number)
    rows = re.findall(r"<tr.*?</tr>", html, re.S)
    for row in rows:
        if re.search(r"EX-99\.?1", row, re.I):
            clean = re.sub(r"<[^>]+>", " ", row)
            match = re.search(r"(\S+\.htm)", clean)
            if match:
                return match.group(1)
    return None


def _clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&#160;", " ").replace("&nbsp;", " ").replace("&#8217;", "'")
    text = re.sub(r"\s+", " ", text)
    return text


def _find_value_match(text: str, metric: str) -> re.Match | None:
    """Find the number after the metric's keyword — the "current quarter"
    (or current balance-sheet date) column in a multi-column table row.

    Requires a comma-grouped number (e.g. "124,300") rather than any digit
    run, so footnote markers like the "(1)" right after "Total net sales (1)"
    in Apple's table don't get matched as the value.

    For instant metrics (LongTermDebt), the keyword's line appears twice
    (current portion, then non-current portion) -- the *last* match is the
    non-current figure that corresponds to the XBRL LongTermDebt fact this
    is compared against; for duration metrics the first match is correct.
    """
    for keyword in METRIC_KEYWORDS[metric]:
        pattern = re.escape(keyword) + r"\D{0,20}?\$?\s*\(?(\d{1,3}(?:,\d{3})+)\)?"
        matches = list(re.finditer(pattern, text))
        if not matches:
            continue
        return matches[-1] if metric in INSTANT_METRICS else matches[0]
    return None


def _parse_date_in_window(window: str) -> str | None:
    day_match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),", window)
    if not day_match:
        return None
    month = MONTHS.get(day_match.group(1))
    if not month:
        return None

    year_match = re.search(r"\b(20\d{2})\b", window[day_match.end():])
    if not year_match:
        return None

    return date(int(year_match.group(1)), month, int(day_match.group(2))).isoformat()


def _detect_unit_multiplier(text: str, value_start: int) -> float:
    """Figure out whether the matched number is reported in thousands or
    millions -- companies aren't consistent. Apple/Microsoft state
    "(In millions...)"; Netflix's income statement is explicitly
    "(in thousands...)" even though other sections of the same release say
    "(in millions)" (referring to subscriber counts, not dollars). Assuming
    millions unconditionally silently inflated every NFLX dollar figure
    parsed here by 1000x -- caught by comparing against the XBRL 10-Q value
    in build_gold_set.py, where the two numbers matched digit-for-digit but
    differed by exactly 3 orders of magnitude.

    Finds the nearest "(in thousands...)" / "(In millions...)" table-header
    annotation *before* the matched value; defaults to millions (the more
    common case in this project's pilot set) if none is found nearby.

    Must anchor on the parenthetical right after "(" -- a bare substring
    search for "in thousands" also matches Apple's header "(In millions,
    except number of shares which are reflected **in thousands** and per
    share amounts)", which is describing the share count, not the dollar
    unit, and picking whichever phrase happens to sit closer to the value
    silently chose the wrong one for every Apple entry.
    """
    preceding = text[max(0, value_start - 5000): value_start]
    matches = list(re.finditer(r"\(\s*(?:\$\s*)?in\s+(thousands|millions)\b", preceding, re.I))
    if not matches:
        return 1_000_000.0
    return 1_000.0 if matches[-1].group(1).lower() == "thousands" else 1_000_000.0


def _find_period_end_before(text: str, value_start: int) -> str | None:
    """Find the quarter-end date for the table row a matched value sits in.

    Layouts vary: sometimes a date immediately follows "Three Months Ended"
    (e.g. "Three Months Ended June 27, 2015"); sometimes the month/day and
    the year are listed in separate blocks further apart (e.g. Microsoft's
    "Three Months Ended ... December 31, ... 2024 2023 ..."). Anchoring on
    the "Three Months Ended" heading closest before the matched *value*
    (rather than the first one anywhere in the document, which is often an
    unrelated "Constant Currency" summary table) ties the date to the right
    table.
    """
    preceding = text[max(0, value_start - 2000): value_start]
    header_idx = preceding.rfind("Three Months Ended")
    if header_idx == -1:
        return None
    return _parse_date_in_window(preceding[header_idx:])


def _find_balance_sheet_date_before(text: str, value_start: int) -> str | None:
    """Same idea as _find_period_end_before, but for balance-sheet (instant)
    metrics: the anchor is "... BALANCE SHEETS ..." followed immediately by
    two dates (current period-end, then prior fiscal year-end) rather than
    "Three Months Ended <date>" -- the first date is the one that matches.
    """
    preceding = text[max(0, value_start - 3000): value_start]
    header_idx = preceding.rfind("BALANCE SHEET")
    if header_idx == -1:
        return None
    return _parse_date_in_window(preceding[header_idx:])


def get_release_figure(cik: str, filing: EarningsReleaseFiling, metric: str) -> ReleaseFigure:
    html = get_document_text(cik, filing.accession_number, filing.exhibit_filename)
    text = _clean_text(html)

    value_match = _find_value_match(text, metric)
    if not value_match:
        return ReleaseFigure(metric=metric, period_end=None, value=None, filing=filing)

    unit_multiplier = _detect_unit_multiplier(text, value_match.start())
    value = float(value_match.group(1).replace(",", "")) * unit_multiplier
    if metric in INSTANT_METRICS:
        period_end = _find_balance_sheet_date_before(text, value_match.start())
    else:
        period_end = _find_period_end_before(text, value_match.start())

    return ReleaseFigure(metric=metric, period_end=period_end, value=value, filing=filing)
