"""Additional baseline -- RAG + deterministic verification + self-reflection.

Same initial stage and numeric verification as A2, then the model critiques
its own verdict and revises it -- with NO new retrieval and NO numeric
checks of its own. It gets the same number of extra LLM calls as A3 (one
to list up to N weaknesses, one to reassess them and give the final
verdict), the same output cap, and the same deterministic guards. If A3
beats this baseline, the gain is attributable to contradiction-directed
evidence retrieval rather than to simply giving the model a second look.
"""

from engine.prompts import REVISION_INSTRUCTION, REVISION_TOOL, SELF_CRITIQUE_INSTRUCTION, SELF_CRITIQUE_TOOL

from .contradiction_aware import initial_summary
from .financial_verification import verified_initial
from .pipeline import ClaimRun, NoStructuredOutput, StageBudgetExhausted, build_prediction, finish_revision


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
    n = cfg["reflection"]["max_items"]
    reflection = {"enabled": True, "weaknesses": []}
    try:
        critique = r.ask("self_critique", SELF_CRITIQUE_INSTRUCTION.format(n=n),
                         {"initial_verdict": initial_summary(s), "max_hypotheses": n}, SELF_CRITIQUE_TOOL)
        weaknesses = (critique.get("weaknesses") or [])[:n]
        for i, w in enumerate(weaknesses):
            w["weakness_id"] = str(w.get("weakness_id") or f"W{i + 1}")
        reflection["weaknesses"] = weaknesses
        r.stages.append({"stage": "self_critique", "weaknesses": weaknesses})
        final = r.ask("revision", REVISION_INSTRUCTION,
                      {"initial_verdict": {"label": s["label"], "claim_type": v.get("claim_type")}, "weaknesses": weaknesses},
                      REVISION_TOOL)
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return build_prediction(r, initial_label=s["label"], label=s["label"], reasoning=v.get("reasoning_summary", ""),
                                supporting=s["supporting"], contradicting=s["contradicting"],
                                stop_reason="BUDGET_EXHAUSTED_AFTER_INITIAL" if isinstance(e, StageBudgetExhausted) else "NO_FINAL_VERDICT",
                                error=str(e), extra={**base, "reflection": reflection})

    g, label, rule, sup, con = finish_revision(r, s, final)
    reflection.update({"assessments": g["assessments"], "model_final_label": final.get("label"),
                       "model_says_changed": final.get("verdict_changed"), "change_reason": final.get("change_reason"),
                       "guard_reverted": g["reverted"], "final_numeric_rule": rule,
                       "challenges_supported": sum(1 for a in g["assessments"] if a["assessment"] == "CHALLENGE_SUPPORTED"),
                       "invalid_challenges": sum(1 for a in g["assessments"] if a["flag"])})
    r.stages.append({"stage": "revision", "label": label, "guard_reverted": g["reverted"], "numeric_rule": rule,
                     "assessments": g["assessments"]})
    return build_prediction(r, initial_label=s["label"], label=label, reasoning=final.get("reasoning_summary", ""),
                            supporting=sup, contradicting=con, stop_reason="COMPLETED",
                            extra={**base, "reflection": reflection})
