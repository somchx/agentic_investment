# Historical baseline — workflow 1.0 (archived 2026-10-30)

Read-only copies of the experiment results produced **before** the workflow 2.0
refactor (shared InvestigationEngine, tool schema 2.0, Evidence Gate 2.0, prompt 2.0).
They are kept for backward comparison and must not be edited or regenerated.

| File | Produced by | Configuration |
|---|---|---|
| `full_experiment_results.json` | `src/run_full_experiment.py` | LLM-only (baseline1) vs single-shot RAG (baseline2) vs rule-based vs `run_with_llm` agent (workflow 1.0), scored against `primary_source_verification_set.json` |
| `consistency_experiment_results.json` | `src/run_consistency_experiment.py` | repeat-consistency of the 1.0 agent |
| `personalization_experiment_results.json` | `src/run_personalization_experiment.py` | investor-profile personalization, 1.0 |

Model: `claude-sonnet-4-5-20250929`, temperature 0, pricing $3 / $15 per M tokens.

`full_experiment_results.json` was copied from the working tree, which differed from
git commit `653cd8a` at archive time; `SHA256SUMS` records the exact bytes archived.

These are **not** B0–B3 results: B0–B3 (protocol `b0b3-2.0`) did not exist under
workflow 1.0. New runs go to `data/experiments/b0b3-2.0/<timestamp>/` via
`backend/scripts/run_b0b3.py` and are never compared with these files as if they
shared a configuration.
