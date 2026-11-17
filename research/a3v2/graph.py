"""LangGraph for A3 v2 (Sequential pipeline with a review stage and a
deterministic guard). Reuses the v1 nodes unchanged; adds analyze_claim,
evidence_review, reconcile_v2 and reconciliation_guard.

    retrieve_evidence -> initial_verdict -> numeric_verification -> analyze_claim
      -> generate_hypotheses -> counter_investigation
      -> evidence_review -> reconcile_v2            (review.enabled)
      |  reconcile (v1)                             (review disabled: v1 behaviour)
      -> apply_guards (v1) -> reconciliation_guard  (guard.enabled) -> finalize
"""

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from experiments.pipeline import ClaimRun
from graphs import nodes as v1
from graphs.build import LLM_RETRY, initial_state
from graphs.state import ClaimState

from . import A3V2_VERSION, GRAPH_VERSION
from .derived import run_computation
from .guard import decide
from .interfaces import DefaultAnalyzer, NotAssessedDecidability
from .prompts import RECONCILIATION_INSTRUCTION_V2
from .reviewer import review


class V2State(ClaimState, total=False):
    v2_analysis: dict
    v2_computations: list[dict]
    v2_review: dict
    v2_guard: dict


@dataclass
class V2Context:
    run: Any
    kind: str = "contradiction_aware"  # v1 nodes (apply_guards, finalize) format their records as A3
    analyzer: Any = field(default_factory=DefaultAnalyzer)
    decidability: Any = field(default_factory=NotAssessedDecidability)


def analyze_claim(state: V2State, runtime: Runtime[V2Context]) -> dict:
    """Entry: `model_verdict`. Exit: assertions, claim period, requested
    deterministic computations (executed here, registered as evidence). No LLM
    call with the default analyzer."""
    t0 = time.monotonic()
    v1._require(state, "analyze_claim", "model_verdict")
    run = runtime.context.run
    analysis = runtime.context.analyzer.analyze(run.claim, state["model_verdict"], run.retriever.filings)
    analysis["decidability"] = runtime.context.decidability.assess(run.claim, analysis["assertions"], [])
    comps = [run_computation(run.ledger, run.claim, c) for c in analysis["computations"]]
    run.stages.append({"stage": "analyze_claim", "analysis": analysis, "computations": comps})
    return {"v2_analysis": analysis, "v2_computations": comps,
            **v1._step(runtime, "analyze_claim", t0, assertions=len(analysis["assertions"]), computations=len(comps),
                       period_source=analysis["claim_period"]["source"])}


def _reviewable_ids(state: V2State) -> list[str]:
    ids = [p["evidence_id"] for p in state.get("retrieved_evidence") or []]
    ids += [e for c in state["financial_verification"]["checks"] for e in c.get("evidence_ids") or []]
    ids += [p["evidence_id"] for p in state.get("counterevidence") or []]
    ids += [e for n in state.get("counter_numeric") or [] for e in n.get("evidence_ids") or []]
    ids += [c["evidence_id"] for c in state.get("v2_computations") or [] if c.get("evidence_id")]
    return list(dict.fromkeys(ids))


def evidence_review(state: V2State, runtime: Runtime[V2Context]) -> dict:
    """Entry: counter-evidence + analysis. Exit: `v2_review` (deterministic
    checks + validated reviewer findings), or a NO_FINAL_VERDICT failure."""
    t0 = time.monotonic()
    v1._require(state, "evidence_review", "v2_analysis", "counterevidence")
    run = runtime.context.run
    try:
        rec = review(run, state["v2_analysis"], _reviewable_ids(state), run.cfg["review"])
    except v1.STAGE_ERRORS as e:
        return {**v1._failure(e, "evidence_review", True), **v1._step(runtime, "evidence_review", t0, "failed", error=str(e))}
    run.stages.append({"stage": "evidence_review", **rec})
    return {"v2_review": rec, **v1._step(runtime, "evidence_review", t0, findings=len(rec["findings"]),
                                         deciding=sum(f["relation"] in ("ENTAILS", "CONTRADICTS") for f in rec["findings"]),
                                         downgraded=sum(bool(f["downgraded_reason"]) for f in rec["findings"]))}


def reconcile_v2(state: V2State, runtime: Runtime[V2Context]) -> dict:
    """v1 reconciliation with the review table added to its packet."""
    t0 = time.monotonic()
    v1._require(state, "reconcile_v2", "contradiction_hypotheses", "counterevidence", "counter_numeric", "v2_review")
    v = state["model_verdict"]
    table = [{k: f[k] for k in ("assertion_id", "evidence_ids", "relation", "declared_relation", "evidence_type", "definition_mismatch",
                                 "validation_status", "justification")} for f in state["v2_review"]["findings"]]
    try:
        final = runtime.context.run.ask(
            "reconciliation", RECONCILIATION_INSTRUCTION_V2,
            {"initial_verdict": {"label": state["initial_verdict"]["label"], "claim_type": v.get("claim_type")},
             "hypotheses": state["contradiction_hypotheses"], "counter_evidence": state["counterevidence"],
             "counter_numeric": state["counter_numeric"], "assertions": state["v2_analysis"]["assertions"], "evidence_review": table},
            v1.RECONCILIATION_TOOL)
    except v1.STAGE_ERRORS as e:
        return {**v1._failure(e, "reconcile_v2", True), **v1._step(runtime, "reconcile_v2", t0, "failed", error=str(e))}
    return {"second_look": final, **v1._step(runtime, "reconcile_v2", t0, model_final_label=final.get("label"))}


