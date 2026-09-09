"""Baseline 2 (PROPOSAL.md section 9): single-shot RAG -- retrieve once,
stuff into the prompt, answer, no tool-calling loop. This is the "RAG"
tier: Claude gets real retrieved evidence (unlike baseline1), but can't
decide to go get more of it if that evidence looks uncertain or
conflicting, which is exactly what agent.py's run_with_llm (get a second
source when a reason looks uncertain) is meant to improve on.

Retrieval here is real and free: one call to tools.check_reason_status
(the same function the actual agent uses), done by this script directly
rather than left for the model to call -- the model only ever sees the
result as prompt text, never as a callable tool. finalize_answer is the
only tool offered, purely to get structured output instead of parsing
prose (see tools.py's FINALIZE_SINGLE_REASON_TOOL for why).

**Fairness fix:** the retrieved payload's own `status` field (the
pre-computed Supported/Weakened/Broken label from reason_engine.py) is
stripped before the model ever sees it. The first version of this script
handed that label straight to the LLM and asked it to classify -- which
mostly tests "does the model defer to a verdict it was handed," not
"can it reason from raw evidence to a verdict," undermining any later
"baseline2 got this wrong, the agent got it right" comparison. The model
still sees the computed growth/margin number, the numeric explanation, and
the cited evidence (all of which state the reason's threshold in plain
text) -- it has to do the actual classification itself, just without being
handed the answer key.

Usage (spends real API budget):
    python3 baseline2.py TICKER REASON_KEY
"""

import json
import sys

from llm_client import call_claude
from tools import FINALIZE_SINGLE_REASON_TOOL, REASON_DEFS, check_reason_status


def run_baseline2(ticker: str, reason_key: str) -> dict:
    if reason_key not in REASON_DEFS:
        raise ValueError(f"unknown reason_key {reason_key!r}, expected one of {list(REASON_DEFS)}")
    reason = REASON_DEFS[reason_key]

    # Single retrieval call, no ability to seek more -- the defining
    # limitation of this baseline vs. the real agent.
    retrieved = check_reason_status(ticker, reason_key)
    # Strip the pre-computed status before the model sees it -- see the
    # fairness-fix note above. Kept in the returned dict (as `retrieved`)
    # for scoring/comparison purposes, just not shown to the LLM.
    evidence_for_model = {k: v for k, v in retrieved.items() if k != "status"}

    messages = [{
        "role": "user",
        "content": (
            f"Here is retrieved evidence for one investment reason for {ticker}: "
            f"\"{reason.description}\"\n\n"
            f"Retrieved data:\n{json.dumps(evidence_for_model, indent=2)}\n\n"
            "Based only on this retrieved evidence (you cannot retrieve anything else), "
            "classify this reason yourself as Supported / Weakened / Broken / Not enough "
            "data -- the retrieved data does not include a pre-computed verdict, work it "
            "out from the numbers and the reason's stated threshold. "
            "Call finalize_answer with your conclusion."
        ),
    }]
    tools = [FINALIZE_SINGLE_REASON_TOOL]

    total_input_tokens = 0
    total_output_tokens = 0
    for _ in range(3):
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
                "retrieved": retrieved,
                **finalize_call["input"],
                "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            }

        messages.append({
            "role": "user",
            "content": "Please call finalize_answer with your structured conclusion now.",
        })

    raise RuntimeError("baseline2 exceeded its loop cap without reaching finalize_answer")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 baseline2.py TICKER REASON_KEY")
        sys.exit(1)
    result = run_baseline2(sys.argv[1], sys.argv[2])
    print(result)
