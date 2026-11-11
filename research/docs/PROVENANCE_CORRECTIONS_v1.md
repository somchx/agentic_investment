# Provenance corrections: Experiment v1

| | |
|---|---|
| Applies to | Experiment v1, run `claimverif-main-v1-20261110T104207Z` (offline replay of live run `claimverif-main-v1-20261110T091252Z`) |
| Frozen state | commit `f16a986`, tag `claimverif-main-v1-frozen`, freeze record `research/results/freeze/claimverif-main-v1-20261110T104207Z.json` |
| Date | 2026-11-11 |
| Status | Authoritative. Where a frozen file below disagrees with this note, this note takes precedence. |

## Scope: what these corrections change and what they do not

These are **provenance and documentation corrections only**. They correct how the experiment's process is
described: who or what produced a judgement, and how much evidence each approach consumed.

They do **not** alter any of the following:
- the frozen experimental observations;
- the reference (gold) labels;
- the predictions;
- the adjudication decisions themselves (5/44 and 44/44 ACCEPTABLE);
- the statistical tests;
- any numeric result, confidence interval, p-value, cost or latency figure.

All values reported for v1 stay as frozen:
- **Strict accuracy:** A1 62.7%, A2 68.7%, A3 64.0%.
  - A1 → A2: +6.0 points, 95% CI [+2.0, +10.7], McNemar exact p = 0.012.
  - A2 → A3: −4.7 points, 95% CI [−10.7, +1.3], p = 0.21.
- **Adjudicated accuracy:** A1 64.0%, A2 70.0%, A3 66.0%; A2 → A3 −4.0 points, p = 0.286.
- **Lenient accuracy:** A1 78.0%, A2 84.0%, A3 85.3%; A2 → A3 +1.3 points, p = 0.774.

No frozen file was edited. The files listed below keep their original wording and checksums. The corrections
take effect through this note.

## Corrected statements

1. **Adjudication was AI-assisted and approach-blinded.** The case-by-case review of decisive answers on the 44
   INSUFFICIENT_EVIDENCE claims was AI-assisted. It was not performed independently by a human researcher.
   - It was approach-blinded: answers were labelled A/B/C at random, the key was held in a separate file, and
     the model-reasoning column was removed.
   - The value `"adjudicator": "researcher"` in the frozen records is the default of the import command
     (`research/scripts/insufficient_adjudication.py:251`, `--adjudicator` default `researcher`). It is not a
     record of who made the judgements.
2. **The 5/44 accepted answers are not independent expert validation.** The adjudicated scoring is a sensitivity
   analysis based on that AI-assisted, approach-blinded review. The workbook consistency check confirms that the
   recorded decisions match their source workbook; it does not validate the decisions.
3. **The lenient variant (44/44) is a scoring assumption, not a judgement.** It accepts every decisive answer, so
   it is an upper bound. It does not record a case-by-case review.
4. **The 23 discordant-case failure classifications are AI-assisted and await researcher confirmation.** This
   covers the mechanism, counter-evidence, interpretation and entailment codes in
   `research/datasets/error_analysis/discordant_case_review__claimverif-main-v1-20261110T104207Z.csv`.
   - They are provisional codes, not ground truth.
   - `researcher_confirmed` and `researcher_note` are empty as of this note.
   - Any statement built on these codes is a hypothesis until confirmed. That includes "0 of 15 harmful changes
     were entailed", "retrieval is not the bottleneck" and "the main driver of A3's net loss".
