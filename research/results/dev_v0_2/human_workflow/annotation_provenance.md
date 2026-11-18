# dev-v0.2 annotation provenance

- **Generated:** 2026-11-17 by `scripts/dev_v0_2_human_workflow.py provenance` (read-only).
- **Scope:** 72 claims. No label was created or changed.

## Sources of labels

| Source | Who | Claims | Usable for | Notes |
|---|---|---|---|---|
| `rev_som.v3.jsonl` | rev_som (researcher) | 24 dev-v0.1 | first label, κ | before the AI-prepared label review |
| `rev_som.v4.jsonl` | rev_som | 24 dev-v0.1 | informational only | 4 claims decided / defined after the AI-prepared label review |
| `rev_reviewer2.jsonl` | rev_reviewer2 (attested independent person) | 8 dev-v0.1 | second label, κ (historical) | evidence format fixed by the AI analyst; on AAPL-07, MSFT-06, MSFT-07 the reasons closely match the AI review's wording |
| `rev_person2.dev-v0_2.jsonl` | rev_person2 (attested person) | 48 new | first label, κ | 6 evidence cells fixed by the AI analyst; labels match the Codex workbook on 47/48 and design intent on 46/48 (observed; researcher attests the labeller never saw Codex) |
| `dev_blind_review_dev-v0.2_40_{filled,reviewed}.xlsx` (rev_person3) | — | 40 | **not usable** | content identical to the Codex workbook |
| `dev_annotation_workbook_dev-v0.2_new48.xlsx` (ai_codex_dev48) | AI | 48 | **not usable** | AI-filled |
| `design_intent_dev-v0.2.jsonl` | AI drafter | 48 | **not usable** | author expectation, not a label |
| A2 / A3v2.1.1 R / RG predictions | system | 72 | **never** a label source | |

## Claims affected by prior AI review (4): adjudication required

| Claim | Flag | Pre-review label (κ) | Post-review label | rev_reviewer2 | Record |
|---|---|---|---|---|---|
| DEV-AAPL-07 | FIRST_LABEL_AFTER_AI_REVIEW | CONTRADICTED | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | rev_som v4 label changed after the AI-prepared label review (v3 CONTRADICTED -> v4 INSUFFICIENT_EVIDENCE); rev_reviewer2's reason closely matches that review's wording |
| DEV-MSFT-05 | FIRST_LABEL_AFTER_AI_REVIEW | SUPPORTED | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | rev_som v4 label changed after the AI-prepared label review (v3 SUPPORTED -> v4 INSUFFICIENT_EVIDENCE) |
| DEV-MSFT-06 | DEFINITION_AFTER_AI_REVIEW | CONTRADICTED | CONTRADICTED | CONTRADICTED | rev_som label kept but its definition (profitability = gross margin %) was written after the AI-prepared label review; rev_reviewer2's reason closely matches that review's wording |
| DEV-MSFT-07 | FIRST_LABEL_AFTER_AI_REVIEW | SUPPORTED | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | rev_som v4 label changed after the AI-prepared label review (v3 SUPPORTED -> v4 INSUFFICIENT_EVIDENCE); rev_reviewer2's reason closely matches that review's wording |

These four are excluded from AGREED approval: an independent third person adjudicates them (`adjudication-packet` puts them in the packet with the **pre-review** v3 record, not v4). κ uses v3.

## AI involvement by claim group

- **48 new claims (dev-v0.2):**
  - claim text and design intent were drafted by AI;
  - an AI-filled workbook exists and is excluded;
  - rev_person2's labels agree with that AI workbook on 47/48 claims. This is disclosed as a limitation of the first labels' independence; it rests on the researcher's attestation.
- **24 dev-v0.1 claims:** first labels v1–v3 predate any AI review. v4 is not used for κ or approval.
- **Tools and workbooks** were prepared by the AI analyst; none carries a label, a model output or a first-annotator answer (see the blind audits).

## Per-claim record

| Claim | Type | Version | Author | First (κ) | Second | Status | κ subset | Approval route | AI involvement |
|---|---|---|---|---|---|---|---|---|---|
| DEV-AAPL-01 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AAPL-02 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AAPL-03 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AAPL-04 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 0 |
| DEV-AAPL-05 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: SUPPORTED | DISAGREED | HISTORICAL_DEV_V0_1 | ADJUDICATION (third person) | 1 |
| DEV-AAPL-06 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 0 |
| DEV-AAPL-07 | ambiguous | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | rev_reviewer2: INSUFFICIENT_EVIDENCE | AGREED | HISTORICAL_DEV_V0_1 | ADJUDICATION (third person) | 1 |
| DEV-AAPL-08 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-MSFT-01 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-MSFT-02 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-MSFT-03 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-MSFT-04 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 0 |
| DEV-MSFT-05 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | rev_reviewer2: INSUFFICIENT_EVIDENCE | AGREED | HISTORICAL_DEV_V0_1 | ADJUDICATION (third person) | 1 |
| DEV-MSFT-06 | ambiguous | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | AGREED | HISTORICAL_DEV_V0_1 | ADJUDICATION (third person) | 2 |
| DEV-MSFT-07 | ambiguous | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | rev_reviewer2: INSUFFICIENT_EVIDENCE | AGREED | HISTORICAL_DEV_V0_1 | ADJUDICATION (third person) | 1 |
| DEV-MSFT-08 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AMZN-01 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AMZN-02 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AMZN-03 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-AMZN-04 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 0 |
| DEV-AMZN-05 | interpretive | dev-v0.1 | not recorded (dev-v0.1) | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: INSUFFICIENT_EVIDENCE | AGREED | HISTORICAL_DEV_V0_1 | AGREED (pending approval) | 0 |
| DEV-AMZN-06 | ambiguous | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | AGREED | HISTORICAL_DEV_V0_1 | AGREED (pending approval) | 1 |
| DEV-AMZN-07 | ambiguous | dev-v0.1 | not recorded (dev-v0.1) | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | AGREED | HISTORICAL_DEV_V0_1 | AGREED (pending approval) | 1 |
| DEV-AMZN-08 | numerical | dev-v0.1 | not recorded (dev-v0.1) | rev_som: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 0 |
| DEV-ADBE-01 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-02 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-03 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-04 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-05 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-06 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-07 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-08 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-09 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-10 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-11 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
| DEV-ADBE-12 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-01 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-02 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-03 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-04 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 3 |
| DEV-INTC-05 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-06 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-07 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-08 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-09 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-10 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-INTC-11 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 3 |
| DEV-INTC-12 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 3 |
| DEV-PG-01 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-02 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-03 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-04 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 3 |
| DEV-PG-05 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-06 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-07 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-08 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-09 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-10 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
| DEV-PG-11 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 3 |
| DEV-PG-12 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-01 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-02 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-03 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-04 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-05 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 3 |
| DEV-CAT-06 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-07 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-08 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-09 | interpretive | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: SUPPORTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-10 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: INSUFFICIENT_EVIDENCE | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-11 | ambiguous | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | PRIMARY_44 | AGREED with independent second label, else adjudication | 2 |
| DEV-CAT-12 | numerical | dev-v0.2-new | AI (ai_draft_claude-opus-5-5) | rev_person2: CONTRADICTED | —: — | SINGLE | NUMERICAL_VERIFICATION | AGREED with independent second label, else adjudication | 2 |
