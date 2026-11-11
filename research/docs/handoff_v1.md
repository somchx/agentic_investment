# Handoff: claim-verification experiment v1

**Experiment.**
- Approaches: A1 conventional RAG, A2 RAG + deterministic XBRL numeric verification, A3 contradiction-aware
  second look.
- Data: 150 gold claims (10 companies × 15; 50 each Numerical / Interpretive / Ambiguous).
- Model: `claude-sonnet-4-5-20250929`, temperature 0.
- Prompts: `claim-prompts-1.0`; graph: `langgraph-claims-1.0` (LangGraph 1.2.20).
- Reference: Final Gold v3 (approved), sha256 `e47897c4…`.

**Runs and Git tag.**
- Canonical run `claimverif-main-v1-20261110T104207Z` is an offline replay of live run
  `claimverif-main-v1-20261110T091252Z`. The live run spent $12.25; the whole project has spent $12.51 on API
  calls.
- Git tag: `claimverif-main-v1-frozen`.

## 1. Integrity: verified

- **Freeze record.** `results/freeze/claimverif-main-v1-20261110T104207Z.json` (read-only) holds the checksums
  of:
  - both run directories (`SHA256SUMS` intact);
  - the config;
  - prompts, with no drift between recorded and current hashes;
  - model settings;
  - gold claims, development claims, corpus manifest and reference workbook;
  - both adjudication variants and their source workbooks;
  - all 450 cached model responses (0 missing);
  - the result files;
  - the scores recomputed from the predictions.
- **Check it again** with `scripts/freeze_experiment.py --run claimverif-main-v1-20261110T104207Z --verify`.
  It reports 0 changed and 0 removed items. Files added since the freeze (the error-analysis outputs) are listed
  but do not fail the check.
- **Code and data the run used.**
  - The 29 code files whose hashes the run manifest records match the tagged commit, except `engine/reference.py`
    and `engine/stats.py`. Those two gained analysis-only functions after the run; scoring of strict results is
    unchanged and recomputed identically.
  - All 10 XBRL company-facts files match the manifest. The GOOGL snapshot, `CIK0001652044.json`, is committed
    with this tag.
  - The SEC filing texts (`backend/app/data/cache/doc_*.htm`, 145 MB) are not committed. Each is listed with its
    sha256 in `datasets/corpus_manifest.json` and can be re-downloaded free of charge with
    `scripts/build_corpus.py --download`.
- **No modification, no paid calls.** No gold label, prediction, prompt or configuration was changed after the
  run, and no model was called after the live run.
- **Tests.** 154 offline tests pass.
- **Deprecated file.** `results/metrics/claimverif-main-v1-20261110T104207Z__adjudicated_accuracy.csv` is
  mislabelled (it holds the lenient scores) and must not be cited.
  - It is inside the frozen set, so it is kept unchanged.
  - It is registered in `results/DEPRECATED.json` with its sha256, provenance and replacement
    (`__accuracy_by_scoring.csv`).
  - Notebook 08 shows the warning and asserts that `__accuracy_by_scoring.csv` equals the frozen scores.

## 2. Main results (strict scoring; primary)

| | A1 | A2 | A3 |
|---|---|---|---|
| Accuracy (n = 150) | 62.7% | 68.7% | 64.0% |
| Numerical / Interpretive / Ambiguous | 76 / 62 / 50% | 94 / 60 / 52% | 96 / 58 / 38% |
| Estimated cost per claim | $0.020 | $0.020 | $0.082 |
| Mean latency per claim (live) | 9.9 s | 9.9 s | 34.5 s |

- **A1 → A2:** +6.0 pts, 95% paired bootstrap CI [+2.0, +10.7], McNemar exact p = 0.012 (10 vs 1 discordant).
- **A2 → A3:** −4.7 pts, CI [−10.7, +1.3], p = 0.21 (8 vs 15 discordant). Not significant.
- **Leakage:** no evidence filed after a claim's cutoff was used by any approach.

## 3. Sensitivity: how decisive answers on INSUFFICIENT_EVIDENCE claims are scored

| Scoring | Source (provenance verified by re-reading the workbook) | A1 | A2 | A3 | A2 → A3 | A1 → A2 |
|---|---|---|---|---|---|---|
| strict (primary) | — | 62.7% | 68.7% | 64.0% | −4.7, p = 0.21 | +6.0, p = 0.012 |
| adjudicated | `INSUFFICIENT_adjudication_filled.xlsx`, 5/44 acceptable | 64.0% | 70.0% | 66.0% | −4.0, p = 0.29 | +6.0, p = 0.012 |
| lenient (upper bound) | `INSUFFICIENT_adjudication__…104207Z.xlsx`, 44/44 | 78.0% | 84.0% | 85.3% | +1.3, p = 0.77 | +6.0, p = 0.012 |

- **Separate variants.** Each variant is a separate file (`datasets/adjudication/…__{adjudicated,lenient}.jsonl`)
  and records its source workbook and adjudicator.
- **Report lenient as an upper bound only.** A provenance-valid citation does not show that the answer is
  supported.

## 4. Error analysis findings

Details are in `docs/error_analysis_report.md` and notebook 08.

**Observed:**
1. **All A2/A3 differences come from the second look.** A3 starts from A2's final verdict on 150/150 claims. It
   changed 31 verdicts: 8 wrong → right, 15 right → wrong, 8 still wrong.
