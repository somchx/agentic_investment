"""Run the earnings-release vs 10-Q comparison across every quarter available,
for one company, and report Match / Conflict / Unparsed for each.

Usage:
    python3 earnings_release_check.py [TICKER]
"""

import sys

from earnings_release import get_release_figure, list_earnings_release_filings
from sec_client import get_company_facts
from xbrl_extract import extract_quarterly_facts, latest_version_per_quarter

TOLERANCE = 0.005  # 0.5%


def run(ticker: str = "AAPL") -> None:
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)

    revenue_facts = extract_quarterly_facts(facts_json, cik, "Revenue")
    revenue_by_quarter = latest_version_per_quarter(revenue_facts)

    releases = list_earnings_release_filings(ticker, cik)
    print(f"\n{company_name} ({ticker}) — {len(releases)} earnings-release 8-Ks found")
    print("=" * 100)

    match, conflict, unparsed, no_filing_match = 0, 0, 0, 0

    for filing in sorted(releases, key=lambda f: f.filed):
        rf = get_release_figure(cik, filing, "Revenue")

        if rf.period_end is None or rf.value is None:
            print(f"[{filing.filed}] accn={filing.accession_number} -> UNPARSED "
                  f"(period_end={rf.period_end}, value={rf.value})")
            unparsed += 1
            continue

        versions = revenue_by_quarter.get(rf.period_end)
        if not versions:
            print(f"[{filing.filed}] period {rf.period_end}: release=${rf.value:,.0f} "
                  f"-> NO MATCHING 10-Q/10-K FACT FOR THIS PERIOD")
            no_filing_match += 1
            continue

        filing_value = versions[-1].value  # most-recently-filed = authoritative
        diff = abs(rf.value - filing_value) / abs(filing_value) if filing_value else None
        is_conflict = diff is not None and diff > TOLERANCE

        status = "CONFLICT" if is_conflict else "match"
        print(
            f"[{filing.filed}] period {rf.period_end}: "
            f"release=${rf.value:,.0f} vs 10-Q/10-K=${filing_value:,.0f} "
            f"(diff={diff:.2%}) -> {status}"
        )
        if is_conflict:
            conflict += 1
        else:
            match += 1

    print("=" * 100)
    print(
        f"Summary: {match} match, {conflict} conflict, "
        f"{unparsed} unparsed, {no_filing_match} no matching filing fact "
        f"(out of {len(releases)} earnings releases checked)"
    )


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run(ticker)
