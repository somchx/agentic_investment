# ReasonCheck Research — financial claim verification experiments

**Study:** *Evaluating Contradiction-Aware Agentic AI for Evidence-Grounded Financial Claim Verification*

**Research question:** Does contradiction-aware investigation improve the accuracy and evidence grounding of
financial claim verification compared with conventional RAG and RAG with deterministic financial verification?

This directory is the research pipeline. It runs without the website, the database or the portfolio
workflow. The ReasonCheck application (`backend/`, `frontend/`) stays the demo and is unchanged; the research
engine imports the application's deterministic core rather than copying it (see *Reuse* below).
Method details: [`METHODOLOGY.md`](METHODOLOGY.md).

## Status — read first

| Item | State |
|---|---|
| Pipeline, four approaches, metrics, statistics, notebooks, tests | Implemented. Approaches run as **LangGraph** `StateGraph`s (`graphs/`). 154 automated tests pass offline, including executing all eight notebooks. |
| Readiness audit | [`docs/readiness_audit.md`](docs/readiness_audit.md) — reusable parts, gaps, leakage sources, validity risks. |
| Development claims | 24 claims (AAPL / MSFT / AMZN × numerical / interpretive / ambiguous), **unlabelled** (pilot / debugging only). |
| Gold (held-out) claims | 150 claims (`gold-v0.1`): 10 companies × 5 numerical / 5 interpretive / 5 ambiguous. Five ask about a period not yet reported at their cutoff (future-data leakage checks). |
| Reference labels | **Final Gold v3, approved** (`datasets/workbooks/Final_Gold_v3_approved.xlsx`, exported from the researcher's Google Sheet; read only by `engine/reference.py`): 68 SUPPORTED / 38 CONTRADICTED / 44 INSUFFICIENT_EVIDENCE (7 labels differ from v1, see `engine/reference.py`). Provenance: three LLMs annotated (Fleiss' κ = Krippendorff's α = 0.634), AI-assisted adjudication, researcher review. **Not independent human gold**; 71/150 reference evidence items are corroborated table values rather than verbatim quotes; all 150 marked human review Approved. Validate with `scripts/validate_gold.py`. |
| Real model runs | **None yet.** Mock runs (keyword heuristic LLM) exercise the plumbing only. No accuracy number in this repository is a research result. |
| Paid API calls made while building this | None. |

## Layout

```text
research/
├── engine/                  shared research engine (Python modules, no notebook logic)
│   ├── schema.py            ClaimInput (whitelisted model input), dataset / annotation / adjudication records
│   ├── datasets.py          loading, dev/gold separation, gold assembly (agreement / adjudication), Cohen's κ
│   ├── corpus.py            point-in-time SEC corpus, filing cleaning, BM25 passage retrieval, corpus build
│   ├── numeric.py           deterministic numeric verification over XBRL (reuses backend xbrl_extract)
│   ├── prompts.py           system prompt, instructions, structured-output tools (PROMPT_VERSION)
│   ├── llm.py               response cache, offline / mock / live modes, paid-run approval, budget guard
│   ├── config.py            experiment configs: merge, freeze, hash, fairness checks
│   ├── runner.py            cost plan, resumable immutable runs, integrity check
│   ├── metrics.py           accuracy, P/R/F1, macro-F1, confusion, evidence P/R, unsupported rate, cost,
│   │                        second-look transitions, citation validity, leakage / fiscal-period rates
│   ├── reference.py         Final Gold reference labels: load (read-only), provenance, validation (evaluation only)
│   ├── stats.py             McNemar (exact + χ²), paired bootstrap CIs
│   ├── synthetic.py         SYNTHETIC data for self-checks only (never results)
│   └── notebook.py          display helpers for the notebooks
├── graphs/                  LangGraph orchestration of the approaches
│   ├── state.py             ClaimState (typed graph state) and GraphContext (per-run objects)
│   ├── nodes.py             one node per stage, with entry / exit conditions
│   └── build.py             graph per approach, conditional edges, retry policy, run_graph()
├── experiments/             the approaches
│   ├── pipeline.py          stage functions: retrieval, initial verdict, numeric stage, citation validation, guards, trace
│   ├── conventional_rag.py  A1          (each module: description + run() -> graphs.run_graph)
│   ├── financial_verification.py  A2
│   ├── contradiction_aware.py     A3 (proposed)
│   └── self_reflection.py   SR control
├── configs/                 main_comparison.json, ablation_contradiction.json
├── datasets/                development_cases.jsonl, gold_claims.jsonl (claims only), annotations/,
│                            annotation_guidelines.md, corpus_manifest.json, workbooks/ (Final_Gold_v3_approved.xlsx, earlier versions and the
│                            annotator workbooks -- evaluation only), llm_annotations/
├── docs/                    readiness_audit.md, architecture.md, reproducibility.md, error_analysis_report.md,
│                            technical_issues_v1.md, handoff_v1.md (start here for v1)
├── notebooks/               01 gold validation, 02 LangGraph pilot, 03 baseline comparison, 04 contradiction analysis,
│                            05 evaluation metrics, 06 statistical analysis (01–06 generated without outputs),
│                            07 LLM annotator comparison, 08 post-experiment error analysis
├── results/
│   ├── runs/<run_id>/       manifest, predictions.jsonl, traces/, status, corpus, SHA256SUMS (read-only when complete)
│   ├── llm_cache/           every model response, keyed by request hash (makes runs reproducible / resumable)
│   ├── metrics/  figures/   tables and charts written by notebooks 05 / 04 / 01 / 08
│   ├── freeze/<run_id>.json checksums + recomputed scores of a finished run (scripts/freeze_experiment.py)
│   ├── DEPRECATED.json      frozen result files that must not be cited, with provenance and replacement
├── scripts/                 build_corpus, validate_gold, run_experiment, build_notebooks, execute_notebooks,
│                            annotation_workbook, insufficient_adjudication, freeze_experiment,
│                            discordant_review_workbook
└── tests/                   pytest suite (offline, mock LLM; network access fails the test)
```

The task brief suggested a top-level `core/` package. The application's core already lives in
`backend/app/core/` and the app imports it by module name; moving it would risk the demo for no gain, so the
research engine adds `backend/app/core` to `sys.path` and calls it in place.

## Setup

```bash
python3 -m venv research/.venv
research/.venv/bin/pip install -r research/requirements.txt   # backend deps + pandas, matplotlib, nbclient, pytest
```

The SEC documents for the development claims are already in the application's SEC cache
(`backend/app/data/cache`). For new claims:

```bash
research/.venv/bin/python research/scripts/build_corpus.py              # report what is eligible / missing (offline)
research/.venv/bin/python research/scripts/build_corpus.py --download   # fetch missing filings from SEC EDGAR (free)
```

## Running

```bash
cd research
# tests (offline, ~25 s, includes executing all eight notebooks)
.venv/bin/python -m pytest tests -q

# validate the reference labels against the claims and the SEC corpus (offline)
.venv/bin/python scripts/validate_gold.py

# cost plan only -- never calls the API
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --plan

# whole pipeline with the MOCK LLM (no credentials; output is NOT a result)
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --mode mock

# from cached model responses only (free; stays incomplete where nothing is cached)
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --mode offline

# PAID: real Claude calls. Requires ANTHROPIC_API_KEY and the exact phrase printed by --plan
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --mode live \
    --approve "I approve up to 192 paid Claude API calls costing at most \$21.60"
#   add --claims DEV-AAPL-01,DEV-MSFT-04 for a small pilot, --resume <run_id> after an interruption

# OFFICIAL held-out evaluation (only after prompts / configs are frozen; see docs/reproducibility.md)
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --split gold --allow-gold --plan

# notebooks
.venv/bin/jupyter lab notebooks/        # or execute all: .venv/bin/python scripts/execute_notebooks.py
```

Notebook 03 has the same modes (`RUN_MODE = "load" | "mock" | "offline_cache" | "live"`, default `load`).

### Cost and safety controls

- Default mode never reaches the paid API: `offline` raises on a cache miss; `mock` uses no network.
- `live` needs a `PaidRunApproval`, created only from the exact phrase that states the call and dollar cap.
  The `BudgetGuard` refuses any call that could exceed the approved dollars or call count.
- Per-claim limits: LLM calls, input tokens, retrieval queries (config `budget`); output cap per call.
- Every response is cached before it is used; predictions are appended + fsynced per claim. An interrupted
  run is resumed with `--resume` and repeats no paid call.
- Mock runs are prefixed `MOCK-`, flagged `is_mock` in every row, and notebooks show a red banner.

Current plans at the configured model's prices: 24 development claims × 4 approaches ≤ 192 calls, upper bound
$21.60, typical ≈ $3.60; 150 gold claims × 4 approaches ≤ 1,200 calls, upper bound $135.00, typical ≈ $22.50 (the
initial call is identical across approaches and served from cache after the first, so the real count is lower).
Recommended first step: the notebook 02 pilot on 3 development claims.

## The approaches

| | Pipeline | LLM calls / claim |
|---|---|---|
| **A1** Conventional RAG | claim → BM25 retrieval over eligible 10-K/10-Q → LLM verdict | 1 |
| **A2** RAG + numeric verification | A1 → deterministic XBRL check of the model's numeric assertions → rule-based final label | 1 |
| **A3** Contradiction-aware | A2 → model writes challenge questions → new-passage retrieval + numeric checks per challenge → reconciliation → guards → final | 3 |
| **SR** Self-reflection | A2 → self-critique → revision on the same evidence → same guards → final | 3 |

Each approach is a LangGraph `StateGraph` (shapes in [`docs/architecture.md`](docs/architecture.md)); the nodes
wrap the stage functions in `experiments/pipeline.py`, so the LangGraph port produced byte-identical predictions
and traces on all 216 mock (approach, claim) pairs it was checked against. The initial request is byte-identical
in all four, so differences come only from the stages each adds.
`contradiction.enabled=false` turns A3 into A2 exactly (tested); `counter_retrieval` / `counter_numeric_checks`
ablate its two evidence sources (`configs/ablation_contradiction.json`).

## Reuse of the application

| Application component (`backend/app/core`) | Used for |
|---|---|
| `sec_client` (cache, CIK map) | document / submissions / company-facts files |
| `xbrl_extract` (tag migration, restatements, MSFT Q4 = FY − 9M) | every number the numeric verifier computes |
| `evidence_ledger` (`EvidenceLedger`, `EvidenceUnit`) | evidence ids, provenance, quote normalisation |
| `investigation_engine.AnthropicClient` | the live Messages API call |
| `agent_config` (model snapshot, temperature, pricing, hashing) | defaults and cost estimates |
| `tools.check_reason_status` | cross-checked in tests: research revenue growth == app rule-engine value |

The app's `InvestigationEngine` (free-form tool loop) and its B0–B3 baselines for thesis monitoring are left as
they are; the claim-verification approaches use fixed stages so that each approach differs by one mechanism.

## Known limitations

See METHODOLOGY.md §10 and [`docs/readiness_audit.md`](docs/readiness_audit.md) §5. In short: reference labels
are LLM-annotated, AI-adjudicated and researcher-reviewed (not independent human gold), with low agreement on
interpretive / ambiguous claims; reference evidence quotes are not verbatim-verified, so passage-level evidence
precision / recall are not computed; one annotator (Claude Opus 5.5) shares a vendor with the experiment model;
no real-model results yet; retrieval covers the main 10-K/10-Q document only; fiscal Q4 is derived only for
Microsoft; the model may know post-cutoff facts from pre-training; the mock LLM is a keyword heuristic.