5. **The approaches shared the initial retrieval configuration, not the total evidence budget.**
   - **Shared by A1, A2 and A3:**
     - the initial retrieval configuration (one query, top 6 passages of 1,200 characters, same filing limits);
     - a byte-identical initial model request;
     - the same per-claim caps: at most 3 LLM calls, 4 retrieval queries and 60,000 input tokens.
   - **Not shared:** actual usage. Every claim in the frozen run used the following:

   | Approach | Retrieval queries / claim | Passages retrieved / claim | LLM calls / claim | Mean input tokens / claim |
   |---|---|---|---|---|
   | A1 | 1 | 6 | 1 | 3,927 |
   | A2 | 1 (+ XBRL facts for numeric checks) | 6 | 1 | 3,927 |
   | A3 | 4 (1 initial + 3 counter-evidence) | 15 (6 initial + 9 counter-evidence) | 3 | 17,840 (≈ 4.5×) |

   - **Consequence:** A2 vs A3 compares pipelines with different evidence budgets. It cannot separate the effect
     of the contradiction procedure from the effect of seeing more evidence.
   - **Measured from:** `research/results/runs/claimverif-main-v1-20261110T104207Z/traces/*/` (tool calls) and
     `predictions.jsonl` (`token_usage`).

## Correction mapping

- **Line numbers** refer to the file as committed in `f16a986`, read with `git show f16a986:<path>`.
- **"Numeric results affected?"** asks whether any reported number changes. It is "No" in every row.
- **Paths** are relative to `research/`.

| ID | Original statement or metadata | Corrected interpretation | Affected artifact (frozen) | Reason for correction | Numeric results affected? |
|---|---|---|---|---|---|
| PC-1 | `"adjudicator": "researcher"` on all 44 rows | AI-assisted, approach-blinded review; the field is the import command's default value, not provenance | `datasets/adjudication/insufficient_alternatives__claimverif-main-v1-20261110T104207Z__adjudicated.jsonl` (all 44 rows; sha256 `cbc9d2ae…`) | Metadata was filled by a CLI default (`scripts/insufficient_adjudication.py:251`) | No |
| PC-2 | `"adjudicator": "researcher"` on all 44 rows | Accept-all scoring assumption (upper bound), not a case-by-case judgement | `datasets/adjudication/insufficient_alternatives__claimverif-main-v1-20261110T104207Z__lenient.jsonl` (all 44 rows; sha256 `f5421280…`) | Same CLI default; the variant accepts every answer by construction | No |
| PC-3 | `"adjudicators": ["researcher"]` for both variants | As PC-1 and PC-2 | `results/freeze/claimverif-main-v1-20261110T104207Z.json` lines 331–333, 343–345 | Copied from the jsonl metadata at freeze time | No |
| PC-4 | "*Adjudicated*: a decisive answer … also counts when the researcher, blind to the approach, judged its label and cited evidence ACCEPTABLE case by case" | … when an AI-assisted, approach-blinded review judged it ACCEPTABLE; not independent expert validation | `METHODOLOGY.md` lines 128–130 | Misattributes the judgement to a human researcher | No |
| PC-5 | "\| **adjudicated** \| a person, blind to the approach, judged it ACCEPTABLE case by case \|" | An AI-assisted, approach-blinded review judged it ACCEPTABLE | `scripts/build_notebooks.py` line 556; `notebooks/05_evaluation_metrics.ipynb` (scoring table in the sensitivity section) | Same misattribution, in the notebook text | No |
| PC-6 | "When a person judged those answers case by case, only 5 of 44 were acceptable." | An AI-assisted, approach-blinded review accepted 5 of 44 | `docs/error_analysis_report.md` lines 190–191 | Same misattribution | No |
| PC-7 | "Under the researcher's case-by-case adjudication, only 5 of 44 decisive answers were acceptable." | Under the AI-assisted, approach-blinded adjudication, 5 of 44 were accepted | `docs/technical_issues_v1.md` lines 143–144 | Same misattribution | No |
| PC-8 | "records its source workbook and adjudicator"; open item "Record adjudication provenance … whether AI assistance was used" | The recorded adjudicator value is not reliable (PC-1); the open item is resolved by this note | `docs/handoff_v1.md` lines 73–74, 114 | Provenance now documented | No |
| PC-9 | The 5/44 adjudication presented as a verified sensitivity analysis ("Re-read of workbook: identical") | The check verifies that records match the workbook, not that the decisions are valid; the 5/44 is AI-assisted, not expert-validated | `docs/error_analysis_report.md` lines 34–41 (§2); `docs/handoff_v1.md` lines 67–74 (§3) | Prevents reading a consistency check as validation | No |
| PC-10 | "Observed: manual review of the 23 discordant claims" and the counts built on it (genuine 10/4/1, interpreted wrong 13, entailed 0/15) | Provisional AI-assisted codes pending researcher confirmation; not observations | `docs/error_analysis_report.md` lines 113–138, 158–159 | The codes are an AI reading of the traces, not measured or confirmed | No |
| PC-11 | Interpretations stated on the 23-case codes: "Retrieval is not the bottleneck", "The investigation retrieved evidence but drew conclusions from it that the evidence did not license" | Hypotheses conditional on confirmation of the AI-assisted codes | `docs/error_analysis_report.md` lines 140, 255–257 | Conclusions rest on unconfirmed codes | No |
| PC-12 | "harmed cases: final citations entail the verdict in 0/15 (manual)", "main driver of A3's −7 net"; "Observed in v1 (manual, 23 discordant claims)" | Provisional AI-assisted coding; "main driver" is a hypothesis | `docs/technical_issues_v1.md` lines 16, 95–99 | Same | No |
| PC-13 | "From the manual review (AI analyst, awaiting your confirmation)" with counts 14 / 13 / 0 | Correctly labelled; restated here so the counts are not cited as findings before confirmation | `docs/handoff_v1.md` lines 96–99 | Reinforces existing label | No |
| PC-14 | "Same claims, corpus, cutoffs, model, retrieval and per-claim budget." | Same initial retrieval configuration and per-claim caps; actual evidence and token usage differed (A3: 15 passages, 4 queries, ≈ 4.5× input tokens) | `configs/main_comparison.json` line 3 (`description`) | "Same budget" reads as equal usage; only the caps were equal | No |
| PC-15 | "… temperature 0, the same output cap per call, the same per-claim budget" | Same per-claim caps; A3 used more retrieval and tokens than A1/A2 | `METHODOLOGY.md` line 50 | As PC-14 | No |
| PC-16 | "Same claims, corpus, cutoffs, model, temperature, prompt, retrieval config and per-claim budget for every [approach]" | As PC-15; the retrieval config shared is the initial retrieval, and A3 adds counter-evidence retrieval | `METHODOLOGY.md` lines 95–97 | As PC-14 | No |
| PC-17 | "What must not change between approaches: … retrieval settings, per-claim budgets" | Caps must not change; usage did and does differ by design | `docs/reproducibility.md` lines 98–99 | As PC-14 | No |

