"""Approach 1 -- Conventional RAG (baseline 1).

Financial claim -> SEC retrieval -> LLM -> final verdict.

The model fills the same verdict schema as every other approach (including
numeric_assertions, so the initial call is byte-identical across
approaches), but nothing checks those assertions: the model's label is the
final label.
"""

from .pipeline import ClaimRun, NoStructuredOutput, StageBudgetExhausted, build_prediction, initial_stage


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    r = ClaimRun(claim, cfg, llm, run_id)
    try:
        v = initial_stage(r)
    except (NoStructuredOutput, StageBudgetExhausted) as e:
        return build_prediction(r, initial_label=None, label="INSUFFICIENT_EVIDENCE", reasoning="", supporting=[],
                                contradicting=[], stop_reason="NO_VERDICT", error=str(e))
    return build_prediction(r, initial_label=v["label"], label=v["label"], reasoning=v.get("reasoning_summary", ""),
                            supporting=v.get("supporting_evidence"), contradicting=v.get("contradicting_evidence"),
                            stop_reason="COMPLETED", extra={"claim_type": v.get("claim_type")})
