"""A3 v2 -- contradiction-aware verification with an Evidence Reviewer and a
deterministic Reconciliation Guard. Development version: not run on any
labelled split yet, no results.

Built beside v1, never inside it. A1 / A2 / A3 v1 code (engine/, experiments/,
graphs/) is imported, not edited, so the frozen v1 run, its LLM cache keys and
its code checksums are untouched. Design source: the v1 error analysis
(steps 1-5); pattern choice: Sequential + Review and Critique + tool-using
agent. No feedback loop, coordinator or swarm.

    retrieve -> initial verdict -> numeric verification (= A2)
      -> analyze_claim (interface; default = whole-claim + numeric assertions)
      -> generate_hypotheses -> counter_investigation           (v1 nodes)
      -> evidence_review   (deterministic checks, then an isolated LLM review)
      -> reconcile_v2      (v1 reconciliation + the review table)
      -> apply_guards      (v1 guards, unchanged)
      -> reconciliation_guard (deterministic, evidence-grounded)
      -> finalize          (v1)
"""

A3V2_VERSION = "a3v2-0.1.0-dev"
REVIEW_PROMPT_VERSION = "a3v2-review-prompts-0.1"
GUARD_VERSION = "a3v2-guard-0.1"
GRAPH_VERSION = "langgraph-claims-a3v2-0.1"
KIND = "contradiction_aware_v2"
