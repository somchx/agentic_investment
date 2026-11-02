# Gold annotation guidelines — financial claim verification

Guideline version: **gold-guidelines-1.0** (record it in every annotation as `guideline_version`).

These guidelines tell independent human reviewers how to label one financial claim about one company as
**SUPPORTED**, **CONTRADICTED** or **INSUFFICIENT_EVIDENCE**, and how to record the evidence for the label.
The labels become the ground truth that the approaches are scored against, so they must be produced
without looking at any approach's output.

## 1. Rules that protect the evaluation

1. **Independence.** Label alone. Do not discuss a claim with another reviewer before both labels are saved.
2. **No model output.** Do not open experiment runs, traces, notebooks 03–06, or ask any LLM about the claim.
   The model under evaluation must never produce or suggest ground truth. (`reviewer_type` must be `human`;
   reviewer ids that look like model names are rejected by the loader.)
3. **Evidence cutoff.** Use only SEC filings in the claim's `allowed_sources` filed **on or before**
   `as_of_date`. A later filing, a later restatement, news, or what you remember happened later must not
   influence the label — even if you know the claim turned out differently.
4. **Held-out claims stay held out.** Gold claims (`gold_claims.jsonl`) are never used to tune prompts,
   retrieval or rules. If a gold claim is needed for development, move it to development and replace it.

## 2. Labels

Judge the claim **as written**, including every material part (figures, direction of change, period,
and any stated cause, driver or attribution).

| Label | Assign when | Typical cases |
|---|---|---|
| **SUPPORTED** | The eligible filings affirmatively establish every material part of the claim. | Figure / direction / threshold checks out for the stated period; a stated cause is stated by the filing itself (MD&A, segment discussion). |
| **CONTRADICTED** | The eligible filings establish that at least one material part is false. | The metric moved the other way or misses the threshold; the filing attributes the change to a different cause; the stated period's figure differs beyond rounding. |
| **INSUFFICIENT_EVIDENCE** | The eligible filings neither establish nor refute a material part. | The number is right but the filing does not state the claimed cause; the period is not yet reported at the cutoff; the claim is vague ("strong", "efficient") and the filings support several readings. |

Decision order:

1. Split the claim into its material parts (e.g. *"operating margin improved"* + *"because operations became more efficient"*).
2. If any part is **shown false** → CONTRADICTED.
3. Else, if every part is **shown true** → SUPPORTED.
4. Else → INSUFFICIENT_EVIDENCE.

Clarifications:

- **A number moving is not its cause.** "Margin rose because of efficiency" needs a passage that says so
  (or that names cost reductions / productivity as the driver). Margin rising alone → INSUFFICIENT_EVIDENCE
  for the causal part.
- **Explicitly different cause** → CONTRADICTED. If the filing says growth was "primarily due to" a
  different segment than the claim names, the attribution is false.
- **"Primarily driven by X"**: SUPPORTED if the filing says so, or segment figures show X contributed more
  than half of the change; CONTRADICTED if they show it did not.
- **Rounding.** A stated figure within normal rounding of the filed figure (e.g. "about 16%" for 16.4%) is true.
- **Restatements.** Use the latest version filed on or before the cutoff.
- **Basis.** Compare like with like (quarter vs same quarter a year earlier; fiscal year vs prior fiscal year;
  balance at period end vs a year earlier). If the claim's basis is ambiguous and the readings disagree,
  label INSUFFICIENT_EVIDENCE and say why in `review_notes`.
- **Absence claims** ("not affected by tariffs") are SUPPORTED only if a filing states the absence or the
  immateriality; CONTRADICTED if a filing discloses the effect; otherwise INSUFFICIENT_EVIDENCE.

## 3. Category guidance (for claim authors)

| Category | Target | What it tests |
|---|---|---|
| `numerical` | ~50 | A figure, threshold or direction checkable from reported statements (revenue growth > 10%, operating margin > 20%, long-term debt decreased). |
| `interpretive` | ~50 | A driver, cause or quality judgement the MD&A / segment notes can confirm or refute (growth driven by a segment; profitability improved due to efficiency; cash generation vs earnings). |
| `ambiguous` | ~50 | Claims where disclosures can point both ways: strong headline results with offsetting disclosures, a conclusion resting on an unverified causal story, or several defensible readings. |

Write claims as an analyst would state them, without hedges that give away the label. Do not write a claim
by first looking at a model's answer. Set `difficulty` before annotation, from the claim text alone.

## 4. Evidence records

For a SUPPORTED or CONTRADICTED label, record at least one evidence item; for INSUFFICIENT_EVIDENCE record the
evidence you checked when it explains the label (e.g. the passage that reports the number but not the cause).

Each evidence item:

```json
{"accession_number": "0001018724-26-000026", "form": "10-Q", "kind": "filing_passage",
 "locator": "MD&A — Operating Income", "quote": "The increase in AWS operating income in Q2 2026 ..."}
```

- `quote` is copied **verbatim** from the filing (one or two sentences). Scoring matches a model citation to
  your evidence when it is the same filing and contains ≥ 80 % of your quote's words, so keep quotes specific.
- For a figure from the financial statements use `"kind": "xbrl_fact"` with `xbrl_concept` (e.g.
  `RevenueFromContractWithCustomerExcludingAssessedTax`) and `period_end`.
- Put supporting items in `supporting_evidence` and refuting ones in `contradictory_evidence` — relative to
  the **claim**, not to your label.

## 5. File format and workflow

One file per reviewer: `datasets/annotations/<reviewer_id>.jsonl`, one JSON object per line:

```json
{"claim_id": "GOLD-AMZN-004", "reviewer_id": "rev_somchai", "reviewer_type": "human",
 "gold_label": "SUPPORTED", "supporting_evidence": [ ... ], "contradictory_evidence": [],
 "review_notes": "MD&A states AWS drove the operating income increase.",
 "annotated_at": "2026-11-10T09:30:00+07:00", "guideline_version": "gold-guidelines-1.0", "time_spent_minutes": 6}
```

1. **Two independent reviewers per claim** (minimum).
2. Notebook 02 shows agreement (Cohen's κ), disagreements, and annotations missing evidence.
3. **Agreement** (both labels equal) finalizes the label.
4. **Disagreement** goes to an adjudicator who did not annotate that claim. The adjudicator reads both
   annotations and the filings, then records the decision with
   `engine.datasets.append_adjudication(Adjudication(claim_id, adjudicator_id, final_label, decision_notes))`.
   Adjudications are append-once: a decision is never overwritten. To change one, publish a new dataset version.
5. Only finalized claims (AGREED or ADJUDICATED) are scored.
6. Report κ before adjudication in the paper.

## 6. When a claim is unusable

Mark it in `review_notes` starting with `UNUSABLE:` (e.g. the period ends after the cutoff, the company has
no eligible filing, the claim mixes two companies) and label it INSUFFICIENT_EVIDENCE. The dataset owner then
removes or rewrites the claim in the next dataset version rather than keeping it in the evaluation set.