2. **Changes concentrate on Ambiguous claims:** 11 harmful and 4 helpful. Numerical claims are unaffected.
3. **20 of 31 changes resolved an INSUFFICIENT_EVIDENCE verdict.** Of these 20, 5 matched the reference, 10 were
   claims the reference calls INSUFFICIENT_EVIDENCE, and 5 took the opposite label. Overconfident decisive
   answers rose from 23 to 32, and over-abstentions fell from 16 to 9.
4. **The contradiction stage changed verdicts it had not challenged.** Of 435 hypotheses, 44% found no relevant
   evidence, 39% were refuted and 16% were supported. 7 changes happened with no supported challenge.
5. **Citation integrity in A3:**
   - 7 of 18 quoted XBRL / derived citations are misattributed.
   - 8.2% of citations on claims stating a period come from another period (A1/A2: 0%).
6. **A3 costs about 4×** per claim and 4.6× per correct answer.

**From the manual review (AI analyst, awaiting your confirmation):**
- In the 15 harmful changes, the counter-evidence was genuine or partly genuine in 14.
- The interpretation was wrong in 13 and debatable in 2.
- The final citations entailed the new verdict in 0.

**Hypotheses (not tested):**
- The second look acts as a second retrieval round rather than falsification.
- Evaluative predicates without a criterion become decisive once more evidence is in hand.
- The guards check provenance, not entailment or period.
- The reference reserves INSUFFICIENT_EVIDENCE for ambiguous claims, so being more decisive is penalised.
- With 23 discordant pairs, the study has limited power.

## 5. Researcher review items (your action)

| Item | File | What to do |
|---|---|---|
| Confirm the 23 discordant-case classifications | `datasets/error_analysis/discordant_case_review__<run>.xlsx` | Fill only `researcher_confirmed` (CONFIRMED / PARTIALLY_CONFIRMED / REJECTED / UNSURE) and `researcher_note`, then run `scripts/discordant_review_workbook.py import <file> --run <run_id>`. The CSV keeps the AI-analyst columns unchanged. |
| Look closely at AAPL-12, KO-11, MSFT-13 | same workbook, orange rows at the top | The analyst rated the interpretation DEBATABLE, so the reference may be arguable. If you think a reference label should change, write it in the note. That does not change v1 results, which stay scored against v3-approved. |
| Record adjudication provenance | `datasets/adjudication/` | Note in the thesis whether AI assistance was used for the 10:03 (`_filled`) and 10:13 (all-accept) decisions, and why they differ. |
| Optional: the stale file | `results/DEPRECATED.json` | It is excluded from reporting. You may delete it in a later commit, but `--verify` would then report it as removed. |

## 6. Known technical limitations

Full details and proposed fixes are in `docs/technical_issues_v1.md`.

- **Unchecked XBRL quotes.** Quotes on XBRL and derived-metric citations are not validated; any text passes.
- **No period check on citations.** Citations are not checked against the claim's fiscal period.
- **Validity is not entailment.** A single provenance-valid citation is enough to change a verdict, with no
  check that it entails the new label.
- **Asymmetric guard.** A move to INSUFFICIENT_EVIDENCE needs no evidence, and a move away from it needs only
  one valid citation.
- **Truncated reconciliations.** 5/150 A3 reconciliations were truncated at 1,500 output tokens, so A3 kept the
  initial verdict on those claims.
- **The reference is not independent human gold.** It was annotated by three LLMs, with AI-assisted adjudication
  and researcher review (initial κ = α = 0.634).
- **Single run and setup.** One live run, one model snapshot, one prompt version, 10 companies. Run-to-run
  variance is not estimated.
- **Latency.** It comes from a single sequential live run; costs use list prices.

## 7. Recommended follow-up experiments

None of these was run, and each paid run needs your explicit approval and a cost cap.

1. **Confirm the review first.** It costs nothing and is needed before the Discussion cites mechanism counts.
2. **Ablation: second look on decisive verdicts only.** Skip A3 when A2 says INSUFFICIENT_EVIDENCE. This tests
   whether the losses come from resolving abstentions. It costs less than the full A3 run (about 37 fewer
   claims).
3. **A3-v2 with the proposed guards.** Add XBRL quote and period validation, a decidability check, an
   entailment-linked change rule and a symmetric guard. Develop and test on the development split first, then
   pre-register and run once on gold.
4. **Self-reflection control (SR) on gold.** Same number of extra calls, no new evidence. This separates
   "more evidence" from "more reasoning" (estimated about $8–9).
5. **Variance.** Repeat the A2 and A3 live runs at least twice with separate caches.
6. **Independent human labels on a subset.** For example, the 50 Ambiguous claims, to measure how much of the
   A2/A3 gap depends on the reference.

## 8. Where things are

| | Path |
|---|---|
| Run (predictions, traces, manifest) | `results/runs/claimverif-main-v1-20261110T104207Z/`; live: `…091252Z/` |
| Freeze record | `results/freeze/claimverif-main-v1-20261110T104207Z.json` |
| Deprecated artifacts | `results/DEPRECATED.json` |
| Notebooks | `notebooks/03`–`06` (results), `08_error_analysis.ipynb` |
| Tables / figures | `results/metrics/claimverif-main-v1-20261110T104207Z__*.csv`, `results/figures/*_claimverif-main-v1-20261110T104207Z.png` |
| Reports | `docs/error_analysis_report.md`, `docs/technical_issues_v1.md`, this file |
| Methodology / reproduction | `METHODOLOGY.md`, `docs/reproducibility.md` |
