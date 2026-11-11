"""Approach 1 -- Conventional RAG (baseline 1).

Financial claim -> SEC retrieval -> LLM -> final verdict.

The model fills the same verdict schema as every other approach (including
numeric_assertions, so the initial call is byte-identical across
approaches), but nothing checks those assertions: the model's label is the
final label.

Orchestrated as a LangGraph StateGraph: see graphs/build.py (graph shape)
and graphs/nodes.py (stage logic, entry/exit conditions).
"""


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    from graphs import run_graph  # imported here: graphs.nodes imports experiments.pipeline

    return run_graph("conventional_rag", claim, cfg, llm, run_id)
