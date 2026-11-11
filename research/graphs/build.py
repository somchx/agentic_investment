"""LangGraph construction and execution for the four approaches.

    A1 conventional_rag        retrieve -> initial_verdict -> finalize
    A2 financial_verification  ... -> numeric_verification -> finalize
    A3 contradiction_aware     ... -> numeric_verification -> generate_hypotheses
                                   -> counter_investigation -> reconcile -> apply_guards -> finalize
    SR self_reflection         ... -> numeric_verification -> self_critique -> revise -> apply_guards -> finalize

Every node routes to `finalize` as soon as the state carries a stage
failure, so a claim always yields one prediction. A3 with
contradiction.enabled=false stops after numeric_verification (the ablation
switch), which makes it identical to A2.

LLM nodes carry a RetryPolicy for transient API failures only (timeouts,
connection errors, HTTP 429/5xx). A retry repeats the identical request
(ClaimRun.ask extends the conversation only after a call returns). Paid-call
refusals, budget stops and cache misses are never retried.
"""

from functools import lru_cache

import requests
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from experiments.pipeline import ClaimRun

from . import nodes
from .state import ClaimState, GraphContext

GRAPH_VERSION = "langgraph-claims-1.0"
KINDS = ("conventional_rag", "financial_verification", "contradiction_aware", "self_reflection")
TRANSIENT_HTTP = {408, 409, 429, 500, 502, 503, 504, 529}


def is_transient(e: Exception) -> bool:
    if isinstance(e, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return e.response.status_code in TRANSIENT_HTTP
    return False


LLM_RETRY = RetryPolicy(max_attempts=3, initial_interval=2.0, backoff_factor=2.0, max_interval=30.0, retry_on=is_transient)


def _failed(state: ClaimState) -> bool:
    return bool(state.get("stop_reason"))


def _after_initial(state: ClaimState, kind: str) -> str:
    if _failed(state) or kind == "conventional_rag":
        return "finalize"
    return "numeric_verification"


def _after_numeric(state: ClaimState, kind: str, contradiction_enabled: bool) -> str:
    if kind == "contradiction_aware" and contradiction_enabled:
        return "generate_hypotheses"
    if kind == "self_reflection":
        return "self_critique"
    return "finalize"


def _next_or_finalize(target: str):
    def route(state: ClaimState) -> str:
        return "finalize" if _failed(state) else target
    return route


@lru_cache(maxsize=16)
def build_graph(kind: str, contradiction_enabled: bool = True, retry: RetryPolicy = LLM_RETRY):
    """Compiled graph for one approach kind. Cached: graphs hold no per-run
    data (that lives in the state and the GraphContext)."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    g = StateGraph(ClaimState, context_schema=GraphContext)
    g.add_node("retrieve_evidence", nodes.retrieve_evidence)
    g.add_node("initial_verdict", nodes.initial_verdict_node, retry_policy=retry)
    g.add_node("finalize", nodes.finalize)
    g.add_edge(START, "retrieve_evidence")
    g.add_conditional_edges("retrieve_evidence", _next_or_finalize("initial_verdict"), ["initial_verdict", "finalize"])
    g.add_edge("finalize", END)
    if kind == "conventional_rag":
        g.add_edge("initial_verdict", "finalize")
        return g.compile()

    g.add_node("numeric_verification", nodes.numeric_verification)
    g.add_conditional_edges("initial_verdict", lambda s: _after_initial(s, kind), ["numeric_verification", "finalize"])
    if kind == "financial_verification" or (kind == "contradiction_aware" and not contradiction_enabled):
        g.add_edge("numeric_verification", "finalize")
        return g.compile()

    g.add_node("apply_guards", nodes.apply_guards)
    g.add_edge("apply_guards", "finalize")
    if kind == "contradiction_aware":
        g.add_node("generate_hypotheses", nodes.generate_hypotheses, retry_policy=retry)
        g.add_node("counter_investigation", nodes.counter_investigation)
        g.add_node("reconcile", nodes.reconcile, retry_policy=retry)
        g.add_edge("numeric_verification", "generate_hypotheses")
        g.add_conditional_edges("generate_hypotheses", _next_or_finalize("counter_investigation"), ["counter_investigation", "finalize"])
        g.add_conditional_edges("counter_investigation", _next_or_finalize("reconcile"), ["reconcile", "finalize"])
        g.add_conditional_edges("reconcile", _next_or_finalize("apply_guards"), ["apply_guards", "finalize"])
    else:
        g.add_node("self_critique", nodes.self_critique, retry_policy=retry)
        g.add_node("revise", nodes.revise, retry_policy=retry)
        g.add_edge("numeric_verification", "self_critique")
        g.add_conditional_edges("self_critique", _next_or_finalize("revise"), ["revise", "finalize"])
        g.add_conditional_edges("revise", _next_or_finalize("apply_guards"), ["apply_guards", "finalize"])
    return g.compile()


def initial_state(claim) -> ClaimState:
    return {"claim_id": claim.claim_id, "claim_text": claim.claim, "company": claim.company,
            "evidence_cutoff": claim.as_of_date, "reporting_period": claim.reporting_period, "execution_trace": []}


def run_graph(kind: str, claim, cfg, llm, run_id: str | None = None, graph=None) -> tuple[dict, dict]:
    """Run one claim through the approach's graph -> (prediction, trace), the
    same contract as the engine's runners. `claim` must be a ClaimInput."""
    run = ClaimRun(claim, cfg, llm, run_id)
    enabled = bool(cfg["contradiction"]["enabled"]) if kind == "contradiction_aware" else True
    graph = graph or build_graph(kind, enabled)
    final = graph.invoke(initial_state(claim), context=GraphContext(run=run, kind=kind))
    final["trace"]["graph"]["graph_version"] = GRAPH_VERSION
    return final["prediction"], final["trace"]


def mermaid(kind: str, contradiction_enabled: bool = True) -> str:
    return build_graph(kind, contradiction_enabled).get_graph().draw_mermaid()