def reconciliation_guard(state: V2State, runtime: Runtime[V2Context]) -> dict:
    """Entry: v1 guards applied (`final_verdict`). Exit: final label after the
    evidence-grounded guard; a rejected change keeps A2's label and citations.
    No LLM call."""
    t0 = time.monotonic()
    v1._require(state, "reconciliation_guard", "final_verdict", "financial_verification", "v2_review")
    run, fv = runtime.context.run, state["financial_verification"]
    d = decide(initial_label=fv["label"], proposed_label=state["final_verdict"], initial_rule=fv["rule"], initial_checks=fv["checks"],
               supporting=state["final_supporting"], contradicting=state["final_contradicting"],
               assessments=state.get("contradiction_assessment") or [], counter_numeric=state.get("counter_numeric") or [],
               findings=state["v2_review"]["findings"], ledger=run.ledger, claim=run.claim, period=state["v2_review"]["claim_period"])
    out = {"v2_guard": d, "final_verdict": d["final_label"]}
    if d["outcome"] == "REJECT":
        out.update({"final_supporting": fv["supporting"], "final_contradicting": fv["contradicting"]})
    elif d["excluded_citations"]:
        bad = {e["evidence_id"] for e in d["excluded_citations"]}
        out.update({"final_supporting": [c for c in state["final_supporting"] if isinstance(c, dict) and c.get("evidence_id") not in bad],
                    "final_contradicting": [c for c in state["final_contradicting"] if isinstance(c, dict) and c.get("evidence_id") not in bad]})
    investigation = {**state["investigation"], "a3v2": {"version": A3V2_VERSION, "analysis": state["v2_analysis"],
                                                         "computations": state.get("v2_computations") or [],
                                                         "evidence_review": state["v2_review"], "reconciliation_guard": d}}
    run.stages.append({"stage": "reconciliation_guard", **d})
    return {**out, "investigation": investigation,
            **v1._step(runtime, "reconciliation_guard", t0, outcome=d["outcome"], reason=d["reason_code"], label=d["final_label"])}


def v1_route(target):
    def route(state):
        return "finalize" if state.get("stop_reason") else target
    return route


@lru_cache(maxsize=8)
def build_v2_graph(review_enabled: bool = True, guard_enabled: bool = True, retry=LLM_RETRY):
    if guard_enabled and not review_enabled:
        raise ValueError("the reconciliation guard needs the evidence review")
    g = StateGraph(V2State, context_schema=V2Context)
    for name, fn, r in (("retrieve_evidence", v1.retrieve_evidence, None), ("initial_verdict", v1.initial_verdict_node, retry),
                        ("numeric_verification", v1.numeric_verification, None), ("analyze_claim", analyze_claim, None),
                        ("generate_hypotheses", v1.generate_hypotheses, retry), ("counter_investigation", v1.counter_investigation, None),
                        ("apply_guards", v1.apply_guards, None), ("finalize", v1.finalize, None)):
        g.add_node(name, fn, retry_policy=r) if r else g.add_node(name, fn)
    g.add_edge(START, "retrieve_evidence")
    g.add_conditional_edges("retrieve_evidence", v1_route("initial_verdict"), ["initial_verdict", "finalize"])
    g.add_conditional_edges("initial_verdict", v1_route("numeric_verification"), ["numeric_verification", "finalize"])
    g.add_edge("numeric_verification", "analyze_claim")
    g.add_conditional_edges("analyze_claim", v1_route("generate_hypotheses"), ["generate_hypotheses", "finalize"])
    g.add_conditional_edges("generate_hypotheses", v1_route("counter_investigation"), ["counter_investigation", "finalize"])
    if review_enabled:
        g.add_node("evidence_review", evidence_review)
        g.add_node("reconcile_v2", reconcile_v2, retry_policy=retry)
        g.add_conditional_edges("counter_investigation", v1_route("evidence_review"), ["evidence_review", "finalize"])
        g.add_conditional_edges("evidence_review", v1_route("reconcile_v2"), ["reconcile_v2", "finalize"])
        g.add_conditional_edges("reconcile_v2", v1_route("apply_guards"), ["apply_guards", "finalize"])
    else:
        g.add_node("reconcile", v1.reconcile, retry_policy=retry)
        g.add_conditional_edges("counter_investigation", v1_route("reconcile"), ["reconcile", "finalize"])
        g.add_conditional_edges("reconcile", v1_route("apply_guards"), ["apply_guards", "finalize"])
    if guard_enabled:
        g.add_node("reconciliation_guard", reconciliation_guard)
        g.add_edge("apply_guards", "reconciliation_guard")
        g.add_edge("reconciliation_guard", "finalize")
    else:
        g.add_edge("apply_guards", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def run(claim, cfg, llm, run_id=None, analyzer=None, decidability=None, graph=None) -> tuple[dict, dict]:
    """(prediction, trace) for one ClaimInput, the engine's runner contract.
    Not registered in experiments.RUNNERS: scripts/run_experiment.py cannot
    start a (paid) v2 run by accident."""
    r = ClaimRun(claim, cfg, llm, run_id)
    graph = graph or build_v2_graph(bool(cfg["review"]["enabled"]), bool(cfg["guard"]["enabled"]))
    ctx = V2Context(run=r, analyzer=analyzer or DefaultAnalyzer(), decidability=decidability or NotAssessedDecidability())
    final = graph.invoke(initial_state(claim), context=ctx)
    final["trace"]["graph"]["graph_version"] = GRAPH_VERSION
    final["trace"]["a3v2_version"] = A3V2_VERSION
    return final["prediction"], final["trace"]
