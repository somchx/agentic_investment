"""Approach 2 -- RAG + deterministic financial verification (baseline 2).

Financial claim -> SEC retrieval -> LLM -> deterministic numeric
verification -> final verdict.

Identical to A1 up to the model's verdict; then every numeric assertion the
model extracted is recomputed from XBRL facts filed by the cutoff (engine/
numeric.py, reusing the app's XBRL extraction), and the deterministic
reconcile rule decides the final label. No counter-evidence search.
Purely qualitative claims have no assertions, so the stage is a no-op.
"""

from .pipeline import ClaimRun, NoStructuredOutput, StageBudgetExhausted, build_prediction, initial_stage, numeric_evidence, numeric_stage


def verified_initial(r: ClaimRun) -> dict:
    """A2's whole pipeline; also the initial stage of A3 and SR."""
    v = initial_stage(r)
    label, rule, checks = numeric_stage(r, v)
    sup, con = list(v.get("supporting_evidence") or []), list(v.get("contradicting_evidence") or [])
    if rule == "NUMERIC_FALSE":
        con += numeric_evidence(checks, "FALSE")
    elif rule == "NUMERIC_ALL_TRUE":
        sup += numeric_evidence(checks, "TRUE")
    return {"verdict": v, "label": label, "rule": rule, "checks": checks, "supporting": sup, "contradicting": con}


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    r = ClaimRun(claim, cfg, llm, run_id)
    try:
        s = verified_initial(r)
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return build_prediction(r, initial_label=None, label="INSUFFICIENT_EVIDENCE", reasoning="", supporting=[],
                                contradicting=[], stop_reason="NO_VERDICT", error=str(e))
    v = s["verdict"]
    return build_prediction(r, initial_label=s["label"], label=s["label"], reasoning=v.get("reasoning_summary", ""),
                            supporting=s["supporting"], contradicting=s["contradicting"], stop_reason="COMPLETED",
                            extra={"claim_type": v.get("claim_type"), "llm_label": v["label"], "numeric_rule": s["rule"],
                                   "numeric_statuses": [c["status"] for c in s["checks"]]})
