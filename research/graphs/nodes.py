"""Graph nodes. Each wraps one stage of experiments/pipeline.py, so prompts,
tool schemas and request bytes are those of the pre-LangGraph engine (the
LLM response cache stays valid).

Every node states its entry condition (what must already be in the state)
and its exit condition (what it guarantees to write). A node that cannot do
its work because the model returned no usable structured output, or the
claim's budget ran out, records `error` / `stop_reason` / `failed_stage` and
the conditional edges route straight to `finalize`. Any other exception
propagates and the runner records the claim as ERROR -- nothing is hidden.

Correctness is never judged here: nodes see no label from the dataset.
"""

import time

from langgraph.runtime import Runtime

from engine.prompts import (CONTRADICTION_INSTRUCTION, CONTRADICTION_PLAN_TOOL, RECONCILIATION_INSTRUCTION, RECONCILIATION_TOOL,
                            REVISION_INSTRUCTION, REVISION_TOOL, SELF_CRITIQUE_INSTRUCTION, SELF_CRITIQUE_TOOL)
from experiments.pipeline import (NoStructuredOutput, StageBudgetExhausted, build_prediction, finish_revision, initial_retrieval,
                                  initial_summary, initial_verdict, verified_from)

from .state import ClaimState, GraphContext

STAGE_ERRORS = (NoStructuredOutput, StageBudgetExhausted)


def _step(runtime: Runtime[GraphContext], node: str, t0: float, status: str = "ok", **info) -> dict:
    run = runtime.context.run
    return {"execution_trace": [{"node": node, "status": status, "duration_ms": round((time.monotonic() - t0) * 1000),
                                 "llm_calls_so_far": len(run.llm_calls), "retrieval_queries_so_far": len(run.retriever.queries),
                                 **info}]}


def _require(state: ClaimState, node: str, *keys: str) -> None:
    missing = [k for k in keys if k not in state]
    if missing:
        raise RuntimeError(f"{node}: entry condition failed, state lacks {missing}")


def _failure(e: Exception, stage: str, after_initial: bool) -> dict:
    if after_initial:
        stop = "BUDGET_EXHAUSTED_AFTER_INITIAL" if isinstance(e, StageBudgetExhausted) else "NO_FINAL_VERDICT"
    else:
        stop = "NO_VERDICT"
    return {"error": str(e), "stop_reason": stop, "failed_stage": stage}


# ------------------------------------------------------------ initial stage

