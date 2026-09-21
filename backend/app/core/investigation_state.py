"""Explicit Investigation State + a deterministic Evidence Assessor sitting
between the agent's tool loop and its finalize_report call (agent.py
run_with_llm).

Closes two gaps a design review of the architecture surfaced:

1. Before this, "state" was implicit -- just the raw conversation
   `messages` list. Nothing besides the LLM re-reading that transcript
   tracked which reason had which evidence gathered, so nothing else could
   reason about sufficiency without re-parsing free text.
2. Before this, "is the evidence sufficient to finalize" was decided
   entirely by the LLM's own judgment (a natural-language instruction in
   the system prompt: "for anything uncertain, gather a second source"),
   with no code checkpoint verifying it actually did. `assess_sufficiency`
   adds one -- not to second-guess the LLM's classification of a reason's
   status (that stays the LLM's call), but to catch a narrow, checkable
   failure mode: finalizing an uncertain reason without the corroborating
   tool call the prompt asked for.
"""

from dataclasses import dataclass, field

UNCERTAIN_STATUSES = {"Weakened", "Broken", "Not enough data"}


@dataclass
class InvestigationState:
    """What the agent has actually done and found this run, tracked
    alongside (not instead of) the raw message history the LLM sees.
    """

    ticker: str
    tool_calls: list[dict] = field(default_factory=list)

    def record(self, name: str, tool_input: dict, result: dict) -> None:
        self.tool_calls.append({"name": name, "input": tool_input, "result": result})

    def calls_for(self, tool_name: str, reason_key: str) -> list[dict]:
        return [
            c for c in self.tool_calls
            if c["name"] == tool_name and c["input"].get("reason_key") == reason_key
        ]


def assess_sufficiency(state: InvestigationState, proposed_reasons: list[dict]) -> list[str]:
    """Deterministic checkpoint run before a finalize_report call is
    accepted. Returns a list of problems (empty list = sufficient).

    Only flags the specific failure mode this project's own system prompt
    asks the agent to avoid but never previously verified: an uncertain
    status, or a status derived from conflicting evidence, finalized
    without the corroborating tool call that situation calls for.
    """
    problems = []
    for entry in proposed_reasons:
        reason_key = entry.get("reason_key")
        status = entry.get("status")
        status_calls = state.calls_for("check_reason_status", reason_key)
        if not status_calls:
            problems.append(
                f"{reason_key}: finalized with status {status!r} but check_reason_status "
                "was never called for it"
            )
            continue

        original = status_calls[-1]["result"]
        if status in UNCERTAIN_STATUSES and not state.calls_for("get_secondary_evidence", reason_key):
            problems.append(
                f"{reason_key}: status is {status} but no get_secondary_evidence call "
                "was made for it"
            )
        if original.get("conflicting_evidence") and not state.calls_for("get_filing_context", reason_key):
            problems.append(
                f"{reason_key}: conflicting evidence was found but get_filing_context "
                "was never called for it"
            )
    return problems
