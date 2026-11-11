"""Typed state shared by every claim-verification graph.

One state object describes one (approach, claim) run. Fields an approach
does not use stay absent. Everything here is JSON-serialisable; the
non-serialisable run objects (evidence ledger, retriever, LLM client,
conversation) live in the per-run context (`GraphContext`), not the state.

Deliberately absent: the claim category and any label or annotation field.
Approaches see only `ClaimInput` (engine/schema.py). The category is withheld
because "ambiguous" correlates with the INSUFFICIENT_EVIDENCE reference label
(28 of 50 ambiguous claims), so exposing it would leak a prior.
"""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict


@dataclass
class GraphContext:
    """Per-run runtime objects passed to every node (LangGraph `context`)."""

    run: Any  # experiments.pipeline.ClaimRun
    kind: str


class ClaimState(TypedDict, total=False):
    # claim (from ClaimInput only)
    claim_id: str
    claim_text: str
    company: str
    evidence_cutoff: str
    reporting_period: str | None

    # initial stage
    retrieved_evidence: list[dict]        # passages issued by the point-in-time retriever
    model_verdict: dict                   # the model's initial structured verdict
    financial_verification: dict          # deterministic checks + reconcile rule (A2 stage)
    initial_verdict: dict                 # label after the A2 stage (= model label for A1)

    # contradiction investigation (A3)
    contradiction_hypotheses: list[dict]
    counterevidence_queries: list[dict]
    counterevidence: list[dict]           # passages retrieved for the hypotheses (new text only)
    counter_numeric: list[dict]
    contradiction_assessment: list[dict]  # per-hypothesis assessment after the evidence guard

    # self-reflection control (SR)
    reflection_weaknesses: list[dict]

    # second look (A3 / SR): raw final tool output, before guards
    second_look: dict
    investigation: dict                   # the prediction's `contradiction` / `reflection` record
    final_supporting: list[dict]          # cited items after the guards (validated at finalize)
    final_contradicting: list[dict]

    # outcome
    final_verdict: str
    verdict_changed: bool
    change_reason: str | None
    reasoning: str
    evidence_ids: list[str]
    stop_reason: str
    error: str | None
    failed_stage: str | None

    # accounting
    token_usage: dict
    latency_ms: int
    estimated_api_cost: float
    execution_trace: Annotated[list[dict], operator.add]

    # outputs handed back to the runner
    prediction: dict
    trace: dict