def retrieve_evidence(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: claim fields. Exit: `retrieved_evidence` (possibly empty) from
    filings filed on or before the cutoff, or a NO_VERDICT failure."""
    t0 = time.monotonic()
    _require(state, "retrieve_evidence", "claim_id", "claim_text", "evidence_cutoff")
    try:
        passages = initial_retrieval(runtime.context.run)
    except STAGE_ERRORS as e:
        return {**_failure(e, "retrieve_evidence", False), **_step(runtime, "retrieve_evidence", t0, "failed", error=str(e))}
    return {"retrieved_evidence": passages,
            **_step(runtime, "retrieve_evidence", t0, passages=len(passages),
                    eligible_filings=len(runtime.context.run.retriever.filings))}


def initial_verdict_node(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `retrieved_evidence`. Exit: `model_verdict` with a valid label
    (+ `initial_verdict` for A1, which has no later stage), or NO_VERDICT."""
    t0 = time.monotonic()
    _require(state, "initial_verdict", "retrieved_evidence")
    try:
        v = initial_verdict(runtime.context.run, state["retrieved_evidence"])
    except STAGE_ERRORS as e:
        return {**_failure(e, "initial_verdict", False), **_step(runtime, "initial_verdict", t0, "failed", error=str(e))}
    out = {"model_verdict": v, **_step(runtime, "initial_verdict", t0, label=v["label"], claim_type=v.get("claim_type"))}
    if runtime.context.kind == "conventional_rag":
        out["initial_verdict"] = {"label": v["label"]}
    return out


def numeric_verification(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `model_verdict`. Exit: `financial_verification` (deterministic
    checks of the model's numeric assertions + reconcile rule) and
    `initial_verdict` = label after the rule. No LLM call."""
    t0 = time.monotonic()
    _require(state, "numeric_verification", "model_verdict")
    s = verified_from(runtime.context.run, state["model_verdict"])
    fv = {"rule": s["rule"], "llm_label": state["model_verdict"]["label"], "label": s["label"], "checks": s["checks"],
          "supporting": s["supporting"], "contradicting": s["contradicting"]}
    return {"financial_verification": fv, "initial_verdict": {"label": s["label"]},
            **_step(runtime, "numeric_verification", t0, rule=s["rule"], checks=[c["status"] for c in s["checks"]])}


def _verified(state: ClaimState) -> dict:
    fv = state["financial_verification"]
    return {"verdict": state["model_verdict"], "label": fv["label"], "rule": fv["rule"], "checks": fv["checks"],
            "supporting": fv["supporting"], "contradicting": fv["contradicting"]}


# --------------------------------------------- contradiction investigation

def generate_hypotheses(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `financial_verification`. Exit: up to max_hypotheses falsification
    hypotheses, each with a search query and optionally a figure to compute."""
    t0 = time.monotonic()
    _require(state, "generate_hypotheses", "financial_verification")
    run, c = runtime.context.run, runtime.context.run.cfg["contradiction"]
    investigation = {"enabled": True, "hypotheses": [], "queries": [], "counter_evidence_ids": [], "counter_numeric": []}
    try:
        plan = run.ask("contradiction_plan", CONTRADICTION_INSTRUCTION.format(n=c["max_hypotheses"]),
                       {"initial_verdict": initial_summary(_verified(state)), "max_hypotheses": c["max_hypotheses"]},
                       CONTRADICTION_PLAN_TOOL)
    except STAGE_ERRORS as e:
        return {"investigation": investigation, **_failure(e, "generate_hypotheses", True),
                **_step(runtime, "generate_hypotheses", t0, "failed", error=str(e))}
    hypotheses = (plan.get("hypotheses") or [])[:c["max_hypotheses"]]
    investigation["hypotheses"] = hypotheses
    return {"contradiction_hypotheses": hypotheses, "investigation": investigation,
            **_step(runtime, "generate_hypotheses", t0, hypotheses=len(hypotheses))}


def counter_investigation(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `contradiction_hypotheses`. Exit: for each hypothesis, NEW
    passages (already-shown ones excluded) from the same point-in-time corpus
    and the requested deterministic figure. Finding nothing is recorded, not
    filled in. No LLM call."""
    t0 = time.monotonic()
    _require(state, "counter_investigation", "contradiction_hypotheses", "investigation")
    run, c = runtime.context.run, runtime.context.run.cfg["contradiction"]
    hypotheses = [dict(h) for h in state["contradiction_hypotheses"]]
    investigation = {**state["investigation"], "hypotheses": hypotheses, "queries": []}
    counter, counter_numeric = [], []
    try:
        for i, h in enumerate(hypotheses):
            hid = str(h.get("hypothesis_id") or f"H{i + 1}")
            h["hypothesis_id"] = hid
            if c["counter_retrieval"] and (h.get("search_query") or "").strip():
                hits = run.search(h["search_query"], top_k=c["top_k_per_query"], exclude_shown=True, purpose=f"counter:{hid}")
                investigation["queries"].append({"hypothesis_id": hid, "query": h["search_query"], "results": [p["evidence_id"] for p in hits]})
                counter += [{"hypothesis_id": hid, **p} for p in hits]
            if c["counter_numeric_checks"] and isinstance(h.get("numeric_check"), dict):
                check = run.verify_numbers([h["numeric_check"]], f"counter:{hid}")[0]
                counter_numeric.append({"hypothesis_id": hid, "status": check["status"], "issues": check["issues"],
                                        "computed": check["computed"], "evidence_ids": check["evidence_ids"]})
    except STAGE_ERRORS as e:
        return {"investigation": investigation, "contradiction_hypotheses": hypotheses,
                "counterevidence_queries": investigation["queries"], **_failure(e, "counter_investigation", True),
                **_step(runtime, "counter_investigation", t0, "failed", error=str(e))}
    investigation["counter_evidence_ids"] = [p["evidence_id"] for p in counter]
    investigation["counter_numeric"] = counter_numeric
    run.stages.append({"stage": "contradiction_investigation", **investigation})
    return {"contradiction_hypotheses": hypotheses, "counterevidence_queries": investigation["queries"], "counterevidence": counter,
            "counter_numeric": counter_numeric, "investigation": investigation,
            **_step(runtime, "counter_investigation", t0, queries=len(investigation["queries"]), passages_found=len(counter),
                    numeric_checks=len(counter_numeric), no_counterevidence_found=not counter and not counter_numeric)}


def reconcile(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: hypotheses + counter-evidence. Exit: the model's per-hypothesis
    assessment and final verdict (`second_look`), before the guards."""
    t0 = time.monotonic()
    _require(state, "reconcile", "contradiction_hypotheses", "counterevidence", "counter_numeric")
    v = state["model_verdict"]
    try:
        final = runtime.context.run.ask(
            "reconciliation", RECONCILIATION_INSTRUCTION,
            {"initial_verdict": {"label": state["initial_verdict"]["label"], "claim_type": v.get("claim_type")},
             "hypotheses": state["contradiction_hypotheses"], "counter_evidence": state["counterevidence"],
             "counter_numeric": state["counter_numeric"]}, RECONCILIATION_TOOL)
    except STAGE_ERRORS as e:
        return {**_failure(e, "reconcile", True), **_step(runtime, "reconcile", t0, "failed", error=str(e))}
    return {"second_look": final, **_step(runtime, "reconcile", t0, model_final_label=final.get("label"))}


# ------------------------------------------------- self-reflection control

def self_critique(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `financial_verification`. Exit: up to max_items weaknesses of
    the model's own verdict. No retrieval, no numeric checks."""
    t0 = time.monotonic()
    _require(state, "self_critique", "financial_verification")
    run = runtime.context.run
    n = run.cfg["reflection"]["max_items"]
    reflection = {"enabled": True, "weaknesses": []}
    try:
        critique = run.ask("self_critique", SELF_CRITIQUE_INSTRUCTION.format(n=n),
                           {"initial_verdict": initial_summary(_verified(state)), "max_hypotheses": n}, SELF_CRITIQUE_TOOL)
    except STAGE_ERRORS as e:
        return {"investigation": reflection, **_failure(e, "self_critique", True),
                **_step(runtime, "self_critique", t0, "failed", error=str(e))}
    weaknesses = [dict(w) for w in (critique.get("weaknesses") or [])[:n]]
    for i, w in enumerate(weaknesses):
        w["weakness_id"] = str(w.get("weakness_id") or f"W{i + 1}")
    reflection["weaknesses"] = weaknesses
    run.stages.append({"stage": "self_critique", "weaknesses": weaknesses})
    return {"reflection_weaknesses": weaknesses, "investigation": reflection,
            **_step(runtime, "self_critique", t0, weaknesses=len(weaknesses))}


def revise(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `reflection_weaknesses`. Exit: the model's revised verdict
    (`second_look`), before the guards."""
    t0 = time.monotonic()
    _require(state, "revise", "reflection_weaknesses")
    v = state["model_verdict"]
    try:
        final = runtime.context.run.ask(
            "revision", REVISION_INSTRUCTION,
            {"initial_verdict": {"label": state["initial_verdict"]["label"], "claim_type": v.get("claim_type")},
             "weaknesses": state["reflection_weaknesses"]}, REVISION_TOOL)
    except STAGE_ERRORS as e:
        return {**_failure(e, "revise", True), **_step(runtime, "revise", t0, "failed", error=str(e))}
    return {"second_look": final, **_step(runtime, "revise", t0, model_final_label=final.get("label"))}


# ------------------------------------------------------------- reconciliation

def apply_guards(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: `second_look`. Exit: final label after the deterministic guards
    (A3 and SR alike): a challenge counts only with a valid citation; a move
    to SUPPORTED / CONTRADICTED needs a valid citation for it, otherwise the
    initial verdict is kept; then A2's numeric rule is re-applied."""
    t0 = time.monotonic()
    _require(state, "apply_guards", "second_look", "investigation", "financial_verification")
    run, final = runtime.context.run, state["second_look"]
    g, label, rule, sup, con = finish_revision(run, _verified(state), final)
    investigation = {**state["investigation"]}
    investigation.update({"assessments": g["assessments"], "model_final_label": final.get("label"),
                          "model_says_changed": final.get("verdict_changed"), "change_reason": final.get("change_reason"),
                          "guard_reverted": g["reverted"], "final_numeric_rule": rule,
                          "challenges_supported": sum(1 for a in g["assessments"] if a["assessment"] == "CHALLENGE_SUPPORTED"),
                          "invalid_challenges": sum(1 for a in g["assessments"] if a["flag"])})
    stage = "reconciliation" if runtime.context.kind == "contradiction_aware" else "revision"
    run.stages.append({"stage": stage, "label": label, "guard_reverted": g["reverted"], "numeric_rule": rule,
                       "assessments": g["assessments"]})
    return {"investigation": investigation, "contradiction_assessment": g["assessments"], "final_verdict": label,
            "final_supporting": sup, "final_contradicting": con, "reasoning": final.get("reasoning_summary", ""),
            "change_reason": final.get("change_reason"),
            **_step(runtime, "apply_guards", t0, label=label, guard_reverted=g["reverted"], numeric_rule=rule)}


# ------------------------------------------------------------------ finalize

def _base(state: ClaimState) -> dict:
    v, fv = state["model_verdict"], state["financial_verification"]
    return {"claim_type": v.get("claim_type"), "llm_label": v["label"], "numeric_rule": fv["rule"],
            "numeric_statuses": [c["status"] for c in fv["checks"]]}


def second_look_record(state: ClaimState, pred: dict, kind: str) -> dict:
    """Research fields for A3 / SR. Whether a change was correct is decided
    at evaluation time against the reference labels, never here."""
    inv = state.get("investigation") or {}
    counter = state.get("counterevidence") or []
    return {"initial_verdict": state.get("initial_verdict", {}).get("label"),
            "initial_evidence": [c.get("evidence_id") for c in (state.get("financial_verification") or {}).get("supporting", [])
                                 + (state.get("financial_verification") or {}).get("contradicting", []) if isinstance(c, dict)],
            "contradiction_hypotheses": [h.get("challenge") or h.get("critique") for h in
                                         (state.get("contradiction_hypotheses") or state.get("reflection_weaknesses") or [])],
            "counterevidence_queries": [q["query"] for q in state.get("counterevidence_queries") or []],
            "counterevidence_found": len(counter) + len(state.get("counter_numeric") or []),
            "no_counterevidence_found": (kind == "contradiction_aware" and "counterevidence" in state
                                         and not counter and not state.get("counter_numeric")),
            "challenges_supported": inv.get("challenges_supported"), "guard_reverted": inv.get("guard_reverted"),
            "final_verdict": pred["predicted_label"], "verdict_changed": pred["verdict_changed"],
            "change_reason": inv.get("change_reason") if pred["verdict_changed"] else None,
            "completed": pred["stop_reason"] == "COMPLETED"}


def finalize(state: ClaimState, runtime: Runtime[GraphContext]) -> dict:
    """Entry: any state. Exit: `prediction` + `trace` in the engine's output
    format, plus the outcome / accounting fields of the state."""
    t0 = time.monotonic()
    run, kind = runtime.context.run, runtime.context.kind
    err = state.get("error")
    if "model_verdict" not in state:
        args = dict(initial_label=None, label="INSUFFICIENT_EVIDENCE", reasoning="", supporting=[], contradicting=[],
                    stop_reason=state.get("stop_reason", "NO_VERDICT"), error=err)
    elif kind == "conventional_rag":
        v = state["model_verdict"]
        args = dict(initial_label=v["label"], label=v["label"], reasoning=v.get("reasoning_summary", ""),
                    supporting=v.get("supporting_evidence"), contradicting=v.get("contradicting_evidence"),
                    stop_reason="COMPLETED", extra={"claim_type": v.get("claim_type")})
    else:
        v, fv, base = state["model_verdict"], state["financial_verification"], _base(state)
        key = {"contradiction_aware": "contradiction", "self_reflection": "reflection"}.get(kind)
        if kind == "financial_verification":
            extra = base
        elif kind == "contradiction_aware" and not run.cfg["contradiction"]["enabled"]:
            extra = {**base, "contradiction": {"enabled": False}}
        else:
            extra = {**base, key: state.get("investigation")}
        if "final_verdict" in state:
            args = dict(initial_label=fv["label"], label=state["final_verdict"], reasoning=state.get("reasoning", ""),
                        supporting=state["final_supporting"], contradicting=state["final_contradicting"],
                        stop_reason="COMPLETED", extra=extra)
        else:
            args = dict(initial_label=fv["label"], label=fv["label"], reasoning=v.get("reasoning_summary", ""),
                        supporting=fv["supporting"], contradicting=fv["contradicting"],
                        stop_reason=state.get("stop_reason", "COMPLETED"), error=err, extra=extra)
    pred, trace = build_prediction(run, **args)
    if kind in ("contradiction_aware", "self_reflection") and "financial_verification" in state and (
            kind == "self_reflection" or run.cfg["contradiction"]["enabled"]):
        pred["second_look_record"] = second_look_record(state, pred, kind)
    step = _step(runtime, "finalize", t0, label=pred["predicted_label"], stop_reason=pred["stop_reason"])
    trace["graph"] = {"framework": "langgraph", "kind": kind, "execution_trace": state.get("execution_trace", []) + step["execution_trace"],
                      "nodes_visited": [s["node"] for s in state.get("execution_trace", [])] + ["finalize"],
                      "failed_stage": state.get("failed_stage")}
    return {"prediction": pred, "trace": trace, "final_verdict": pred["predicted_label"], "verdict_changed": pred["verdict_changed"],
            "evidence_ids": [c["evidence_id"] for c in pred["citations"] if c["valid"]], "stop_reason": pred["stop_reason"],
            "token_usage": pred["token_usage"], "latency_ms": pred["latency_ms"], "estimated_api_cost": pred["estimated_cost_usd"],
            **step}
