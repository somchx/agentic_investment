"""LangGraph implementations of the claim-verification approaches.

`run_graph(kind, claim, cfg, llm, run_id)` is what experiments.RUNNERS call;
see build.py for the graph shapes and nodes.py for each node's entry and
exit conditions.
"""

import engine  # noqa: F401  (puts backend/app/core on sys.path before the nodes import the pipeline)

from .build import GRAPH_VERSION, KINDS, build_graph, mermaid, run_graph  # noqa: E402

__all__ = ["GRAPH_VERSION", "KINDS", "build_graph", "mermaid", "run_graph"]
