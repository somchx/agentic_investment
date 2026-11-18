# dev-v0.2 reference-label status

Claims: 72. Status: ADJUDICATED 1, AGREED 7, SINGLE 64. Approved final labels: 0/72.

## Disagreements requiring adjudication

- none

## Independent second annotation required (44: SINGLE ambiguous / interpretive)

DEV-AAPL-04, DEV-AAPL-06, DEV-MSFT-04, DEV-AMZN-04, DEV-ADBE-01, DEV-ADBE-02, DEV-ADBE-03, DEV-ADBE-04, DEV-ADBE-05, DEV-ADBE-06, DEV-ADBE-07, DEV-ADBE-08, DEV-ADBE-09, DEV-INTC-01, DEV-INTC-02, DEV-INTC-03, DEV-INTC-04, DEV-INTC-05, DEV-INTC-06, DEV-INTC-07, DEV-INTC-08, DEV-INTC-09, DEV-INTC-10, DEV-INTC-12, DEV-PG-01, DEV-PG-02, DEV-PG-03, DEV-PG-04, DEV-PG-05, DEV-PG-06, DEV-PG-07, DEV-PG-08, DEV-PG-09, DEV-CAT-01, DEV-CAT-02, DEV-CAT-03, DEV-CAT-04, DEV-CAT-05, DEV-CAT-06, DEV-CAT-07, DEV-CAT-08, DEV-CAT-09, DEV-CAT-10, DEV-CAT-11

## Second annotation optional (20: SINGLE numerical)

DEV-AAPL-01, DEV-AAPL-02, DEV-AAPL-03, DEV-AAPL-08, DEV-MSFT-01, DEV-MSFT-02, DEV-MSFT-03, DEV-MSFT-08, DEV-AMZN-01, DEV-AMZN-02, DEV-AMZN-03, DEV-AMZN-08, DEV-ADBE-10, DEV-ADBE-11, DEV-ADBE-12, DEV-INTC-11, DEV-PG-10, DEV-PG-11, DEV-PG-12, DEV-CAT-12

## First labels decided after the AI-prepared label review (v4 differs from v3; not independent of AI assistance) (3)

DEV-AAPL-07, DEV-MSFT-05, DEV-MSFT-07

## Second-review files that are not usable

- rev_person3: dev_blind_review_dev-v0.2_40_{filled,reviewed}.xlsx: content identical to the Codex-filled workbook; not imported, not usable for κ
- ai_codex_dev48: AI-filled workbook; not a human label

## Claims without an approved final label (72)

All of them: no approved reference-label file exists yet (`datasets/annotations_dev/dev-v0.2_reference_labels.approved.jsonl`). AGREED / ADJUDICATED labels still need to be approved into that file.

| claim | type | status | first | second | needs |
|---|---|---|---|---|---|
| DEV-AAPL-01 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-AAPL-02 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-AAPL-03 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-AAPL-04 | interpretive | SINGLE | rev_som: SUPPORTED | —: — | 2nd annotation |
| DEV-AAPL-05 | interpretive | ADJUDICATED | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: SUPPORTED | approval |
| DEV-AAPL-06 | interpretive | SINGLE | rev_som: CONTRADICTED | —: — | 2nd annotation |
| DEV-AAPL-07 | ambiguous | AGREED | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: INSUFFICIENT_EVIDENCE | approval |
| DEV-AAPL-08 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-MSFT-01 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-MSFT-02 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-MSFT-03 | numerical | SINGLE | rev_som: CONTRADICTED | —: — | 2nd (optional) |
| DEV-MSFT-04 | interpretive | SINGLE | rev_som: SUPPORTED | —: — | 2nd annotation |
| DEV-MSFT-05 | interpretive | AGREED | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: INSUFFICIENT_EVIDENCE | approval |
| DEV-MSFT-06 | ambiguous | AGREED | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | approval |
| DEV-MSFT-07 | ambiguous | AGREED | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: INSUFFICIENT_EVIDENCE | approval |
| DEV-MSFT-08 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-AMZN-01 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-AMZN-02 | numerical | SINGLE | rev_som: CONTRADICTED | —: — | 2nd (optional) |
| DEV-AMZN-03 | numerical | SINGLE | rev_som: CONTRADICTED | —: — | 2nd (optional) |
| DEV-AMZN-04 | interpretive | SINGLE | rev_som: SUPPORTED | —: — | 2nd annotation |
| DEV-AMZN-05 | interpretive | AGREED | rev_som: INSUFFICIENT_EVIDENCE | rev_reviewer2: INSUFFICIENT_EVIDENCE | approval |
| DEV-AMZN-06 | ambiguous | AGREED | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | approval |
| DEV-AMZN-07 | ambiguous | AGREED | rev_som: CONTRADICTED | rev_reviewer2: CONTRADICTED | approval |
| DEV-AMZN-08 | numerical | SINGLE | rev_som: SUPPORTED | —: — | 2nd (optional) |
| DEV-ADBE-01 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-02 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-03 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-04 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-ADBE-05 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-06 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-07 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-ADBE-08 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-ADBE-09 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-ADBE-10 | numerical | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd (optional) |
| DEV-ADBE-11 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
| DEV-ADBE-12 | numerical | SINGLE | rev_person2: SUPPORTED | —: — | 2nd (optional) |
| DEV-INTC-01 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-02 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-03 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-04 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-INTC-05 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-INTC-06 | interpretive | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-INTC-07 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-08 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-INTC-09 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-10 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-INTC-11 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
| DEV-INTC-12 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-PG-01 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-PG-02 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-PG-03 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-PG-04 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-PG-05 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-PG-06 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-PG-07 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-PG-08 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-PG-09 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-PG-10 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
| DEV-PG-11 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
| DEV-PG-12 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
| DEV-CAT-01 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-02 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-03 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-04 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-CAT-05 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-CAT-06 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-07 | interpretive | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-08 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-CAT-09 | interpretive | SINGLE | rev_person2: SUPPORTED | —: — | 2nd annotation |
| DEV-CAT-10 | ambiguous | SINGLE | rev_person2: INSUFFICIENT_EVIDENCE | —: — | 2nd annotation |
| DEV-CAT-11 | ambiguous | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd annotation |
| DEV-CAT-12 | numerical | SINGLE | rev_person2: CONTRADICTED | —: — | 2nd (optional) |
