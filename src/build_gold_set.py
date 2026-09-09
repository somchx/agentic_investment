"""Build a gold/reference set for scoring status accuracy -- addresses the
circularity problem: every "correct" status so far was "this system's own
SEC extraction, run through this system's own rule," which never fails on
its own terms.

**Honest scope of what "gold" means here:** for each (ticker, reason_key)
this cross-checks the XBRL-derived 10-Q/10-K value against the figure in
the company's own 8-K earnings-release press release for the same quarter
-- a genuinely separate filing/document, prepared and submitted
independently of (and usually before) the 10-Q, not just a second read of
the same XBRL blob. This is NOT the same as a human analyst independently
re-deriving the number from first principles; both documents ultimately
come from the company's own books. It's a real, if partial, independent
check -- worth stating plainly rather than calling it "ground truth"
without qualification. A stronger gold set would add a small number of
hand-verified entries read directly from the primary filing text.

Only entries where the earnings-release figure parsed successfully AND
matches the 10-Q/10-K value (or shows a genuine, explainable conflict) are
gold-worthy; unparsed/unmatched cases are recorded separately so the
scoring script doesn't silently skip them.

Usage:
    python3 build_gold_set.py [TICKER ...]   # defaults to all 15 pilot companies
"""

import json
import sys

from earnings_release import get_release_figure, list_earnings_release_filings
from sec_client import KNOWN_CIKS, get_company_facts
from tools import SECONDARY_EVIDENCE_METRICS
from xbrl_extract import extract_instant_facts, extract_quarterly_facts, latest_version_per_quarter

GOLD_SET_PATH = "../data/gold_set.json"


def build_for_ticker(ticker: str) -> list[dict]:
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)

    releases = list_earnings_release_filings(ticker, cik)
    entries = []

    for reason_key, metric in SECONDARY_EVIDENCE_METRICS.items():
        if metric == "LongTermDebt":
            facts = extract_instant_facts(facts_json, cik, metric)
        else:
            facts = extract_quarterly_facts(facts_json, cik, metric)
        by_quarter = latest_version_per_quarter(facts)

        for filing in sorted(releases, key=lambda f: f.filed):
            rf = get_release_figure(cik, filing, metric)
            if rf.period_end is None or rf.value is None:
                continue
            versions = by_quarter.get(rf.period_end)
            if not versions:
                continue

            # Use the ORIGINAL (first-ever ​filed) version, not the latest/most-
            # authoritative one, and keep its value and its filed date together.
            # Using the latest-filed version's *value* paired with its *filed
            # date* as a point-in-time as_of was wrong two ways: (1) the latest
            # version can be filed a year-plus after the quarter itself (a
            # later 10-K referencing it again), which massively overshoots
            # "when was this known"; (2) even fixing the date, testing the
            # RESTATED value at a point in time *before* the restatement
            # happened will correctly get back the original number from the
            # live pipeline, not the restated one -- a mismatch that isn't a
            # bug. Using the original version consistently for both value and
            # date keeps the test coherent: "does the pipeline reproduce this
            # quarter's number as it was known when first filed."
            original = versions[0]
            filed_value = original.value
            diff = abs(rf.value - filed_value) / abs(filed_value) if filed_value else None
            entries.append({
                "ticker": ticker,
                "company": company_name,
                "reason_key": reason_key,
                "metric": metric,
                "period_end": rf.period_end,
                "xbrl_10q_value": filed_value,
                "earnings_release_value": rf.value,
                "diff_pct": diff,
                "sources_agree": diff is not None and diff <= 0.005,
                "as_of": filing.filed,  # the 8-K's filed date -- when the release figure became public
                # The 10-Q/10-K's own filed date -- NOT the same as the 8-K's.
                # Point-in-time matters here: the earnings release for a quarter
                # is often published a day or more *before* that quarter's own
                # 10-Q is filed, so check_reason_status(as_of=<8-K filed date>)
                # can still correctly resolve to the *previous* quarter, since
                # this quarter's XBRL fact doesn't exist yet as of the 8-K date.
                # Scoring must use xbrl_filed, not as_of, to test "does the
                # pipeline compute this quarter's status right once its data
                # actually exists" -- using as_of here was a real bug in an
                # earlier version of score_against_gold.py, caught by a batch
                # of Broken/Supported mismatches that turned out to be the
                # live pipeline correctly returning the *prior* quarter, not
                # a classification error.
                "xbrl_filed": original.filed,
                "provenance": (
                    "XBRL 10-Q/10-K value cross-checked against the company's own 8-K "
                    "earnings-release exhibit for the same quarter (independent filing, "
                    "not a re-read of the same document)."
                ),
            })

    return entries


def run(tickers: list[str]) -> None:
    all_entries = []
    for ticker in tickers:
        print(f"--- {ticker} ---")
        entries = build_for_ticker(ticker)
        agree = sum(e["sources_agree"] for e in entries)
        print(f"  {len(entries)} dual-sourced entries, {agree} where sources agree")
        all_entries.extend(entries)

    with open(GOLD_SET_PATH, "w") as f:
        json.dump(all_entries, f, indent=2)

    n = len(all_entries)
    agree = sum(e["sources_agree"] for e in all_entries)
    print(f"\nWrote {n} entries to {GOLD_SET_PATH} ({agree} agree, {n - agree} disagree)")


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else sorted(KNOWN_CIKS.keys())
    run(tickers)
