"""Approach 2 -- RAG + deterministic financial verification (baseline 2).

Financial claim -> SEC retrieval -> LLM -> deterministic numeric
verification -> final verdict.

Identical to A1 up to the model's verdict; then every numeric assertion the
model extracted is recomputed from XBRL facts filed by the cutoff (engine/
numeric.py, reusing the app's XBRL extraction), and the deterministic
reconcile rule decides the final label. No counter-evidence search.
Purely qualitative claims have no assertions, so the stage is a no-op.

Orchestrated as a LangGraph StateGraph: see graphs/build.py (graph shape)
and graphs/nodes.py (stage logic, entry/exit conditions).
"""


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    from graphs import run_graph  # imported here: graphs.nodes imports experiments.pipeline

    return run_graph("financial_verification", claim, cfg, llm, run_id)
