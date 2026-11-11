# Reproducibility guide

How to reproduce, or extend, the claim-verification experiments. Commands run from `research/`.

## 1. Environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # backend deps, pandas, matplotlib, nbclient, openpyxl, langgraph, pytest
.venv/bin/python -m pytest tests -q            # offline; must pass before any run
```

Versions that affect results are recorded in every run manifest: engine, prompts (with hashes of every prompt and
tool schema), numeric / reconcile rules, retrieval and cleaning, graph version and installed LangGraph version,
model id, temperature, pricing version, git commit + dirty flag, and the sha256 of every research and relevant
backend source file.

## 2. Data

| Input | Where | Integrity |
|---|---|---|
| Gold claims (claims only) | `datasets/gold_claims.jsonl` | sha256 in each run manifest |
| Development claims | `datasets/development_cases.jsonl` | sha256 in each run manifest |
| Reference labels | `datasets/workbooks/Final_Gold_v3_approved.xlsx`, sheet `Final Gold 150` (v1 layout still readable) | sha256 in `load_reference()["provenance"]`; recorded by `scripts/validate_gold.py` |
| SEC filings | `backend/app/data/cache/doc_*.htm`, listed in `datasets/corpus_manifest.json` | sha256 per document; per-run `corpus.json` |
| XBRL company facts | `backend/app/data/cache/CIK*.json` | sha256 per company in each run manifest |

Rebuild or check the corpus offline with `scripts/build_corpus.py` (`--download` fetches missing filings from
SEC EDGAR; free). Validate the reference with `scripts/validate_gold.py` (exit code 1 on any error).

The XBRL company-facts files are snapshots taken when the cache was filled. Facts are filtered by `filed <=
cutoff`, so later snapshots add only later filings — but keep the cached files (and their hashes) with the
results.

## 3. Freeze before the official run

1. Finish all prompt / config development on development claims only (notebook 02, `--split development`).
2. Bump `PROMPT_VERSION` if any prompt or tool schema changed; commit.
3. Run the full test suite and `scripts/validate_gold.py`.
4. Commit everything (the manifest records `dirty: true` otherwise) and tag the commit.
5. Record the plan: `scripts/run_experiment.py configs/main_comparison.json --split gold --allow-gold --plan`.

## 4. Run

```bash
# paid; the phrase must match the plan exactly
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --split gold --allow-gold \
    --mode live --approve "I approve up to N paid Claude API calls costing at most $X.XX"
# interrupted? resume without repeating a paid call
.venv/bin/python scripts/run_experiment.py configs/main_comparison.json --split gold --allow-gold \
    --mode live --approve "..." --resume <run_id>
```

Each response is stored in `results/llm_cache/` before use, keyed by the full request. Re-running in
`--mode offline` replays the run from the cache with no API access. A completed run directory is made read-only
and checksummed (`SHA256SUMS`; `engine.runner.verify_run_integrity`).

For run-to-run variance, repeat the live run (a new run id each time). Because the cache would replay identical
requests, repeated runs need a separate cache directory (`CachedLLM(cache_dir=...)`).

## 5. Analyse

Notebooks 03–06 load the newest complete real run (or a given `RUN_ID`) and read reference labels through
`engine.notebook.load_gold_labels()`. They write tables to `results/metrics/<run_id>__*.csv` and figures to
`results/figures/`. Report:

- the reference provenance (`reference_banner()` prints it) and the initial agreement (κ = α = 0.634);
- accuracy / macro-F1 with paired bootstrap CIs and the exact McNemar p-value for A2 vs A3 (main) and SR vs A3;
- per-category results as exploratory;
- second-look transitions and counter-evidence retrieval success;
- evidence integrity (citation validity, future-data leakage = 0, fiscal-period mismatch rate);
- tokens, calls, retrieval queries, latency and cost per approach, with the unequal-budget caveat.

## 6. Freeze, then analyse errors

After the official run, and before any error analysis:

```bash
.venv/bin/python scripts/freeze_experiment.py --run <run_id> --source-run <live_run_id>   # once; read-only record
.venv/bin/python scripts/freeze_experiment.py --run <run_id> --verify                     # exit 1 if anything frozen changed
```

The record (`results/freeze/<run_id>.json`) holds the checksums of the run directories, configuration, prompts
(and whether the current code's prompt hashes still match), model settings, datasets, reference, adjudication
variants with their source workbooks, every cached response the run replays from, and the result files, plus the
strict / adjudicated / lenient scores recomputed from the predictions. Notebook 08 re-verifies it first, then
analyses A2 vs A3 claim by claim, A3's initial vs final verdicts, error types, the counter-evidence and citation
audits, and cost / latency (latency from the live run's per-request timings). Findings:
`docs/error_analysis_report.md`; known defects and v2 proposals: `docs/technical_issues_v1.md`.

Researcher confirmation of the discordant-case review: `scripts/discordant_review_workbook.py export --run <run_id>`
writes the workbook; `import <filled.xlsx> --run <run_id>` copies only `researcher_confirmed` / `researcher_note`
back into `datasets/error_analysis/discordant_case_review__<run_id>.csv`. A frozen result file that must not be
cited is never edited: it is registered in `results/DEPRECATED.json` instead.

## 7. What must not change between approaches

Model and temperature, retrieval settings, per-claim budgets (`config.fairness_problems` refuses a config that
breaks this), claim set, corpus, cutoffs, label definitions and evaluation code. The initial model request is
byte-identical across A1–A3 and SR (tested).