Already consistent with this note, and listed for completeness:
- `METHODOLOGY.md` lines 190–191 ("Unequal budget … A3 also issues up to 3 extra retrieval queries").
- `docs/error_analysis_report.md` §F6.
- `docs/handoff_v1.md` §2 cost table.

## Reporting rules from now on

- Describe the adjudicated scoring as a **sensitivity analysis based on an AI-assisted, approach-blinded
  review**. Never describe it as expert or independent validation.
- Report the lenient scoring only as an **upper bound** under an accept-all assumption, in an appendix.
- Cite the 23-case mechanism, interpretation and entailment counts only as **provisional AI-assisted codes**.
  This holds until `researcher_confirmed` is filled in the review CSV via
  `scripts/discordant_review_workbook.py import`.
- When comparing A2 and A3, state that the initial retrieval was identical but A3 used 15 passages, 4 queries and
  about 4.5× the input tokens per claim, against 6, 1 and 1× for A2.
- Notebooks 05 and 08 display the recorded `adjudicator` value (`researcher`) verbatim. Read it through PC-1.

## How this note relates to the frozen state

- This note was added in a later documentation-only commit.
- Commit `f16a986` and tag `claimverif-main-v1-frozen` are unchanged.
- `scripts/freeze_experiment.py --run claimverif-main-v1-20261110T104207Z --verify` reports no changed or removed
  frozen items.
