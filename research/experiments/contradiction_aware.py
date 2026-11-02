"""Approach 3 -- Contradiction-aware agentic verification (proposed method).

Financial claim -> initial retrieval -> initial verification (= A2) ->
initial verdict -> contradiction investigation -> evidence reconciliation
-> final verdict.

Contradiction investigation: the model writes questions that could
challenge its own initial verdict, each with a search query and optionally
a figure to compute; the retriever then fetches NEW passages for each query
from the same point-in-time corpus (passages already shown are excluded),
and the numeric verifier computes the requested figures. Reconciliation:
the model assesses each challenge against that evidence and gives the final
verdict. Deterministic guards then (a) drop challenges asserted without
valid evidence, (b) keep the initial verdict if it was changed to
SUPPORTED/CONTRADICTED without a valid citation, and (c) re-apply A2's
numeric rule.

`contradiction.enabled=false` makes this exactly A2 (the ablation switch);
`counter_retrieval` / `counter_numeric_checks` switch the two evidence
sources of the investigation separately.
"""

from engine.prompts import CONTRADICTION_INSTRUCTION, CONTRADICTION_PLAN_TOOL, RECONCILIATION_INSTRUCTION, RECONCILIATION_TOOL

from .financial_verification import verified_initial
from .pipeline import ClaimRun, NoStructuredOutput, StageBudgetExhausted, build_prediction, finish_revision


def initial_summary(s: dict) -> dict:
    v = s["verdict"]
    return {"label": s["label"], "model_label": v["label"], "claim_type": v.get("claim_type"),
            "reasoning_summary": v.get("reasoning_summary"), "supporting_evidence": v.get("supporting_evidence") or [],
            "contradicting_evidence": v.get("contradicting_evidence") or [], "numeric_rule": s["rule"],
            "numeric_checks": [{"assertion": c["assertion"], "status": c["status"], "issues": c["issues"],
                                "computed": c["computed"], "evidence_ids": c["evidence_ids"]} for c in s["checks"]]}


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    r = ClaimRun(claim, cfg, llm, run_id)
    try:
        s = verified_initial(r)
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return build_prediction(r, initial_label=None, label="INSUFFICIENT_EVIDENCE", reasoning="", supporting=[],
                                contradicting=[], stop_reason="NO_VERDICT", error=str(e))
    v = s["verdict"]
    base = {"claim_type": v.get("claim_type"), "llm_label": v["label"], "numeric_rule": s["rule"],
            "numeric_statuses": [c["status"] for c in s["checks"]]}
    c = cfg["contradiction"]
    if not c["enabled"]:
        return build_prediction(r, initial_label=s["label"], label=s["label"], reasoning=v.get("reasoning_summary", ""),
                                supporting=s["supporting"], contradicting=s["contradicting"], stop_reason="COMPLETED",
                                extra={**base, "contradiction": {"enabled": False}})

    investigation = {"enabled": True, "hypotheses": [], "queries": [], "counter_evidence_ids": [], "counter_numeric": []}
    try:
        initial = initial_summary(s)
        plan = r.ask("contradiction_plan", CONTRADICTION_INSTRUCTION.format(n=c["max_hypotheses"]),
                     {"initial_verdict": initial, "max_hypotheses": c["max_hypotheses"]}, CONTRADICTION_PLAN_TOOL)
        hypotheses = (plan.get("hypotheses") or [])[:c["max_hypotheses"]]
        investigation["hypotheses"] = hypotheses
        counter, counter_numeric = [], []
        for i, h in enumerate(hypotheses):
            hid = str(h.get("hypothesis_id") or f"H{i + 1}")
            h["hypothesis_id"] = hid
            if c["counter_retrieval"] and (h.get("search_query") or "").strip():
                hits = r.search(h["search_query"], top_k=c["top_k_per_query"], exclude_shown=True, purpose=f"counter:{hid}")
                investigation["queries"].append({"hypothesis_id": hid, "query": h["search_query"], "results": [p["evidence_id"] for p in hits]})
                counter += [{"hypothesis_id": hid, **p} for p in hits]
            if c["counter_numeric_checks"] and isinstance(h.get("numeric_check"), dict):
                check = r.verify_numbers([h["numeric_check"]], f"counter:{hid}")[0]
                counter_numeric.append({"hypothesis_id": hid, "status": check["status"], "issues": check["issues"],
                                        "computed": check["computed"], "evidence_ids": check["evidence_ids"]})
        investigation["counter_evidence_ids"] = [p["evidence_id"] for p in counter]
        investigation["counter_numeric"] = counter_numeric
        r.stages.append({"stage": "contradiction_investigation", **investigation})

        final = r.ask("reconciliation", RECONCILIATION_INSTRUCTION,
                      {"initial_verdict": {"label": s["label"], "claim_type": v.get("claim_type")}, "hypotheses": hypotheses,
                       "counter_evidence": counter, "counter_numeric": counter_numeric}, RECONCILIATION_TOOL)
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return build_prediction(r, initial_label=s["label"], label=s["label"], reasoning=v.get("reasoning_summary", ""),
                                supporting=s["supporting"], contradicting=s["contradicting"],
                                stop_reason="BUDGET_EXHAUSTED_AFTER_INITIAL" if isinstance(e, StageBudgetExhausted) else "NO_FINAL_VERDICT",
                                error=str(e), extra={**base, "contradiction": investigation})

    g, label, rule, sup, con = finish_revision(r, s, final)
    investigation.update({"assessments": g["assessments"], "model_final_label": final.get("label"),
                          "model_says_changed": final.get("verdict_changed"), "change_reason": final.get("change_reason"),
                          "guard_reverted": g["reverted"], "final_numeric_rule": rule,
                          "challenges_supported": sum(1 for a in g["assessments"] if a["assessment"] == "CHALLENGE_SUPPORTED"),
                          "invalid_challenges": sum(1 for a in g["assessments"] if a["flag"])})
    r.stages.append({"stage": "reconciliation", "label": label, "guard_reverted": g["reverted"], "numeric_rule": rule,
                     "assessments": g["assessments"]})
    return build_prediction(r, initial_label=s["label"], label=label, reasoning=final.get("reasoning_summary", ""),
                            supporting=sup, contradicting=con, stop_reason="COMPLETED",
                            extra={**base, "contradiction": investigation})
