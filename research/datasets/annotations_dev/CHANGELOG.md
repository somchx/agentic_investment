# Development annotations: change log

All files are kept. A new version never replaces an earlier one.

## rev_som.v2.jsonl (2026-11-17)

**Inputs and outputs (sha256)**

| File | Role | sha256 |
|---|---|---|
| `datasets/workbooks/dev_annotation_filled.xlsx` | Source workbook, unchanged | `00654ede7f1a226d8d3458459ba2b1e463ddbceab830f40c7dcefc61ca60a355` |
| `datasets/workbooks/dev_annotation_filled_v2.xlsx` | New workbook | `f5de2fcb0c0e3bce0bea07c9ca8738c44cca79eddfc6c52f752d75a14e9a7293` |
| `rev_som.jsonl` (v1) | Kept unchanged | `dd3d78a6652ccb6b14011f9b96c8b629962a23b126a45236c44bf4464d58dbb6` |
| `rev_som.v2.jsonl` | New version | `f279503308297469b47cf3afe4240c037cad7f2da8c9b77fb530565ef5639507` |
| `rev_som.v2.changes.json` | Machine-readable list of every change | `71e272ce4d6d8b4ffd2b9a67e0f444dcc2ea86d38ffa8bb1721b030d1ef293c7` |

**What changed (Evidence sheet only)**

1. **The 12 short-quote evidence rows became 24 `xbrl_fact` rows.** These were the rows whose quote was only a statement line
   label, such as "Total net sales".
   - Each new row has the us-gaap concept, the period end, a locator (`XBRL <concept> | <basis> <start>..<end> | <form>
     FY<fy> <fp>`) and, as the quote, the verbatim statement row of the same filing.
   - Every value comes from the cached SEC companyfacts. The build script checks that each value appears in that statement
     row before writing it.
   - Every figure a calculation needs is recorded. Examples:
     - prior-year comparatives;
     - revenue, wherever a margin is computed;
     - MSFT-02, where Q4 = FY − 9M: fiscal-year and nine-month operating income and revenue;
     - AMZN-03, which also gets its June 2026 long-term debt.
   - Two rows changed which line they point to:
     - AAPL-03 points to "Non-current liabilities: Term debt". The first "Term debt" row in the filing is the current
       portion.
     - AMZN-03 now also cites the June 2026 balance, 128,894.
2. **Locators.** The URL was removed from 14 other evidence rows. The accession number already identifies the filing.

**What did not change**
- Claim ids (still 24).
- Labels, review notes, confidence, uncertainty type and note, second-review flag, reviewer id.
- Evidence side (supporting / contradicting).
- All other quotes.
- **Checked:** the Claims and Filings sheets in the v1 and v2 workbooks have identical values. In the instructions sheets
  the only difference is empty strings that openpyxl writes back as empty cells.

**Reproduce.** The build script is kept with the session analysis files (`build_v2_workbook.py`). The import is:
`scripts/dev_annotation_workbook.py import datasets/workbooks/dev_annotation_filled_v2.xlsx --version v2`.

