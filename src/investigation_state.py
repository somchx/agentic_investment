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

        # Session 3 audit item 1, second half: the tool was genuinely
        # called, but came back with an "error" key (no facts found, SEC
        # unreachable, etc.) -- not a real status at all. Finalizing
        # *anything* off of that (the LLM effectively guessing/hallucinating
        # a number since it has none) must be rejected outright, regardless
        # of which status was declared. Checked before the status-match
        # comparison below, since an error result has no "status" key for
        # that comparison to catch on its own.
        if "error" in original and status != "Not enough data":
            # "Not enough data" is the CORRECT honest response to a tool
            # error and is allowed through; anything else (Supported/
            # Weakened/Broken) means the LLM stated a status with no real
            # evidence behind it at all.
            problems.append(
                f"{reason_key}: finalized with status {status!r} but check_reason_status "
                f"actually returned an error ({original['error']!r}) -- there is no real "
                "evidence to finalize from; call the tool again or report Not enough data"
            )
            continue

        # The one check this project's own accuracy claims quietly depended
        # on without actually enforcing it (Code Audit Session 2, item 3):
        # the LLM's declared status must match what the Rule Engine itself
        # computed. Every prior "100% accuracy" result held only because
        # Claude happened to agree with the tool every time it was run --
        # nothing stopped it from finalizing a different status.
        original_status = original.get("status")
        if original_status is not None and status != original_status:
            problems.append(
                f"{reason_key}: finalized as {status!r} but check_reason_status actually "
                f"returned {original_status!r} -- the declared status must match the "
                "Rule Engine's computed status exactly (re-check the evidence, don't "
                "override the number)"
            )
            continue

        if status in UNCERTAIN_STATUSES:
            secondary = state.calls_for("get_secondary_evidence", reason_key)
            evaluated_period = original.get("evaluated_period")
            # Calling the tool is not the same as obtaining corroboration. A call
            # counts only if it actually cross-checked (checked), for the period
            # the rule was evaluated on (period_matches and target_period ==
            # evaluated_period). Anything else -- unparseable release, another
            # quarter, or an older result without these fields -- does not count.
            valid = [
                c for c in secondary
                if c["result"].get("checked") is True
                and c["result"].get("period_matches") is True
                and isinstance(evaluated_period, str)
                and bool(evaluated_period.strip())
                and "error" not in c["result"]
                and c["result"].get("target_period") == evaluated_period
            ]
            if not secondary:
                problems.append(
                    f"{reason_key}: status is {status} but no get_secondary_evidence call "
                    "was made for it"
                )
            elif not valid:
                last = secondary[-1]["result"]
                problems.append(
                    f"{reason_key}: get_secondary_evidence did not corroborate the evaluated period "
                    f"{evaluated_period} (checked={last.get('checked')}, "
                    f"period_matches={last.get('period_matches')}, target_period={last.get('target_period')}) "
                    "-- no valid secondary evidence for this reason"
                )
        if original.get("conflicting_evidence") and not state.calls_for("get_filing_context", reason_key):
            problems.append(
                f"{reason_key}: conflicting evidence was found but get_filing_context "
                "was never called for it"
            )
    return problems
