"""Additional baseline -- RAG + deterministic verification + self-reflection.

Same initial stage and numeric verification as A2, then the model critiques
its own verdict and revises it -- with NO new retrieval and NO numeric
checks of its own. It gets the same number of extra LLM calls as A3 (one
to list up to N weaknesses, one to reassess them and give the final
verdict), the same output cap, and the same deterministic guards. If A3
beats this baseline, the gain is attributable to contradiction-directed
evidence retrieval rather than to simply giving the model a second look.

Orchestrated as a LangGraph StateGraph: see graphs/build.py (graph shape)
and graphs/nodes.py (stage logic, entry/exit conditions).
"""


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    from graphs import run_graph  # imported here: graphs.nodes imports experiments.pipeline

    return run_graph("self_reflection", claim, cfg, llm, run_id)
