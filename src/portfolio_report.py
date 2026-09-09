"""Multi-company, multi-reason dashboard -- the scaling step described in
PROPOSAL.md 3.1: 1 company x 3 reasons, then 5 companies. Prints the
"My reasons for investing" style snapshot from the proposal's illustrative
prototype output, as-of the most recent filing available for each company,
plus what changed since the previous quarter's snapshot.

Usage:
    python3 portfolio_report.py [TICKER ...]
"""

import sys

from models import Reason
from reason_engine import evaluate_margin_level, evaluate_yoy_growth
from sec_client import get_company_facts
from xbrl_extract import extract_instant_facts, extract_quarterly_facts

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]

STATUS_ICON = {
    "Supported": "\U0001F7E2",  # green circle
    "Weakened": "\U0001F7E1",  # yellow circle
    "Broken": "\U0001F534",  # red circle
    "Not enough data": "⚪",  # white circle
}


def build_company_reasons(ticker: str):
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)

    revenue_facts = extract_quarterly_facts(facts_json, cik, "Revenue")
    oi_facts = extract_quarterly_facts(facts_json, cik, "OperatingIncome")
    debt_facts = extract_instant_facts(facts_json, cik, "LongTermDebt")

    reasons = [
        (
            Reason("R1", company_name, "Revenue", ">", 0.10, kind="yoy_growth",
                   description="Revenue growth must exceed 10% YoY"),
            revenue_facts, None,
        ),
        (
            Reason("R2", company_name, "OperatingIncome", ">=", 0.20, kind="margin_level",
                   denominator_metric="Revenue",
                   description="Operating margin must stay at or above 20%"),
            oi_facts, revenue_facts,
        ),
        (
            Reason("R3", company_name, "LongTermDebt", "<", 0.15, kind="yoy_growth",
                   description="Long-term debt must not grow more than 15% YoY"),
            debt_facts, None,
        ),
    ]
    return company_name, reasons


def evaluate(reason: Reason, facts, denom_facts, as_of: str):
    if reason.kind == "margin_level":
        return evaluate_margin_level(reason, facts, denom_facts, as_of)
    return evaluate_yoy_growth(reason, facts, as_of)


def run(tickers: list[str]) -> None:
    for ticker in tickers:
        company_name, reasons = build_company_reasons(ticker)

        all_filed_dates = sorted({f.filed for _, facts, _ in reasons for f in facts})
        if len(all_filed_dates) < 2:
            print(f"\n{company_name} ({ticker}): not enough filing history yet.")
            continue
        latest_as_of = all_filed_dates[-1]

        print(f"\n{company_name} ({ticker})")
        print("My reasons for investing")
        print("-" * 70)

        changes = []
        for reason, facts, denom_facts in reasons:
            # Each reason's own "previous" snapshot uses the second-most-recent
            # filed date among *its own* facts, not a global date shared across
            # reasons -- if one reason's data source has stale or missing
            # recent coverage (e.g. a metric a company stopped tagging), that
            # gap shouldn't silently roll every other reason's comparison back
            # to whatever old date that source last has.
            reason_dates = sorted({f.filed for f in facts})
            if len(reason_dates) < 2:
                latest = evaluate(reason, facts, denom_facts, latest_as_of)
                icon = STATUS_ICON[latest.status]
                value_str = f"({latest.computed_value:+.1%})" if latest.computed_value is not None else ""
                print(f"  {icon} {latest.status:<16} {reason.description:<45} {value_str}")
                continue

            reason_latest_as_of = reason_dates[-1]
            reason_previous_as_of = reason_dates[-2]

            latest = evaluate(reason, facts, denom_facts, reason_latest_as_of)
            previous = evaluate(reason, facts, denom_facts, reason_previous_as_of)

            icon = STATUS_ICON[latest.status]
            value_str = f"({latest.computed_value:+.1%})" if latest.computed_value is not None else ""
            print(f"  {icon} {latest.status:<16} {reason.description:<45} {value_str}")

            if previous.status != latest.status:
                changes.append(
                    f"    {reason.description}: {previous.status} -> {latest.status} "
                    f"(as of {reason_previous_as_of} -> {reason_latest_as_of})"
                )

        window_label = f"most recent filing per reason, latest overall {latest_as_of}"
        print(f"\n  What's changed since last review? ({window_label})")
        if changes:
            for c in changes:
                print(c)
        else:
            print("    (no status changes)")

    print()


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TICKERS
    run(tickers)
