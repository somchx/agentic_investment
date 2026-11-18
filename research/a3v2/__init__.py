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
# A3 v2.1: same graph and LLM calls, plus reporting-period normalisation and
# compatibility (a3v2.periods), switched on by an approach's `periods.enabled`.
# A v2.0 config (no `periods` section) keeps v2.0 behaviour, requests and hashes.
A3V21_VERSION = "a3v2-0.2.0-dev"
REVIEW_PROMPT_VERSION_V21 = "a3v2-review-prompts-0.2"
# A3 v2.1.1: periods 1.1 (A2-numeric windows from their source facts, statement
# years, historical vs forward-looking key quotes) and API retries with backoff.
A3V211_VERSION = "a3v2-0.2.1-dev"
REVIEW_PROMPT_VERSION_V211 = "a3v2-review-prompts-0.3"
# A3 v2.2 preparation: guard 0.2 (G3 self-contained deciding findings, G6
# two-sided conflict), chosen per approach with guard.version = "0.2". Without
# it an approach keeps guard 0.1, its config hash and its behaviour.
GUARD_VERSION_V02 = "a3v2-guard-0.2"
# Guard 0.3 (exploratory): G3b -- references in a justification must be among the
# surviving final citations -- instead of G3; G6 off.
GUARD_VERSION_V03 = "a3v2-guard-0.3"
# A3 v2.2 (development, Approach A phase 1): A3 v2.1.1 + guard 0.3 (G3b) + quote
# check 1.1 for the guard + an isolated decidability classifier call whose record
# gates decisive changes (G1, optional G4) and downgrades unsupported evaluative
# SUPPORTED answers (D-sup). Switched on by decidability.name = "llm_0.1".
A3V22_VERSION = "a3v2-0.3.0-dev"
