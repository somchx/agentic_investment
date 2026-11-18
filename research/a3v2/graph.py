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
from . import A3V21_VERSION, A3V211_VERSION, A3V22_VERSION
from .prompts import RECONCILIATION_INSTRUCTION_V2, RECONCILIATION_INSTRUCTION_V21, RECONCILIATION_INSTRUCTION_V211
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
    if _v21(run.cfg):  # normalised reporting period (a3v2.periods) for the claim and its assertions
        from .periods import VERSIONS, normalize_claim_period
        p = normalize_claim_period(run.claim, VERSIONS[_pv(run.cfg)])
        analysis["claim_period"] = p
        for a in analysis["assertions"]:
            if a.get("type") == "claim" or not (a.get("numeric") or {}).get("period_end"):
                a["period_end"] = p["end"]
            a["comparison_end"] = p["comparison"]["end"]
            a["period_start"], a["period_months"], a["period_kind"] = p["start"], p["months"], p["kind"]
    if (run.cfg.get("decidability") or {}).get("name") == "llm_0.1":  # A3 v2.2: classifier record, read by the guard only
        from .decidability import assess_with_llm
        rec = assess_with_llm(run)
        analysis["decidability_record"] = rec
        analysis["decidability"] = [{"assertion_id": "A0", "status": rec["status"], "predicate_type": rec["predicate_type"],
                                     "reason": rec.get("note") or ""}]
    else:
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
    rcfg = runtime.context.run.cfg
    keys = ("assertion_id", "evidence_ids", "relation", "declared_relation", "evidence_type", "definition_mismatch",
            "validation_status", "justification") + (("period_compatibility",) if _v21(rcfg) else ()) + \
        (("statement_time",) if _pv(rcfg) == "1.1" else ())
    table = [{k: f.get(k) for k in keys} for f in state["v2_review"]["findings"]]
    instruction = (RECONCILIATION_INSTRUCTION_V211 if _pv(rcfg) == "1.1" else RECONCILIATION_INSTRUCTION_V21 if _v21(rcfg)
                   else RECONCILIATION_INSTRUCTION_V2)
    try:
        final = runtime.context.run.ask(
            "reconciliation", instruction,
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
    findings = state["v2_review"]["findings"]
    if run.cfg.get("quote_check") == "1.1":  # A3 v2.2: tolerant key-quote check, for the guard's inputs only
        from .checks import revalidate_quotes_v11
        findings, restored = revalidate_quotes_v11(findings, lambda i: getattr(run.ledger.get(i), "excerpt", "") if i else "",
                                                   state["v2_review"]["claim_period"])
    d = decide(initial_label=fv["label"], proposed_label=state["final_verdict"], initial_rule=fv["rule"], initial_checks=fv["checks"],
               supporting=state["final_supporting"], contradicting=state["final_contradicting"],
               assessments=state.get("contradiction_assessment") or [], counter_numeric=state.get("counter_numeric") or [],
               findings=findings, ledger=run.ledger, claim=run.claim, period=state["v2_review"]["claim_period"],
               version=run.cfg["guard"].get("version") or "0.1")
    rec = (state["v2_analysis"] or {}).get("decidability_record")
    if rec is not None:  # A3 v2.2 phase 1: G1 (+G4) gate on accepted changes, D / D-sup downgrade
        from .decidability import apply_phase1
        dcfg = run.cfg["decidability"]
        label, why = apply_phase1(fv["label"], d["final_label"], rec, findings, bool(dcfg.get("scope_gate")), dcfg.get("downgrade") or False)
        d = {**d, "decidability_gate": {"record": rec, "reason": why, "label_before": d["final_label"], "label_after": label}}
        if why:
            d["rule_trace"] = d["rule_trace"] + [f"decidability: {why} ({d['final_label']} -> {label})"]
            if label == fv["label"] and d["final_label"] != fv["label"]:
                d["outcome"], d["reason_code"] = "REJECT", f"DECIDABILITY:{why}"
            elif why.endswith("DOWNGRADE_NO_CRITERION"):
                d["reason_code"] = d["reason_code"] + "+DOWNGRADE_NO_CRITERION"
            d["final_label"] = label
    if run.cfg.get("numeric_checks") == "0.1":  # A3 v2.2: N1 validity of A2's numeric rule, N2 window free cash flow
        from .numeric_checks import apply_numeric_checks, fcf_direction_check, numeric_validity
        from .periods import derive_for_claim
        period = state["v2_review"]["claim_period"]
        validity = numeric_validity(fv["rule"], fv["checks"], period, run.claim.as_of_date, rec)
        fcf = fcf_direction_check(run.claim.claim, run.claim.company, run.claim.as_of_date, period)
        if fcf.get("status") in ("TRUE", "FALSE"):  # register the window figures as evidence for the trace
            fcf["evidence_ids"] = [x["evidence_id"] for m in ("OperatingCashFlow", "CapitalExpenditure")
                                   for x in derive_for_claim(run.ledger, run.claim, period, m)]
        label, why = apply_numeric_checks(d["final_label"], fv["rule"], validity, fcf, findings, rec)
        d = {**d, "numeric_checks": {"validity": validity, "fcf": {k: v for k, v in fcf.items() if k != "inputs"},
                                     "reason": why, "label_before": d["final_label"], "label_after": label}}
        if why:
            d["rule_trace"] = d["rule_trace"] + [f"numeric checks: {why} ({d['final_label']} -> {label})"]
            d["reason_code"] = d["reason_code"] + "+" + why
            if label != fv["label"] and d["outcome"] == "REJECT":
                d["outcome"] = "ACCEPT"
            d["final_label"] = label
    if run.cfg.get("contribution") == "0.1b" and rec is not None:  # A3 v2.2c: deterministic main-driver / largest-factor test
        from .contribution import apply_contribution_b, assess_contribution
        verdict = assess_contribution(run, rec, state["v2_review"].get("reviewed_evidence_ids") or [])
        label, why = apply_contribution_b(d["final_label"], verdict)
        d = {**d, "contribution": {**verdict, "reason": why, "label_before": d["final_label"], "label_after": label}}
        if why:
            d["rule_trace"] = d["rule_trace"] + [f"contribution: {why} ({d['final_label']} -> {label})"]
            d["reason_code"] = d["reason_code"] + "+" + why
            if label != fv["label"] and d["outcome"] == "REJECT":
                d["outcome"] = "ACCEPT"
            d["final_label"] = label
    if run.cfg.get("coverage") == "0.1":  # A3 v2.2 E1: a decisive final label needs a validated basis
        from .numeric_checks import apply_coverage, evidence_basis
        nc = d.get("numeric_checks") or {}
        det = any(k in d["reason_code"] for k in ("N1_", "N2_", "C_TRUE", "C_FALSE"))
        basis = evidence_basis(d["final_label"], findings, fv["rule"], nc.get("validity") or [], det)
        label, why = apply_coverage(d["final_label"], basis)
        d = {**d, "coverage": {"basis": basis, "reason": why, "label_before": d["final_label"], "label_after": label}}
        if why:
            d["rule_trace"] = d["rule_trace"] + [f"coverage: {why} ({d['final_label']} -> {label})"]
            d["reason_code"] = d["reason_code"] + "+" + why
            d["final_label"] = label
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


def _v21(cfg) -> bool:
    return bool((cfg.get("periods") or {}).get("enabled"))


def _pv(cfg) -> str | None:
    """periods rule version of an approach ('1.0' = A3 v2.1, '1.1' = A3 v2.1.1), None when off."""
    return ((cfg.get("periods") or {}).get("version") or "1.0") if _v21(cfg) else None


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
    # when the LLM client retries transient errors itself, the graph does not retry again
    graph = graph or build_v2_graph(bool(cfg["review"]["enabled"]), bool(cfg["guard"]["enabled"]),
                                    retry=None if getattr(llm, "retry", None) else LLM_RETRY)
    ctx = V2Context(run=r, analyzer=analyzer or DefaultAnalyzer(), decidability=decidability or NotAssessedDecidability())
    final = graph.invoke(initial_state(claim), context=ctx)
    final["trace"]["graph"]["graph_version"] = GRAPH_VERSION
    final["trace"]["a3v2_version"] = A3V22_VERSION if (cfg.get("decidability") or {}).get("name") == "llm_0.1" else \
        {None: A3V2_VERSION, "1.0": A3V21_VERSION, "1.1": A3V211_VERSION}[_pv(cfg)]
    return final["prediction"], final["trace"]
