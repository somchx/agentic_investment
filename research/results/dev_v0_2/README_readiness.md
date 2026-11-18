# dev-v0.2: research evaluation readiness (A3 v2.1.1)

- **As of:** 2026-11-17.
- **What exists:** predictions are complete; the pipeline is built and tested.
- **Not yet done:** no reference label is approved, so nothing has been scored.

## Deliverables

| # | Deliverable | File | sha256 (16) |
|---|---|---|---|
| 1 | Consolidated claim-level comparison (72 claims, 216 predictions) | `results/dev_v0_2/a3v2.1.1_claims.jsonl` / `.csv` + `.manifest.json` | `5d743ce47217adb4` / `2a559f8189c5367c` / `a5fa2fb76785113b` |
| 2 | Consolidation script | `scripts/a3v2_dev_consolidate.py` | |
| 2 | Evaluation script (approved labels only) | `scripts/a3v2_dev_evaluate.py` | |
| 3 | Human evidence-review workbook: 310 evidence rows (49 P1) + 72 claim rows; no predicted or reference labels | `datasets/workbooks/a3v2.1.1_evidence_review.xlsx` | `260cbf1c925be069` |
| 3 | Workbook export / import script | `scripts/a3v2_evidence_review_workbook.py` | |
| 4 | Adjudication status report | `results/dev_v0_2/label_status.md` / `.jsonl` (`scripts/dev_v0_2_label_status.py`) | `4af588df61b6ab5e` / `060a39b2aeb89ac1` |
| 5 | This checklist | `results/dev_v0_2/README_readiness.md` | |
| — | Tests | `tests/test_dev_v0_2_evaluation.py` (7); the full suite has 276 passed | |

## Checklist

| Item | State |
|---|---|
| 3 runs complete, locked, intact (`verify_run_integrity` = []) and sharing one config | ✅ |
| 72 unique claims × 3 approaches = 216 COMPLETED predictions; dataset sha `120d60d4…` | ✅ (enforced by the consolidation script) |
| RG is cache-only for all 72 claims | ✅ |
| Evaluation refuses reviewer files, design intent, LLM files, unapproved statuses, duplicates and unknown claims | ✅ (tested) |
| Metrics ready | ✅ |
| Evidence-review workbook: independent, label-free, dropdown-validated; import refuses model-like reviewer ids and is never overwritten | ✅ (tested) |
| Frozen v1, Gold, dev claims, annotations and earlier runs unchanged | ✅ (freeze verify `changed: [] removed: []`; hashes unchanged) |
| **Approved reference labels** | ❌ 0 / 72 |
| AAPL-05 adjudication | ❌ |
| Independent second annotation: 44 ambiguous / interpretive claims (40 new + AAPL-04, AAPL-06, MSFT-04, AMZN-04) | ❌ |
| κ before adjudication; adjudication of every disagreement | ❌ (after second annotation) |
| Approved reference-label file `datasets/annotations_dev/dev-v0.2_reference_labels.approved.jsonl` | ❌ (to be written by the researcher) |
| Human evidence review (workbook above) | ❌ (optional before scoring; needed for the evidence error analysis) |

**Metrics ready:**
- Accuracy and macro-F1 with bootstrap CIs.
- Results by claim type.
- McNemar (exact) and paired bootstrap for A2 vs R, A2 vs RG and R vs RG.
- Correction and regression rates with Wilson CIs.
- Guard helpful / harmful counts, overall and by reason code.
- Vote patterns with a Fisher exact test.

## Remaining before final scoring

1. **AAPL-05 adjudication** by a third person: `scripts/dev_adjudication.py export` / `record`.
2. **Second annotation, done independently by a person** of the 44 claims listed in `label_status.md`, from a blank workbook. The numerical claims are optional.
3. **κ against the first labels.** For the 4 old claims, use the pre-review labels (v3) for κ. AAPL-07, MSFT-05 and MSFT-07 were relabelled after the AI-prepared review, and MSFT-06's definition was written after it. Then adjudicate every disagreement.
4. **The researcher writes the approved reference-label file.**
   - One row per claim: `final_label`, `label_status` AGREED / ADJUDICATED, `approved_by`, `approved_at`, `source`.
   - Freeze dev-v0.2 labels at that point.
5. **Run** `scripts/a3v2_dev_evaluate.py --labels <approved file>`. Optionally add `--votes` with the label-agreement status as an external pattern.
6. **Evidence error analysis.** Join the human evidence review, imported with `a3v2_evidence_review_workbook.py import`, with the scored claims. Code the suspicious-reasoning types.

## Not done (by instruction)

- No label was created or changed.
- No provisional label was used as Gold.
- No paid call.
- No change to models or the architecture; A3 v2.2 not started.
- No commit.
