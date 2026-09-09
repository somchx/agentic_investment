"""Run both agent.py planners (deterministic rule-based vs LLM-driven) across
the same company set and compare their verdicts -- the experiment design
from PROPOSAL.md section 9: does the LLM's tool-selection match or improve
on the rule-based planner's, not just "does it sound smart".

Compares per-reason (not just per-company) now that both planners return
structured output -- see tools.py's FINALIZE_REPORT_TOOL. An earlier version
of this script text-matched the LLM's free-text summary for phrases like
"recommended", which silently misread a report that said "Human Review
Needed: **YES**" as a "no review needed" verdict. Fixed by forcing the LLM
to call finalize_report with structured booleans instead of writing prose
this script then had to reverse-engineer.

Usage:
    python3 compare_planners.py [TICKER ...]
"""

import sys
import time

from agent import run_rule_based, run_with_llm

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "PEP", "JNJ", "PG",
    "KO", "WMT", "NFLX", "ORCL", "COST",
]


def extra_calls(trace: list[str]) -> int:
    return sum(1 for line in trace if "get_secondary_evidence" in line)


def run(tickers: list[str]) -> None:
    total_input_tokens = 0
    total_output_tokens = 0
    per_reason_rows = []

    for ticker in tickers:
        print(f"--- {ticker} ---")
        rb_report = run_rule_based(ticker)
        rb_by_key = {r["reason_key"]: r for r in rb_report["reasons"] if "error" not in r}

        try:
            llm_result = run_with_llm(ticker)
        except Exception as e:  # noqa: BLE001 -- report the failure, keep going
            print(f"  LLM run failed for {ticker}: {e}")
            continue

        total_input_tokens += llm_result["usage"]["input_tokens"]
        total_output_tokens += llm_result["usage"]["output_tokens"]
        llm_by_key = {r["reason_key"]: r for r in llm_result["reasons"]}

        rb_extra = extra_calls(rb_report["trace"])
        llm_extra = extra_calls(llm_result["trace"])

        for key in rb_by_key:
            if key not in llm_by_key:
                continue
            rb_r, llm_r = rb_by_key[key], llm_by_key[key]
            status_agree = rb_r["status"] == llm_r["status"]
            review_agree = rb_r["human_review_recommended"] == llm_r["human_review_recommended"]
            per_reason_rows.append({
                "ticker": ticker,
                "reason_key": key,
                "rb_status": rb_r["status"],
                "llm_status": llm_r["status"],
                "status_agree": status_agree,
                "rb_review": rb_r["human_review_recommended"],
                "llm_review": llm_r["human_review_recommended"],
                "review_agree": review_agree,
            })
            flag = "" if (status_agree and review_agree) else "  <-- DISAGREE"
            print(
                f"  [{key}] rb={rb_r['status']}/{rb_r['human_review_recommended']}  "
                f"llm={llm_r['status']}/{llm_r['human_review_recommended']}{flag}"
            )
        print(f"  (extra tool calls: rule_based={rb_extra}, llm={llm_extra})")
        time.sleep(0.5)  # be polite to the API

    print("\n" + "=" * 100)
    print(f"{'Ticker':<8}{'Reason':<18}{'RB status':<14}{'LLM status':<14}{'RB rev':<8}{'LLM rev':<8}{'Agree':<8}")
    for r in per_reason_rows:
        agree = r["status_agree"] and r["review_agree"]
        print(
            f"{r['ticker']:<8}{r['reason_key']:<18}{r['rb_status']:<14}{r['llm_status']:<14}"
            f"{str(r['rb_review']):<8}{str(r['llm_review']):<8}{str(agree):<8}"
        )

    n = len(per_reason_rows)
    status_agreement = sum(r["status_agree"] for r in per_reason_rows) / n if n else 0
    review_agreement = sum(r["review_agree"] for r in per_reason_rows) / n if n else 0
    est_cost = total_input_tokens / 1e6 * 3 + total_output_tokens / 1e6 * 15
    print("=" * 100)
    print(f"Per-reason comparisons: {n}")
    print(f"Status agreement (Supported/Weakened/Broken/Not enough data): {status_agreement:.0%}")
    print(f"Human-review-recommended agreement: {review_agreement:.0%}")
    print(
        f"Total LLM usage: {total_input_tokens} input tokens, {total_output_tokens} output tokens "
        f"(~${est_cost:.3f} at $3/$15 per MTok)"
    )

    disagreements = [r for r in per_reason_rows if not (r["status_agree"] and r["review_agree"])]
    if disagreements:
        print(f"\n{len(disagreements)} disagreement(s):")
        for r in disagreements:
            print(
                f"  {r['ticker']} [{r['reason_key']}]: "
                f"rule_based={r['rb_status']}/review={r['rb_review']}  "
                f"llm={r['llm_status']}/review={r['llm_review']}"
            )


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TICKERS
    run(tickers)
