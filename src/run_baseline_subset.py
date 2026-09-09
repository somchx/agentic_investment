"""Real, budgeted run of all three approaches (baseline1, baseline2,
agent.run_with_llm) across a small subset -- the first 5 pilot companies --
before committing to the full 15-company x 3-reason run. Reports each
approach's verdict side by side plus total cost.

Usage:
    python3 run_baseline_subset.py
"""

from agent import run_with_llm
from baseline1 import run_baseline1
from baseline2 import run_baseline2
from tools import REASON_DEFS

SUBSET_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0


def cost(usage: dict) -> float:
    return usage["input_tokens"] / 1e6 * COST_PER_M_INPUT + usage["output_tokens"] / 1e6 * COST_PER_M_OUTPUT


def run() -> None:
    total_input, total_output = 0, 0
    rows = []

    for ticker in SUBSET_TICKERS:
        print(f"--- {ticker} ---")
        agent_result = run_with_llm(ticker)
        total_input += agent_result["usage"]["input_tokens"]
        total_output += agent_result["usage"]["output_tokens"]
        agent_by_key = {r["reason_key"]: r for r in agent_result["reasons"]}

        for reason_key in REASON_DEFS:
            b1 = run_baseline1(ticker, reason_key)
            total_input += b1["usage"]["input_tokens"]
            total_output += b1["usage"]["output_tokens"]

            b2 = run_baseline2(ticker, reason_key)
            total_input += b2["usage"]["input_tokens"]
            total_output += b2["usage"]["output_tokens"]

            agent_r = agent_by_key.get(reason_key, {})
            row = {
                "ticker": ticker,
                "reason_key": reason_key,
                "baseline1_status": b1["status"],
                "baseline2_status": b2["status"],
                "agent_status": agent_r.get("status", "?"),
                "retrieved_status": b2["retrieved"].get("status", "?"),
            }
            rows.append(row)
            print(
                f"  [{reason_key}] baseline1={b1['status']:<16} baseline2={b2['status']:<16} "
                f"agent={row['agent_status']:<16} (actual/retrieved={row['retrieved_status']})"
            )

    print("\n" + "=" * 100)
    print(f"{'Ticker':<8}{'Reason':<18}{'Baseline1':<16}{'Baseline2':<16}{'Agent':<16}{'Retrieved(truth)':<16}")
    for r in rows:
        print(
            f"{r['ticker']:<8}{r['reason_key']:<18}{r['baseline1_status']:<16}"
            f"{r['baseline2_status']:<16}{r['agent_status']:<16}{r['retrieved_status']:<16}"
        )

    b1_correct = sum(1 for r in rows if r["baseline1_status"] == r["retrieved_status"])
    b2_correct = sum(1 for r in rows if r["baseline2_status"] == r["retrieved_status"])
    agent_correct = sum(1 for r in rows if r["agent_status"] == r["retrieved_status"])
    n = len(rows)
    print("=" * 100)
    print(f"Agreement with retrieved (point-in-time-correct) status, out of {n}:")
    print(f"  baseline1 (parametric only): {b1_correct}/{n} ({b1_correct/n:.0%})")
    print(f"  baseline2 (single-shot RAG): {b2_correct}/{n} ({b2_correct/n:.0%})")
    print(f"  agent (tool-using, this project): {agent_correct}/{n} ({agent_correct/n:.0%})")

    total_cost = cost({"input_tokens": total_input, "output_tokens": total_output})
    print(f"\nTotal usage: {total_input} input tokens, {total_output} output tokens")
    print(f"Total cost: ${total_cost:.3f}")


if __name__ == "__main__":
    run()
