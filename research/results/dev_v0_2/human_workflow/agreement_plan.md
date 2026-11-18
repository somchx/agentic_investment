# dev-v0.2: agreement-analysis plan (Cohen's κ)

Written 2026-11-17, before any second annotation exists. κ is computed by
`scripts/dev_v0_2_human_workflow.py agreement`, which only reads files. The
plan is fixed now so that the analysis cannot be chosen after the labels are
seen.

## Subsets (never pooled with each other)

| Subset | Claims | First label (κ) | Second label | Status | Role in thesis |
|---|---|---|---|---|---|
| **PRIMARY_44** | 44 ambiguous / interpretive: 40 new and AAPL-04, AAPL-06, MSFT-04, AMZN-04 | `rev_person2` (40); `rev_som.v3` (4) | the new independent second annotator, from the blind 44-claim workbook | waiting | **primary reliability figure** |
| **HISTORICAL_DEV_V0_1** | 8 dev-v0.1 claims | `rev_som.v3` (pre-review) | `rev_reviewer2` | done: 4/8, κ 0.24 (95% bootstrap −0.23 … 0.60) | secondary, with caveats |
| **NUMERICAL_VERIFICATION** | 20 numerical | `rev_som.v3` (12), `rev_person2` (8) | the numerical verifier's conclusion (checklist) | waiting | separate; agreement on computable claims |

## What is excluded from every κ

- **`rev_som.v4`.** Decided after the AI-prepared label review. It is reported only as informational (7/8 against `rev_reviewer2`).
- **`rev_person3` and `ai_codex_dev48`.** The first is identical to the Codex output; the second is AI-filled.
- **`design_intent_dev-v0.2`.** It records the AI drafter's expectation, not a label.
- **A2 / R / RG outputs.**
- **Adjudicated labels.** These are decisions, not independent annotations.

## Reporting rules

1. **PRIMARY_44.** Report:
   - n, raw agreement, κ and a bootstrap 95% CI (2,000 resamples, seed 20261102);
   - the confusion matrix and the list of disagreements.
2. **Breakdowns.** Give κ by first labeller and by claim type (ambiguous 25 / interpretive 19).
   - **Pooled κ** mixes two first labellers, so it is not a strict Cohen's κ.
   - **The `rev_person2` row** (n = 40) is the Cohen's κ proper.
   - **The `rev_som` row** has n = 4, so it is listed without interpretation.
3. **Completeness.** κ is reported only when all 44 claims are covered (`complete: true`). Otherwise the result is labelled INCOMPLETE.
4. **Before adjudication.** κ is computed before adjudication, and the file is frozen as `results/dev_v0_2/human_workflow/agreement_<second>.json`. That file is never overwritten.
5. **Caveats to report with the numbers:**
   - `rev_person2`'s labels match the AI-filled workbook on 47/48 claims (observed). The researcher attests that the labeller never saw it.
   - In HISTORICAL_DEV_V0_1, `rev_reviewer2`'s reasons on AAPL-07, MSFT-06 and MSFT-07 closely match the AI review's wording.
   - The claim texts of the 48 new claims were drafted by AI.
6. **Interpretation bands** (Landis & Koch) are descriptive only. No threshold is used to accept or reject labels: every disagreement is adjudicated whatever the κ.

## Commands

```bash
PY=research/.venv/bin/python; S=research/scripts/dev_v0_2_human_workflow.py
# after importing the second annotator's workbook (writes datasets/annotations_dev/<rev_id>.jsonl):
$PY research/scripts/dev_annotation_workbook.py import <filled.xlsx> --claims research/datasets/development_cases_dev-v0.2.jsonl
# after importing the numerical checklist (writes datasets/annotations_dev/numcheck_<id>.jsonl):
$PY $S numeric-import <filled_numeric.xlsx>
$PY $S agreement --second research/datasets/annotations_dev/<rev_id>.jsonl --numeric research/datasets/annotations_dev/numcheck_<id>.jsonl
```

## Second-label files are refused if

- **Reviewer:**
  - `reviewer_type` is not `human`;
  - the id looks like a model;
  - the id is an excluded reviewer;
  - the second annotator is the claim's first labeller.
- **Copied text:**
  - any note repeats text from the Codex workbook or the design intent;
  - any note is identical to the first labeller's note.
- **Location:** the file is not under `datasets/annotations_dev/`.
