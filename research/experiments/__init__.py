"""The four claim-verification approaches compared in the study.

    conventional_rag        A1  claim -> SEC retrieval -> LLM -> verdict
    financial_verification  A2  A1 + deterministic numeric verification
    contradiction_aware     A3  A2 + contradiction investigation + reconciliation
    self_reflection         SR  A2 + LLM self-critique and revision (no new retrieval)

All four share the initial stage in experiments/pipeline.py (same prompt,
same retrieval, same verdict tool), so a difference between two approaches
comes only from the stages each adds after it.
"""

from . import contradiction_aware, conventional_rag, financial_verification, self_reflection

RUNNERS = {
    "conventional_rag": conventional_rag.run,
    "financial_verification": financial_verification.run,
    "contradiction_aware": contradiction_aware.run,
    "self_reflection": self_reflection.run,
}
