"""Versioned configuration for the shared Agentic Investigation Architecture
(chat assistant + B0-B3 experiment baselines).

Every run records `config_manifest()` in its trace, so a stored result can
always be tied back to the exact workflow / tool schema / prompt / Evidence
Gate it was produced under. Bump the matching version whenever behaviour
that could change a result changes -- the experiment protocol requires
rerunning every affected baseline after a bump, never silently comparing
results across versions.

History:
- workflow 1.0 / tools 1.0 / gate 1.0: run_with_llm + _chat_loop before the
  2026-10-30 refactor (portfolio context passed as prose, no claim schema).
  Results produced under it are archived in data/experiments/historical_v1.
- workflow 2.0 / tools 2.0 / gate 2.0 (2026-10-30): one InvestigationEngine
  shared by chat and B2/B3; portfolio/thesis/history/filing tools; evidence
  ledger with citation verification; reassurance guard; stored traces.
- workflow 2.1 / tools 2.1 / prompt 2.1 (2026-10-30, after the first real
  chat run hit the tool budget with per-reason duplicate calls and its
  forced answer was cut off at max_tokens): tool descriptions say one call
  covers all holdings/reasons; a finalize cut off at max_tokens is rejected
  and retried instead of accepted; chat output cap 3000 -> 8000 tokens and
  tool cap 16 -> 20; prompt asks for a concise answer. The only B0-B3 run
  under 2.0 was B0 (no LLM, unaffected).
- 2026-11-02 (chat only, no version bump: B0-B3 do not use the intent
  analyzer or the demo list): demo universe AAPL/MSFT/AMZN + GOOGL/NVDA;
  intent aliases for both; "เป็นไง" also counts as a portfolio question.
"""

import hashlib
import json

AGENT_WORKFLOW_VERSION = "2.1"
TOOL_SCHEMA_VERSION = "2.1"
EVIDENCE_GATE_VERSION = "2.0"
# Bumped together with any edit to a prompt in investigation_prompts.py.
PROMPT_VERSION = "2.1"
EXPERIMENT_PROTOCOL_VERSION = "b0b3-2.1"

# Same model snapshot as the pre-refactor agent, so a change in results is
# attributable to the workflow, not to a model swap.
MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0
PRICING_VERSION = "anthropic-2025-09:sonnet-4.5"
PRICE_PER_M_INPUT = 3.0
PRICE_PER_M_OUTPUT = 15.0

# Gold Design v0.1 section 6 feasibility budget for B2/B3: 8 tool calls,
# 4 retrieval iterations, 2,000 final-output tokens, 180 s per case.
EXPERIMENT_BUDGET = {
    "max_tool_calls": 8, "max_retrieval_iterations": 4, "max_iterations": 8,
    "max_output_tokens": 2000, "max_seconds": 180, "max_gate_rejections": 2,
}
# A portfolio-wide chat question touches several holdings at once, so it
# gets a larger (still bounded) tool budget than one experiment case.
CHAT_BUDGET = {
    "max_tool_calls": 20, "max_retrieval_iterations": 6, "max_iterations": 10,
    "max_output_tokens": 8000, "max_seconds": 240, "max_gate_rejections": 2,
}


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens / 1e6 * PRICE_PER_M_INPUT + output_tokens / 1e6 * PRICE_PER_M_OUTPUT


def prompt_hash(*parts: str) -> str:
    return hashlib.sha256("\n\x00".join(parts).encode()).hexdigest()[:16]


def tools_hash(tool_specs: list[dict]) -> str:
    return hashlib.sha256(json.dumps(tool_specs, sort_keys=True).encode()).hexdigest()[:16]


def config_manifest(mode: str, budget: dict, system_prompt: str = "", tool_specs: list[dict] | None = None) -> dict:
    return {
        "mode": mode,
        "workflow_version": AGENT_WORKFLOW_VERSION,
        "tool_schema_version": TOOL_SCHEMA_VERSION,
        "evidence_gate_version": EVIDENCE_GATE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(system_prompt) if system_prompt else None,
        "tools_hash": tools_hash(tool_specs) if tool_specs else None,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "pricing_version": PRICING_VERSION,
        "budget": dict(budget),
    }
