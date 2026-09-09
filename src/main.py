"""Phase 1 thin vertical slice runner.

1 company x 1 reason, walked forward through every quarter's filing date,
using only point-in-time data (no lookahead). This is the smallest possible
end-to-end proof that the pipeline works before scaling to more reasons,
then more companies.

Usage:
    cd src && python3 main.py [TICKER]
"""

import sys

from models import Reason
from reason_engine import evaluate_margin_level, evaluate_yoy_growth
from sec_client import get_company_facts
from xbrl_extract import extract_quarterly_facts


def run_operating_margin_slice(ticker: str = "AAPL", threshold: float = 0.20) -> None:
    facts_json = get_company_facts(ticker)
    cik = facts_json.get("cik")
    cik_str = str(cik).zfill(10) if cik else ""
    company_name = facts_json.get("entityName", ticker)

    revenue_facts = extract_quarterly_facts(facts_json, cik_str, "Revenue")
    operating_income_facts = extract_quarterly_facts(facts_json, cik_str, "OperatingIncome")
    if not revenue_facts or not operating_income_facts:
        print(f"Missing Revenue or OperatingIncome facts for {ticker}.")
        return

    reason = Reason(
        reason_id="R2",
        company=company_name,
        metric="OperatingIncome",
        denominator_metric="Revenue",
        comparison=">=",
        threshold=threshold,
        kind="margin_level",
        description=f"Operating margin must stay at or above {threshold:.0%}",
    )

    as_of_dates = sorted({f.filed for f in operating_income_facts})

    print(f"\n{company_name} ({ticker}) — Reason: \"{reason.description}\"")
    print("=" * 100)

    prev_status = None
    for as_of in as_of_dates:
        ev = evaluate_margin_level(reason, operating_income_facts, revenue_facts, as_of)
        if ev.status == "Not enough data":
            continue

        changed = " <-- status changed" if prev_status and ev.status != prev_status else ""
        value_str = f"{ev.computed_value:.1%}" if ev.computed_value is not None else "n/a"
        print(f"[as of {as_of}] status={ev.status:<10} margin={value_str}{changed}")
        print(f"    {ev.explanation}")
        for f in ev.supporting_evidence:
            print(f"    evidence: {f.label()}")
        for f in ev.conflicting_evidence:
            print(f"    conflict: {f.label()}")
        prev_status = ev.status

    print("=" * 100)


def run_revenue_growth_slice(ticker: str = "AAPL") -> None:
    facts_json = get_company_facts(ticker)
    cik = facts_json.get("cik")
    cik_str = str(cik).zfill(10) if cik else ""
    company_name = facts_json.get("entityName", ticker)

    revenue_facts = extract_quarterly_facts(facts_json, cik_str, "Revenue")
    if not revenue_facts:
        print(f"No quarterly revenue facts found for {ticker}.")
        return

    reason = Reason(
        reason_id="R1",
        company=company_name,
        metric="Revenue",
        comparison=">",
        threshold=0.10,
        kind="yoy_growth",
        description="Revenue growth must exceed 10% year-over-year",
    )

    # Walk forward through every distinct filing date so we can see the
    # reason's status evolve exactly as it would have to a real investor.
    as_of_dates = sorted({f.filed for f in revenue_facts})

    print(f"\n{company_name} ({ticker}) — Reason: \"{reason.description}\"")
    print("=" * 100)

    prev_status = None
    for as_of in as_of_dates:
        ev = evaluate_yoy_growth(reason, revenue_facts, as_of)
        if ev.status == "Not enough data":
            continue  # skip the early filings before a YoY comparison exists

        changed = " <-- status changed" if prev_status and ev.status != prev_status else ""
        value_str = f"{ev.computed_value:+.1%}" if ev.computed_value is not None else "n/a"
        print(f"[as of {as_of}] status={ev.status:<10} growth={value_str}{changed}")
        print(f"    {ev.explanation}")
        for f in ev.supporting_evidence:
            print(f"    evidence: {f.label()}")
        for f in ev.conflicting_evidence:
            print(f"    conflict: {f.label()}")
        prev_status = ev.status

    print("=" * 100)


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    run_revenue_growth_slice(ticker)
    run_operating_margin_slice(ticker)
