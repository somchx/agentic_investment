"""Run-to-run consistency experiment: repeat agent.run_with_llm on the same
ticker multiple times and measure how often tool selection, per-reason
status, and the human-review verdict actually vary on identical input.

Scoped to the 9 tickers whose reference status includes at least one
non-Supported reason (GOOGL, AMZN, META, TSLA, PEP, JNJ, PG, WMT, COST) --
that's where a judgment call is actually being exercised; repeating a
clean all-Supported ticker mostly just re-confirms it says Supported every
time, which doesn't test consistency of *judgment*, just of arithmetic
(already known to be deterministic).

The PG case found earlier this session (same input, different human-review
verdict on the Weakened revenue-growth reason across two runs) was found
by accident while fixing an unrelated bug -- this is the systematic version
of that check.

Real, budgeted run. Usage:
    python3 run_consistency_experiment.py [N_REPS]
"""

import json
import sys
from collections import Counter

from agent import run_with_llm

TICKERS = ["GOOGL", "AMZN", "META", "TSLA", "PEP", "JNJ", "PG", "WMT", "COST"]
DEFAULT_REPS = 7
OUT_PATH = "../data/consistency_experiment_results.json"
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0


def tool_signature(trace: list[str]) -> tuple:
    """Which tools were called, ignoring order and exact args -- e.g.
    ("check_reason_status", "get_secondary_evidence", "get_filing_context")
    vs a run that skipped the filing-context investigation. This is what
    "tool selection consistency" means here: did the agent choose to
    investigate the same way each time.
    """
    names = []
    for line in trace:
        for tool in ("check_reason_status", "get_secondary_evidence", "get_filing_context"):
            if line.startswith(f"LLM called {tool}("):
                names.append(tool)
    return tuple(sorted(Counter(names).items()))


def run(n_reps: int = DEFAULT_REPS) -> None:
    total_input, total_output = 0, 0
    all_runs = {}  # ticker -> list of run results

    for ticker in TICKERS:
        print(f"--- {ticker} ---")
        runs = []
        for i in range(n_reps):
            result = run_with_llm(ticker)
            total_input += result["usage"]["input_tokens"]
            total_output += result["usage"]["output_tokens"]
            runs.append({
                "reasons": {r["reason_key"]: {"status": r["status"], "human_review_recommended": r["human_review_recommended"]}
                            for r in result["reasons"]},
                "tool_signature": tool_signature(result["trace"]),
            })
            print(f"  run {i+1}/{n_reps}: "
                  f"{ {k: v['status'] for k, v in runs[-1]['reasons'].items()} } "
                  f"tools={runs[-1]['tool_signature']}")
        all_runs[ticker] = runs

    with open(OUT_PATH, "w") as f:
        json.dump({
            "tickers": TICKERS, "n_reps": n_reps, "runs": all_runs,
            "usage": {"input_tokens": total_input, "output_tokens": total_output},
        }, f, indent=2)

    print("\n" + "=" * 100)
    print(f"{'Ticker':<8}{'Reason':<18}{'Status modes':<10}{'Status agree%':<16}{'Review modes':<14}{'Review agree%':<14}")

    status_agreements, review_agreements, tool_agreements = [], [], []
    for ticker, runs in all_runs.items():
        reason_keys = runs[0]["reasons"].keys()
        for reason_key in reason_keys:
            statuses = [r["reasons"][reason_key]["status"] for r in runs]
            reviews = [r["reasons"][reason_key]["human_review_recommended"] for r in runs]
            status_mode_count = Counter(statuses).most_common(1)[0][1]
            review_mode_count = Counter(reviews).most_common(1)[0][1]
            status_agree = status_mode_count / len(statuses)
            review_agree = review_mode_count / len(reviews)
            status_agreements.append(status_agree)
            review_agreements.append(review_agree)
            print(f"{ticker:<8}{reason_key:<18}{len(set(statuses)):<10}{status_agree:<16.0%}"
                  f"{len(set(reviews)):<14}{review_agree:<14.0%}")

        tool_sigs = [r["tool_signature"] for r in runs]
        tool_mode_count = Counter(tool_sigs).most_common(1)[0][1]
        tool_agreements.append(tool_mode_count / len(tool_sigs))
        print(f"{ticker:<8}{'(tool selection)':<18}{len(set(tool_sigs)):<10}{tool_mode_count/len(tool_sigs):<16.0%}")

    print("=" * 100)
    print(f"Mean status agreement (mode share) across all {len(status_agreements)} reason-checks: "
          f"{sum(status_agreements)/len(status_agreements):.1%}")
    print(f"Mean human-review-verdict agreement: {sum(review_agreements)/len(review_agreements):.1%}")
    print(f"Mean tool-selection agreement across {len(tool_agreements)} tickers: "
          f"{sum(tool_agreements)/len(tool_agreements):.1%}")

    cost = total_input / 1e6 * COST_PER_M_INPUT + total_output / 1e6 * COST_PER_M_OUTPUT
    print(f"\nTotal cost: ${cost:.3f} ({len(TICKERS) * n_reps} calls, "
          f"{total_input} input + {total_output} output tokens)")


if __name__ == "__main__":
    n_reps = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPS
    run(n_reps)
