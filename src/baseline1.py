"""Baseline 1 (PROPOSAL.md section 9): "LLM answering from parametric
knowledge alone" -- no tools, no retrieval, no data given at all. Claude is
asked to classify one investment reason purely from what it already knows
about the company, with no access to check_reason_status or any other tool.

This is the weakest baseline and is meant to be: it should either (a) be
stale/wrong because its training data doesn't include the specific quarter
being asked about, or (b) correctly abstain ("Not enough data") if it's
honest about not having current information. Comparing its answers against
the gold set (data/gold_set.json, built for free by build_gold_set.py) is
what would actually demonstrate the value of Contribution 1's point-in-time
retrieval, rather than just asserting it.

**NOT RUN in this session -- costs real API budget.** Written and ready;
see README.md for why it's being held back for now (build first, spend
only when the user says so).

Usage (once budget is available):
    python3 baseline1.py TICKER REASON_KEY
"""

import sys

from llm_client import call_claude
from tools import FINALIZE_SINGLE_REASON_TOOL, REASON_DEFS


def run_baseline1(ticker: str, reason_key: str) -> dict:
    if reason_key not in REASON_DEFS:
        raise ValueError(f"unknown reason_key {reason_key!r}, expected one of {list(REASON_DEFS)}")
    reason = REASON_DEFS[reason_key]

    messages = [{
        "role": "user",
        "content": (
            f"Is the following investment reason currently true for {ticker}, based on what "
            f"you already know -- you have no tools, no live data access, and no retrieved "
            f"documents, only your own training knowledge: \"{reason.description}\"\n\n"
            "If you don't have reliable, current information to answer this (e.g. your "
            "knowledge may be out of date for recent quarters), say so honestly and answer "
            "'Not enough data' rather than guessing. Call finalize_answer with your conclusion."
        ),
    }]
    tools = [FINALIZE_SINGLE_REASON_TOOL]

    total_input_tokens = 0
    total_output_tokens = 0
    for _ in range(3):  # small cap -- this should resolve in one turn almost always
        payload = call_claude(messages, tools=tools, max_tokens=512)
        content = payload["content"]
        usage = payload.get("usage", {})
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        messages.append({"role": "assistant", "content": content})

        finalize_call = next((b for b in content if b["type"] == "tool_use" and b["name"] == "finalize_answer"), None)
        if finalize_call:
            return {
                "ticker": ticker,
                "reason_key": reason_key,
                **finalize_call["input"],
                "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            }

        messages.append({
            "role": "user",
            "content": "Please call finalize_answer with your structured conclusion now.",
        })

    raise RuntimeError("baseline1 exceeded its loop cap without reaching finalize_answer")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 baseline1.py TICKER REASON_KEY")
        sys.exit(1)
    result = run_baseline1(sys.argv[1], sys.argv[2])
    print(result)
