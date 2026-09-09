"""Investigation step: an LLM reads the actual MD&A narrative from the
primary 10-Q/10-K (via filing_context.py) to explain *why* a Broken/Weakened
reason looks the way it does, instead of stopping at "154% > 15%, Human
Review Recommended" with no further context.

This is the "Layer 2 (agentic): why did the number change, what tool do I
need next, is this an accounting artifact or a real event" capability --
the deterministic tools (Layer 1) can flag an anomaly but can't explain one.

Usage (spends real API budget -- one call per run):
    python3 investigate.py TICKER REASON_KEY
"""

import sys

from llm_client import call_claude
from sec_client import get_company_facts
from filing_context import get_filing_narrative, latest_10q_accession
from tools import REASON_DEFS, SECONDARY_EVIDENCE_METRICS, check_reason_status

INVESTIGATE_TOOL = {
    "name": "submit_investigation",
    "description": "Submit your investigation findings for this anomalous reason.",
    "input_schema": {
        "type": "object",
        "properties": {
            "likely_cause": {
                "type": "string",
                "description": "Best-supported explanation for the anomaly, grounded in the filing text provided -- e.g. 'debt issuance for capex', 'acquisition', 'accounting restatement', 'tag/definition mismatch', or 'unclear from available evidence'.",
            },
            "is_data_artifact": {
                "type": "boolean",
                "description": "True if the evidence suggests this is a restatement/tag-mismatch/data problem rather than a real business event.",
            },
            "human_review_recommended": {"type": "boolean"},
            "what_to_check_next": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific follow-up questions a human reviewer should look into.",
            },
            "narrative_summary": {
                "type": "string",
                "description": "2-4 sentence plain-language summary grounded in the retrieved filing text, not speculation beyond it.",
            },
        },
        "required": ["likely_cause", "is_data_artifact", "human_review_recommended", "what_to_check_next", "narrative_summary"],
    },
}


def investigate(ticker: str, reason_key: str) -> dict:
    reason = REASON_DEFS[reason_key]
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]

    status_result = check_reason_status(ticker, reason_key)
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    accn = latest_10q_accession(ticker)
    narrative_snippets = get_filing_narrative(cik, accn, metric)

    if not narrative_snippets:
        evidence_text = "(No narrative text found in the primary filing for this metric.)"
    else:
        evidence_text = "\n\n---\n\n".join(narrative_snippets[:2])

    messages = [{
        "role": "user",
        "content": (
            f"An automated check found this reason for {ticker} in status "
            f"'{status_result['status']}': \"{reason.description}\"\n"
            f"Computed value: {status_result['computed_value']}\n"
            f"Numeric explanation: {status_result['explanation']}\n\n"
            f"Here is the actual narrative text from the company's primary SEC filing "
            f"(10-Q/10-K MD&A section) discussing this metric:\n\n{evidence_text}\n\n"
            "Investigate: what does this filing text say actually caused this? Is it "
            "consistent with a real business event, or could it be a data/tagging "
            "artifact? Ground your answer in the text above -- don't speculate beyond "
            "what it supports. Call submit_investigation with your findings."
        ),
    }]

    payload = call_claude(messages, tools=[INVESTIGATE_TOOL], max_tokens=1024)
    content = payload["content"]
    usage = payload.get("usage", {})

    finalize_call = next((b for b in content if b["type"] == "tool_use" and b["name"] == "submit_investigation"), None)
    if not finalize_call:
        raise RuntimeError("model did not call submit_investigation")

    return {
        "ticker": ticker,
        "reason_key": reason_key,
        "status": status_result["status"],
        "computed_value": status_result["computed_value"],
        **finalize_call["input"],
        "usage": usage,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 investigate.py TICKER REASON_KEY")
        sys.exit(1)
    result = investigate(sys.argv[1], sys.argv[2])
    for k, v in result.items():
        print(f"{k}: {v}")
