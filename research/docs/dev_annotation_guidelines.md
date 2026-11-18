# Development annotation addendum (`dev-addendum-1.1`)

This addendum is for labelling the **development split** (`datasets/development_cases.jsonl`), which is used to
develop A3 v2. It **extends** `datasets/annotation_guidelines.md` (`gold-guidelines-1.0`).

- **Same as gold:** every gold rule applies unchanged. That covers the labels, the decision order, the evidence
  cutoff, the evidence records and the independence rules. Labels are therefore comparable with the gold set.
- **New in this addendum:** recording uncertainty, and keeping development labels separate from gold.

Workbook: `scripts/dev_annotation_workbook.py`.

| Command | What it does |
|---|---|
| `export` | Writes `datasets/workbooks/dev_annotation_workbook.xlsx` |
| `import` | Writes `datasets/annotations_dev/<reviewer_id>.jsonl` |

## 1. What development labels are for

- **Use them for:**
  - developing A3 v2 prompts and rules;
  - choosing between architecture variants;
  - measuring how well the evidence reviewer agrees with people.
- **Do not use them for:**
  - reporting final results;
  - merging into the 150 gold claims;
  - writing new claims by looking at system output.
- **Final evaluation** uses a new holdout. Its claims and labels must be fixed before A3 v2 is frozen.

## 2. Independence (in addition to gold §1)

- **Do not open:**
  - v1 traces;
  - A3 v2 output;
  - the error-analysis workbooks;
  - notebooks 03–08.
- **Do not ask any AI** about a claim.
- **No system-retrieved passages.** The workbook deliberately does not show the passages the system retrieved.
  Read the eligible filings through the links. Otherwise the labels would lean toward what the retriever already
  finds, and the evaluation could no longer measure retrieval misses.
- **Author and annotator.** Whoever writes a claim should not be the only person to label it.

## 3. Labels: same rules as gold (`annotation_guidelines.md` §2)

1. Split the claim into its material parts.
2. If any part is shown false, the label is **CONTRADICTED**.
3. Otherwise, if every part is shown true, the label is **SUPPORTED**.
4. Otherwise the label is **INSUFFICIENT_EVIDENCE**.

The following points come from the v1 error analysis. They are reminders of existing gold rules, not new rules:

- **Evaluative predicates with no criterion** ("resilient", "adequate returns", "fully under control"):
  - With no criterion in the claim or the filing → INSUFFICIENT_EVIDENCE.
  - If a factual part of the claim is shown false → CONTRADICTED.
- **Management intentions and strategy** ("we seek to invest efficiently") are not evidence of results.
- **Absence claims** ("not affected by tariffs"):
  - SUPPORTED only if a filing states the absence or the immateriality.
  - Not finding a disclosure gives INSUFFICIENT_EVIDENCE.
- **Periods.** Use the period the claim states.
  - A figure from another period serves only as the comparison base, such as the same quarter a year earlier.
  - A 10-Q inside the fiscal year is only part of the period for an annual claim.
- **Levels vs changes.** A level in one year does not explain a change. A share of a change needs the figures for
  both periods.
- **Computed figures** (free cash flow = operating cash flow − purchases of property and equipment; share of a
  change):
  - Write the formula and the numbers in the notes.
  - Record the source figures in the Evidence sheet.
- **Definitions and segments.** A segment can be renamed or change composition. A line item can sit outside the
  measure: membership income, for example, is not part of gross profit. In such cases:
  - say so in the notes;
  - choose the label that the claim **as written** deserves.

## 4. Recording uncertainty (new columns in the Claims sheet)

| Column | Values | When to use it |
|---|---|---|
| Confidence | HIGH / MEDIUM / LOW | **Required** for every labelled claim.<br>HIGH = another reviewer would very likely give the same label.<br>MEDIUM = there is a point of interpretation, but you chose for a stated reason.<br>LOW = another label is also reasonable. |
| Uncertainty type | NONE, UNDEFINED_PREDICATE, CAUSE_NOT_STATED, PERIOD_OR_BASIS_UNCLEAR, DEFINITION_CHANGE, CONFLICTING_DISCLOSURES, THRESHOLD_OR_ROUNDING_EDGE, FIGURE_NOT_FOUND, NEGATIVE_CLAIM, OTHER | The main reason for the uncertainty. OTHER requires a note. |
| Uncertainty note | Free text | Explain what could change the label. |
| Second review requested | "ใช่" (yes) | Use when confidence is LOW or the claim should get a second, independent review. |

Confidence is the reviewer's judgement. It is not a statistical measure of how reliable the label is.

## 5. Recommended workflow

1. **Researcher.** Labels all 24 claims and records confidence and uncertainty.
2. **Second reviewer** (a person, labelling independently): labels at least:
   - every claim marked LOW or "second review requested";
   - every ambiguous claim.
3. **Agreement.** Report Cohen's κ before adjudication.
4. **Disagreements.** An adjudicator who did not label the claim decides, and records the decision as in gold §5.
5. **Freeze the dev labels**, with a version and a sha256, before any paid A3 v2 development run.

## 6. Evidence from outside the system's filing set (added in 1.1)

**Rule.** Development evidence may cite any filing that meets all of these:
- same company;
- an allowed form;
- filed on or before the cutoff (gold §1.3).

This covers, for example, the prior-year 10-Q a year-over-year balance comparison needs. The system retrieves only
the latest 10-K and the 2 latest 10-Qs.

**On import.** Each claim lists such filings in `evidence_outside_system_corpus`, so that evidence-recall metrics can
exclude them. The gold workbook tool keeps its narrower rule.

**In Excel.** The Evidence sheet's check column may still show "ไม่ใช่รายงานที่ใช้ได้ของ claim นี้" ("not an eligible
filing for this claim") for such a filing. The import rule decides.

`NEGATIVE_CLAIM` (added in 1.1) marks an absence claim ("not affected by…", "no pressure on…") whose filings state
neither the absence nor that the effect is immaterial.
