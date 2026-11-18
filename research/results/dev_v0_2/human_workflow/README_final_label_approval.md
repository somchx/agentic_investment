# dev-v0.2: final human label approval and freeze

- **Status (2026-11-17):** 0 of 72 claims have an approved label.
  - 3 claims could be approved today: AMZN-05, AMZN-06 and AMZN-07 (AGREED between `rev_som.v3` and `rev_reviewer2`).
  - The other 69 are waiting on the human steps below.
- **No label has been created or changed.**
- **Every step marked 👤 needs a person.** Scripts only package, check and record what people decide.

## Deliverables

All workbooks are in `datasets/workbooks/` and all reports in `results/dev_v0_2/human_workflow/`.

| # | Deliverable | File | sha256 (12) |
|---|---|---|---|
| 1 | Blind annotation package: 44 claims (ambiguous 25, interpretive 19), with its audit | `dev-v0.2_second_annotation_44_blank.xlsx` + `blind_package_audit.json` | `353a58857faa` |
| 2 | AAPL-05 adjudication packet: rev_som vs rev_reviewer2, with Provenance and Declaration sheets, and its audit | `dev-v0.2_AAPL-05_adjudication_packet.xlsx` + `aapl05_packet_audit.json` | `4131738a85b2` |
| 3 | Numerical verification checklist: 20 claims, blind | `dev-v0.2_numerical_verification_20.xlsx` | `c7b022a1133b` |
| 4 | Annotation provenance report | `annotation_provenance.{md,jsonl}` | |
| 5 | Agreement-analysis plan | `agreement_plan.md` | |
| 6 | This guide | `README_final_label_approval.md` | |
| — | Workflow script and tests | `scripts/dev_v0_2_human_workflow.py`, `tests/test_dev_v0_2_human_workflow.py` | |

**Blindness audit.** It passed for workbooks 1 and 2. It checks every cell of every sheet against 268 strings:
- system-output identifiers (A2 / A3v2 / RG, guard codes);
- every note in the AI-filled workbook and the design intent;
- every first-annotator note.

It also checks that the input cells and the reviewer id are blank and that no label value appears in a claim row.

## Steps

### 1 👤 Independent second annotation (44 claims)

- **Who.** One person who is not `rev_som` and not `rev_person2`. They must not have seen:
  - any label of these claims;
  - A2 / A3 output;
  - the evidence-review workbook;
  - the Codex or `rev_person3` files.

  They use no AI.
- **Give them** `dev-v0.2_second_annotation_44_blank.xlsx` only. Do not send `author_only/`, `results/` or other workbooks.
- **Import:**

  ```bash
  research/scripts/dev_annotation_workbook.py import <filled.xlsx> --claims research/datasets/development_cases_dev-v0.2.jsonl
  ```

### 2 👤 Numerical verification (20 claims)

- **Who.** One person who is not the first labeller of the claims they verify:
  - not `rev_som` for AAPL / MSFT / AMZN;
  - not `rev_person2` for ADBE / INTC / PG / CAT.

  They use no AI.
- **For every claim** they record:
  - the formula;
  - each input with its value, scale, unit, period start and end, duration and fiscal period;
  - the SEC form, accession and location;
  - checks for period, units and sources;
  - calculation provenance;
  - a conclusion.
- **Import** with `numeric-import <filled.xlsx>`. The import refuses:
  - an accession that is not an eligible same-company filing on or before the cutoff;
  - a period end after the cutoff;
  - formula references with no matching input row;
  - missing checks;
  - a model-like verifier id;
  - a verifier who is the claim's first labeller.

### 3 👤 AAPL-05 adjudication (third person)

- **Who.** Not `rev_som` and not `rev_reviewer2`.
- **The packet** shows both annotations, their evidence and the SEC links. It contains nothing else.
- The adjudicator answers the Declaration sheet first. If any answer is "ไม่ใช่" (no), use another adjudicator.
- **Record:**

  ```bash
  research/scripts/dev_adjudication.py record <filled packet>
  ```

  Recording is append-only and refuses an adjudicator who labelled the claim.

### 4 κ before adjudication

- Run `agreement --second … --numeric …` as set out in `agreement_plan.md`.
- The output `agreement_<id>.json` is never overwritten. Report it before step 5.

### 5 👤 Adjudicate disagreements, plus the 4 claims affected by prior AI review

```bash
research/scripts/dev_v0_2_human_workflow.py adjudication-packet --second <file> --numeric <file> \
    --out research/datasets/workbooks/dev-v0.2_adjudication_packet_round1.xlsx
```

- **What the packet contains:**
  - every PRIMARY_44 and numerical disagreement;
  - AAPL-07, MSFT-05, MSFT-06 and MSFT-07 always, shown with the **pre-review** `rev_som.v3` record.
- The packet is audited for blindness before it is kept.
- A person adjudicates it, then the decisions are recorded with `dev_adjudication.py record`.

### 6 👤 Approve and freeze

```bash
research/scripts/dev_v0_2_human_workflow.py approve --second <file> --numeric <file> --approved-by rev_som
research/scripts/dev_v0_2_human_workflow.py validate research/datasets/annotations_dev/dev-v0.2_reference_labels.approved.jsonl
```

- **What `approve` writes:** a row only for claims that are either
  - **AGREED** between the first label and every independent second label, or
  - **ADJUDICATED**.
- **What it refuses:**
  - a run with any claim still SINGLE, DISAGREED or needing adjudication (unless `--allow-partial` is given);
  - AI or excluded sources;
  - a model-like `--approved-by`;
  - overwriting an existing file.
- **What it produces:**
  - `…approved.jsonl` and `…approved.manifest.json`, which records the sha256 of every source, the dataset and the approved file;
  - both files are made read-only.
- **Freeze.**
  - Add a CHANGELOG entry with the approved sha256.
  - Commit only when you decide to.
  - Corrections later need a new versioned file and a new approval. Never edit the approved file.

### 7 Score

`a3v2_dev_evaluate.py --labels <approved file>`

It now runs `validate` first. A label file that was not produced by `approve`, or any changed source, is refused.

## Why approved labels cannot come from AI output or provisional labels

| Route | Blocked by | Test |
|---|---|---|
| AI-filled file (`ai_codex_dev48`), model-like reviewer, `reviewer_type` ≠ human | `check_source` | ✅ |
| Excluded reviewer (`rev_person3`) | `EXCLUDED_REVIEWERS` | ✅ |
| Second label whose notes repeat Codex / design-intent text, or copy the first labeller | `screen_independence` | ✅ |
| Design intent, `results/` (A2 / R / RG predictions, traces), files outside `datasets/annotations_dev/` | path rules | ✅ |
| SINGLE (provisional single-labeller) or DISAGREED claims | `derive` leaves them unapproved | ✅ |
| AI-affected claims approved as AGREED | `MUST_ADJUDICATE` | ✅ |
| Model-like `--approved-by` or adjudicator; adjudicator who labelled the claim | `approve` / `derive` | ✅ |
| Hand-written or edited approved file | `validate` (manifest + re-derivation), required by the evaluation script | ✅ |
