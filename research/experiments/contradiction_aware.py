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

Orchestrated as a LangGraph StateGraph: see graphs/build.py (graph shape)
and graphs/nodes.py (stage logic, entry/exit conditions).
"""


def run(claim, cfg, llm, run_id=None) -> tuple[dict, dict]:
    from graphs import run_graph  # imported here: graphs.nodes imports experiments.pipeline

    return run_graph("contradiction_aware", claim, cfg, llm, run_id)