**Not yet done**
- The label review of MSFT-05, MSFT-07, MSFT-06 and AAPL-07 (researcher's decision).
- Second review.
- Freeze.

## rev_som.v3.jsonl (2026-11-17)

**Inputs and outputs (sha256)**

| File | Role | sha256 |
|---|---|---|
| `datasets/workbooks/dev_annotation_filled_v2.xlsx` | Source workbook, unchanged | `f5de2fcb0c0e3bce0bea07c9ca8738c44cca79eddfc6c52f752d75a14e9a7293` |
| `datasets/workbooks/dev_annotation_filled_v3.xlsx` | New workbook | `6256dc118acc97bd2e91ad3164311206c3121a758041ea785e72a93e8c7d5e4e` |
| `rev_som.jsonl` (v1) | Kept unchanged | `dd3d78a6652ccb6b14011f9b96c8b629962a23b126a45236c44bf4464d58dbb6` |
| `rev_som.v2.jsonl` | Kept unchanged | `f279503308297469b47cf3afe4240c037cad7f2da8c9b77fb530565ef5639507` |
| `rev_som.v3.jsonl` | New version | `00c644729ecd6a0de90b193062d497dc0efc37bbc378d52c499ea960ef562e18` |
| `rev_som.v3.changes.json` | Every added row, plus the calculations | `0864898b32492802587190d7dee2070cbd5ff8d2fdf94c1efd539e1905e49f29` |

**What changed: 20 evidence rows added (38 → 58); no existing row was changed.**

The added rows are the source figures behind the numbers in the researcher's notes:

| Claim | Rows added | Evidence |
|---|---|---|
| DEV-AAPL-06 | +4 xbrl_fact | Operating cash flow and net income, FY2025 and FY2024 (10-K 0000320193-25-000079) |
| DEV-AMZN-07 | +6 xbrl_fact, +1 passage | Six-month operating cash flow, purchases of property and equipment (`PaymentsToAcquireProductiveAssets`), operating income, plus the "Proceeds from property and equipment sales and incentives" row, which has no us-gaap fact |
| DEV-MSFT-04 | +2 xbrl_fact, +1 passage | Total revenue FY2026 and FY2025; Intelligent Cloud revenue row from the segment results. Segment figures are dimensional and do not appear in companyfacts. |
| DEV-AAPL-04 | +2 xbrl_fact, +1 passage | Total net sales for both quarters; iPhone net sales row from Net Sales by Category |
| DEV-AMZN-04 | +2 xbrl_fact, +1 passage | Consolidated operating income for both quarters; AWS row from operating income by segment |

**Checks**
- Each xbrl_fact value comes from companyfacts for the same accession and period, and appears in the quoted statement row.
- Each passage quote is verbatim in the cached filing.
- Every recomputed result matches the researcher's notes:

  | Claim | Recomputed result |
  |---|---|
  | AAPL-06 | Operating cash flow fell by 6,772 while net income rose by 18,274 |
  | AMZN-07 | Capex net 55,623 / 96,310; FCF −6,093 / −24,891 |
  | MSFT-04 | 31,526 of 50,115 (62.9%) |
  | AAPL-04 | 9,670 of 15,381 (62.9%) |
  | AMZN-04 | 6,461 of 8,290 (77.9%) |

**Not changed**
- **AMZN-03 and AMZN-05 quotes "$132.1 billion".** SEC's inline XBRL renders `$<ix:nonFraction>132.1</ix:nonFraction> billion` as "$132.1 billion", so the researcher's quote is correct. The space seen earlier came from our text extraction.
- **Labels and notes.** Labels, notes, confidence, uncertainty and the second-review flag are identical in v1, v2 and v3.

## rev_som.v4.jsonl (2026-11-17): researcher's label decisions

**Inputs and outputs (sha256)**

| File | Role | sha256 |
|---|---|---|
| `datasets/workbooks/dev_annotation_filled_v3.xlsx` | Source workbook, unchanged | `6256dc118acc97bd2e91ad3164311206c3121a758041ea785e72a93e8c7d5e4e` |
| `datasets/workbooks/dev_annotation_filled_v4.xlsx` | New workbook | `b9f086551034d8fe83f05ab11b45cffc2db82c739e98373b8c6dacaccfd7870b` |
| `rev_som.v4.jsonl` | New version | `d0c7ec1dc9b3555ccf7916542b9051fa930c9661621718510118fac4487d9482` |
| `rev_som.v4.changes.json` | Before/after of each change | `7ef83b1c570b27cfcee0deeb101d0c3666ef35274e381d67f9029d3b4b2b0829` |

v1, v2 and v3 are unchanged.

**Decisions** (by the researcher, `rev_som`, given in her own words):

| Claim | v3 | v4 |
|---|---|---|
| DEV-MSFT-05 | SUPPORTED | **INSUFFICIENT_EVIDENCE** |
| DEV-MSFT-07 | SUPPORTED | **INSUFFICIENT_EVIDENCE** |
| DEV-MSFT-06 | CONTRADICTED | CONTRADICTED (kept). The definition used is now stated: profitability = gross margin % |
| DEV-AAPL-07 | CONTRADICTED | **INSUFFICIENT_EVIDENCE** |

- **Notes.** The original notes are kept. The decision and its reason are appended, tagged `[v4 2026-11-17 …]`.
- **Unchanged:** confidence, uncertainty, evidence and all other claims.
- **Label totals:**

  | Label | v3 | v4 |
  |---|---|---|
  | SUPPORTED | 14 | 12 |
  | CONTRADICTED | 8 | 7 |
  | INSUFFICIENT_EVIDENCE | 2 | 5 |

**Provenance (important)**
- These decisions were made after the researcher read an AI-prepared label review (`dev_label_review_recommendations.md`).
  v4 is therefore not independent of AI assistance on these 4 claims.
- **Agreement.** Report inter-annotator agreement (κ) with the second reviewer's blind labels against the
  pre-review labels (v1–v3, identical for all 24 claims).
- **Final label.** Treat v4 as the researcher's post-review label. Disagreements still go to adjudication.

## Second review: `rev_reviewer2` (received 2026-11-17, not yet imported)

- **File:** `datasets/workbooks/dev_blind_review_8 copy.xlsx`, sha256 `afac05fd24bad543dd3fff6008f1d5a6c501afc13a6f0c66e645575f68b269aa`.
- **Independence attestation.** The researcher (`rev_som`) states that `rev_reviewer2` is a different person and labelled
  independently ("คนตรวจแน่นอนจ้า รับประกัน", i.e. "it is definitely a different reviewer, guaranteed"; 2026-11-17).
- **Facts recorded as observed** (for the audit trail; not a finding):
  - The file was last saved by the same Excel account as the researcher's workbook ("Chananya Aiamprakhon", 12:23).
  - The reasons on AAPL-07, MSFT-06 and MSFT-07 closely match the wording of the AI-prepared label review.
- **Status:** the import fails validation, so nothing is written yet.
  - All 11 evidence rows use the side values `support`, `refute` and `context` and the kind value `passage`.
  - AMZN-06 has no evidence row.
- **Provisional comparison** (not imported; 8 claims):
  - Against the pre-review labels (v3): agreement 4/8, κ 0.24.
  - Against v4: agreement 7/8.
  - Agreement must be reported against v3 (see the v4 entry).

### Second review imported: `rev_reviewer2.jsonl` (2026-11-17)

**Format fix**
- **Who and where.** Done by the AI analyst at the researcher's request ("คุณแก้ไขเลย", "go ahead and fix it"). The
  original returned file is kept unchanged. The fixed copy is
  `datasets/workbooks/dev_blind_review_8_rev_reviewer2_fixed.xlsx` (sha256 `a524ed3c…`). Every change is listed in
  `rev_reviewer2.fix.json` (sha256 `332acc50…`).
- **Value renames:** `support` → `supporting`, `refute` → `contradicting`, `passage` → `filing_passage`.
- **7 `context` rows moved out.** They are kept verbatim in the fix log, with no side assigned on the reviewer's behalf.
  All of them belong to claims the reviewer labelled INSUFFICIENT_EVIDENCE, where evidence is optional.
- **DEV-AMZN-06.** Added 2 xbrl_fact rows (CostsAndExpenses Q2 2026 / Q2 2025, contradicting). These are the figures the
  reviewer's own note names as the basis.
- **Unchanged.** Labels, notes, confidence and uncertainty were not touched; the Claims sheet is identical.

**Import.** `rev_reviewer2.jsonl` holds 8 claims (sha256 `ce27fd27…`).

**Agreement** (`scripts/dev_label_agreement.py`; results in `results/dev_agreement/`)

| Comparison | Agreement | κ | 95% bootstrap CI | Disagreements |
|---|---|---|---|---|
| **Primary: v3 (pre-review) vs rev_reviewer2** | 4/8 | **0.24** | −0.23 … 0.60 | AAPL-05, AAPL-07, MSFT-05, MSFT-07 |
| Informational: v4 (post-review) vs rev_reviewer2 | 7/8 | 0.77 | — | AAPL-05 |

- **Why v4 is informational only.** v4 was decided after the AI-prepared review, so it is not independent of AI assistance.
- **Adjudication still needed.** The researcher's v4 resolves AAPL-07, MSFT-05 and MSFT-07 the same way rev_reviewer2 did.
  AAPL-05 is still open (rev_som INSUFFICIENT_EVIDENCE vs rev_reviewer2 SUPPORTED).

## dev-v0.2 claims drafted: 48 new claims, unlabelled (2026-11-17)

- **What was added.** 48 new claims for ADBE, INTC, PG and CAT, 12 per company.
  - Categories: ambiguous 25, interpretive 15, numerical 8. Pattern quotas match plan §2b exactly.
  - **All 48 are AI-drafted** (`author_id` `ai_draft_claude-opus-5-5`). The drafter read only the cached SEC filings of
    these four companies. No gold claim text and no system prediction was read.
- **Files**

  | File | sha256 |
  |---|---|
  | `datasets/development_cases_dev-v0.2.jsonl` (72 claims; the first 24 lines are byte-identical to `development_cases.jsonl`) | `120d60d4…` |
  | `design_intent_dev-v0.2.jsonl` (author expectation, not a label; keep away from annotators) | `a4e45f4b…` |
  | `datasets/corpus_manifest_dev-v0.2.json` (19 filings; the frozen `corpus_manifest.json` is unchanged) | `064703a6…` |
  | Blank annotation workbook `datasets/workbooks/dev_annotation_workbook_dev-v0.2_new48.xlsx` | `5f179672…` |

  Author-only material is in `dev-v0.2_author/`: the authoring workbook, SEC filing references, the validation report and
  the summary.
- **Validation.** 48/48 valid, with no errors and no warnings.
  - Maximum similarity: 0.381 to gold, 0.353 to dev-v0.1 and 0.385 among the new claims.
  - No filing was filed after its claim's cutoff.
- **Unchanged.** No label exists for the new claims. The 24 existing claims and all their annotation versions are
  unchanged.

## dev-v0.2: first labels for the 48 new claims, `rev_person2.dev-v0_2.jsonl` (2026-11-17)

- **Labeller.** `rev_person2`. The researcher (`rev_som`) states that another person did the labelling and that she only
  downloaded the file to her machine. She also states that this labeller never saw the Codex results.
- **Files received** (all kept unchanged)

  | File | sha256 | Status |
  |---|---|---|
  | `datasets/dev_annotation_workbook_dev-v0.2_new48.xlsx` | `bd0828ef…` | Wrong file. It was filled by Codex (`ai_codex_dev48`, declared in the file as "not a human annotation"). Rejected by the model-id check; not imported. |
  | `dev_annotation_new48_filled.xlsx` | `27aa1da3…` | First version from `rev_person2`. 12 decisive claims had no evidence. Not imported. |
  | `dev_annotation_new48_evidence_corrected.xlsx` | `a2b95b28…` | Source of this import |

- **Format fix.**
  - **Who.** Done by the AI analyst at the researcher's request.
  - **Output.** `dev_annotation_new48_rev_person2_fixed.xlsx` (sha256 `3983437…`). Every change is logged in
    `rev_person2.fix.json` (`65d0ce05…`).
  - **Changes: 6 evidence cells.**
    - **XBRL concept names (4).** INTC-04 and INTC-11, PG-04 and PG-11. Each now uses the concept under which companyfacts
      report the same value for the same accession and period. The values are unchanged.
    - **Quotes (2).** CAT-05 and INTC-12 had quotes that were not verbatim. Each is replaced with the verbatim filing sentence
      that carries the same figure.
  - **Unchanged.** The Claims and instructions sheets are identical: labels, notes, confidence and uncertainty were not touched.
- **Import.** 48 claims.
  - Labels: INSUFFICIENT_EVIDENCE 24, CONTRADICTED 15, SUPPORTED 9.
  - sha256 `74ff3d4f…`.
- **Facts recorded as observed** (for the audit trail; not a finding).
  - The source file carries no Excel metadata.
  - The "reviewer name" cell reads "9".
  - Labels match the Codex file on 47/48 claims; the exception is INTC-07.
  - Labels match the drafter's design intent on 46/48 claims; the exceptions are INTC-06 and INTC-07.
  - The notes are worded differently from the Codex notes (median text similarity about 0.22).
- **Not yet done**
  - A second human, blind labeller for the 40 ambiguous and interpretive claims. κ is computed after that.
  - Adjudication.
  - Freeze.

## dev-v0.2 second review (`rev_person3`): received, not used for agreement (2026-11-17)

- **Files received.** Neither file was imported.

  | File | sha256 |
  |---|---|
  | `dev_blind_review_dev-v0.2_40_filled.xlsx` | `efdfc544…` |
  | `dev_blind_review_dev-v0.2_40_reviewed.xlsx` | `95b9780d…` |

- **Researcher's attestation.** The researcher states that the reviewer is a person ("เป็นคนจ้า ไม่ใช่ AI", i.e. "it's a
  person, not AI").
- **Observed.** In both files the reviewer-entered fields are character-identical to the Codex-filled workbook
  (`ai_codex_dev48`).
  - Identical on all 40 claims: labels, review notes, confidence and the second-review flag.
  - Uncertainty fields: identical on 40/40 in the first file and 39/40 in the second.
- **Decision.** Not used as an independent blind second review. No κ is reported from these files, whoever submitted
  them, because the content is not independent of the Codex output.
- **Consequence.** dev-v0.2 currently has a single labeller (`rev_person2`). The blank blind workbook
  `dev_blind_review_dev-v0.2_40.xlsx` stays available.

## dev-v0.2 44-claim second annotation (`rev_somchai`): received, not imported (2026-11-18)

- **File received.** `datasets/workbooks/dev-v0.2_second_annotation_44_blank.xlsx`.
  - The blank was filled in place. Blank sha256 was `353a5885…`; the returned file is `b0ea7445…`.
  - Last saved by the Excel account "Chananya Aiamprakhon", 2026-11-18 02:27Z.
- **Format.** The workbook passes import validation (44 claims, 86 evidence rows).
- **Observed (independence screen, `dev_v0_2_human_workflow.py`):**
  - **Reviewer id.** `rev_somchai` is the example id printed in the instructions.
  - **Labels.** They match the Codex-filled workbook (`ai_codex_dev48`) on 40/40 shared claims. They match `rev_person2` on 43/44 (the exception is INTC-07).
  - **Review notes.** They are character-identical to the Codex notes on 39/40 claims; median similarity is 1.00.
  - **Evidence.** 80/86 locators and 78 quotes are identical to the Codex workbook's evidence.
  - **Minutes spent.** Empty for all 44 claims.
- **Decision.** Not imported. Not usable as an independent second annotation or for κ, because its content repeats the
  AI-filled workbook. The approval gate refuses it (`screen_independence`).
- **Replacement blank.** `datasets/workbooks/dev-v0.2_second_annotation_44_blank_v2.xlsx` (blind audit passed;
  `results/dev_v0_2/human_workflow/blind_package_audit_v2.json`).

## dev-v0.2 returns (2026-11-18)

### AAPL-05 adjudication: recorded

- **Source.** `datasets/workbooks/dev-v0.2_AAPL-05_adjudication_packet.xlsx` (sha256 `35589591…`), last saved by the Excel
  account "Chananya Aiamprakhon".
- **Decision.** Adjudicator `kantika` → **INSUFFICIENT_EVIDENCE**, with a written reason.
- **Declaration.** All four statements were answered "ใช่" (yes): not rev_som / rev_reviewer2; has not seen system outputs or
  AI-prepared material; no AI used; decided from the SEC filings.
- **Recorded** with `scripts/dev_adjudication.py record` into `adjudications.jsonl` (append-only).

### 44-claim second annotation `dev-v0.2_second_annotation_44_filled.xlsx`: not imported yet

- **File.** sha256 `c854bc1c…`; reviewer id `rev_somchai`.
- **Not copied.** The text does not repeat any AI-produced text (0/44 identical; median similarity 0.19 to the Codex notes
  and 0.26 to the first labeller's notes).
- **Labels.** Agreement with the first labels is 32/44.
  - The labels are INSUFFICIENT_EVIDENCE 35, CONTRADICTED 7, SUPPORTED 2.
- **Blocked by validation.**
  - The Evidence sheet is empty.
  - 9 decisive claims have no evidence row: ADBE-04, INTC-04, INTC-06, PG-04, PG-07, PG-09, CAT-04, CAT-05, CAT-09.
- **Observed timing.**
  - The workbook was created from `_blank_v2` at 02:28:53Z and last saved at 02:39:00Z, about 10 minutes for 44 claims.
  - The minutes-spent cells are empty.
- **The numerical verification workbook** came back unchanged (sha256 `c7b022a1…` = the blank); it has not been filled.

### Updated returns (2026-11-18, second round): not imported

- **44-claim file `dev-v0.2_second_annotation_44_filled.xlsx`** (sha256 `36925765…`).
  - **Reviewer ID.** Now empty, so the import refuses the file.
  - **Evidence.** 15 rows were added. All 15 are identical (claim, locator, verbatim quote) to evidence rows in the
    Codex-filled workbook. This includes the analysis text inside locators, e.g. "R&D fell but accounts for less than half of
    operating-loss improvement".
  - **File metadata.** The file has no document properties, and every part carries the same 02:44 timestamp; Excel does
    not save files this way.
  - **Status.** The labels and notes from round 1 still show no copying. The evidence is not the annotator's own.
- **Numerical checklist `dev-v0.2_numerical_verification_20.xlsx`** (sha256 `0885954b…`).
  - **Content.** All 20 claims pass validation once the verifier id is set aside.
  - **Agreement.** The conclusions agree with the first labels on 20/20.
  - **Calculations.** 19 were done in a spreadsheet.
  - **Blocked.** The verifier id `ai_apiwat` matches the model-id pattern (`ai_…`).
  - **Tool fix.** "N/A" period start is now accepted for INSTANT values.

### Numerical verification imported: `numcheck_rev_apiwat.jsonl` (2026-11-18)

- **Verifier id.** The researcher states that `ai_apiwat` was a typo and corrected it to `rev_apiwat` in Excel
  (workbook sha256 `64d67e9f…`, saved 02:51Z). No other cell changed.
- **Import.** `dev_v0_2_human_workflow.py numeric-import` passed validation and the independence screen.
  - 20 claims: SUPPORTED 10, CONTRADICTED 9, INSUFFICIENT_EVIDENCE 1.
  - Agreement with the first labels: 20/20.

### Second annotation imported: `rev_somchai.dev-v0_2.jsonl` (2026-11-18)

- **Source.** `datasets/workbooks/dev-v0.2_second_annotation_44_somchai_SEC_rechecked.xlsx` (sha256 `5fdcb8fb…`).
  - Reviewer `rev_somchai`; 44 claims.
  - The output `rev_somchai.dev-v0_2.jsonl` has sha256 `e0ab5c02…`.
- **Evidence.** 9 rows, one per decisive claim, written by the annotator.
  - 0/9 match the Codex workbook.
  - All 9 quotes were found verbatim in the cached SEC filings.
- **Checks.**
  - Import validation passed.
  - Independence screen: no repeated AI-produced text and no copy of the first labeller's notes.
  - Labels and notes are unchanged from the round-1 return.
- **Observed.** The file again has no document properties, and the minutes-spent cells are empty.
- **κ before adjudication** (`results/dev_v0_2/human_workflow/agreement_rev_somchai.json`):

  | Comparison | n | Raw agreement | κ | 95% bootstrap CI |
  |---|---|---|---|---|
  | PRIMARY_44, pooled | 44 | 0.727 | 0.49 | 0.27 – 0.69 |
  | rev_person2 vs rev_somchai | 40 | 0.80 | 0.60 | 0.37 – 0.82 |
  | Ambiguous | 25 | — | 0.80 | — |
  | Interpretive | 19 | — | 0.21 | — |
  | Numerical: first vs rev_apiwat | 20 | 20/20 | 1.00 | — |

  - **Disagreements: 12.**
  - **Direction.** 9 are SUPPORTED → INSUFFICIENT_EVIDENCE and 3 are CONTRADICTED → INSUFFICIENT_EVIDENCE.
  - **Old claims.** All 4 old claims (rev_som v3) disagree.
- **Round-1 adjudication packet.** `datasets/workbooks/dev-v0.2_adjudication_packet_round1.xlsx` (sha256 `453958b3…`).
  - 16 claims: the 12 disagreements plus AAPL-07, MSFT-05, MSFT-06 and MSFT-07.
  - The blind audit passed.

### Round-1 adjudication recorded (2026-11-18)

- **Source.** `datasets/workbooks/dev-v0.2_adjudication_kantika_filled.xlsx` (sha256 `1d56dc8b…`).
  - Adjudicator `kantika`; 16 claims.
  - The claim and reviewer columns are unchanged from the issued packet.
  - Every decision has a reason, and no reason repeats AI-produced text.
  - The file has no document properties.
- **Decisions.**
  - The adjudicator sided with the first labeller on 12 of the 12 disagreements.
  - The 4 AI-affected claims: AAPL-07 → INSUFFICIENT_EVIDENCE, MSFT-05 → SUPPORTED, MSFT-06 → CONTRADICTED,
    MSFT-07 → INSUFFICIENT_EVIDENCE.
- **Recorded** with `dev_adjudication.py record` (append-only). All 72 claims now have an approvable human basis
  (AGREED 55, ADJUDICATED 17).

## dev-v0.2 reference labels APPROVED and frozen (2026-11-18)

- **Approval.** The researcher (`rev_som`) approved the labels ("อนุมัติ"). The file was written by
  `dev_v0_2_human_workflow.py approve`.
- **Files** (both read-only)

  | File | sha256 |
  |---|---|
  | `dev-v0.2_reference_labels.approved.jsonl` | `0d288fe3606a99c6…` |
  | `dev-v0.2_reference_labels.approved.manifest.json` | `b3c9cc5536ad08a9…` |

- **Content.** 72/72 claims.
  - By status: AGREED 55, ADJUDICATED 17.
  - By label: SUPPORTED 22, CONTRADICTED 22, INSUFFICIENT_EVIDENCE 28.
- **Sources** (sha256 of each in the manifest):
  - `rev_som.v3`, `rev_person2`, `rev_reviewer2`, `rev_somchai`, `numcheck_rev_apiwat`;
  - `adjudications.jsonl` (17 decisions, by `kantika`).
- **Validation.** `validate` re-derived every row from the human sources: valid.
- **Corrections.** Any correction needs a new versioned file and a new approval.
- **First evaluation.** `results/dev_v0_2/evaluation_0d288fe3/`.

## dev-v0.2 reference labels v2: DEV-INTC-07 corrected (2026-11-18)

- **Change.** DEV-INTC-07 goes from INSUFFICIENT_EVIDENCE (AGREED: rev_person2 + rev_somchai) to **SUPPORTED** (ADJUDICATED).
  The other 71 claims are unchanged.
- **Basis.** The 10-K FY2025 (0000050863-26-000011), MD&A, DCAI paragraph says: "Our 2025 server revenue was limited in Q4
  2025 by our available supply of products due to Intel Foundry wafer fabrication supply constraints …". Both labellers'
  notes refer only to the client-volume paragraph.
- **Who decided.** The researcher (`rev_som`), who did not label this claim. The decision is recorded in
  `adjudications.v2.jsonl`, a copy of `adjudications.jsonl` plus this one entry; the original log is unchanged.
- **Provenance flag.**
  - The error was found by the AI analyst's audit (`results/dev_v0_2/error_analysis/gold_audit_rg_errors.md`).
  - The researcher decided after seeing that audit and the system outputs (A2 / A3 answered SUPPORTED).
  - The correction is therefore **not a blind adjudication** and must be reported as a post-hoc label correction.
- **Files.** v1 is kept unchanged and still validates (`…approved.jsonl` `0d288fe3…`).

  | File | sha256 |
  |---|---|
  | `dev-v0.2_reference_labels.v2.approved.jsonl` | `7dccc43a…` |
  | `dev-v0.2_reference_labels.v2.approved.manifest.json` | `36f77f72…` |
  | `adjudications.v2.jsonl` | `acbef889…` |

- **Content of v2.** 72/72 claims: AGREED 54, ADJUDICATED 18. Validate: valid.
- **Evaluation.** `results/dev_v0_2/evaluation_7dccc43a_r1.1/`. The v1 evaluation is kept.
