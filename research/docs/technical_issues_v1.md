# Technical issues found in experiment v1 and proposed fixes for v2

- **Scope.** Run `claimverif-main-v1-20261110T104207Z` (frozen: `results/freeze/claimverif-main-v1-20261110T104207Z.json`).
- **Evidence base.** Every count comes from notebook 08 (`results/metrics/<run>__ea_*.csv`). Items marked
  *(manual)* come from the AI-analyst review of the 23 A2/A3 discordant claims, which is awaiting researcher
  confirmation.
- **Status.** None of the issues below has been fixed in v1. The v1 code, prompts, predictions and reference
  labels stay as they are, and the fixes are proposals for a v2 experiment.

## Summary

| # | Issue | Where | v1 extent | Effect on v1 accuracy |
|---|---|---|---|---|
| 1 | Quotes attached to XBRL / derived-metric citations are not validated | `experiments/pipeline.py` `ClaimRun.validate` (l. 145–173) | A3: 7 of 18 quoted XBRL/derived citations misattributed (5 claims); A1/A2: none quoted | none observed (5/5 claims correct); a faithfulness defect |
| 2 | No check that a citation's fiscal period matches the claim | `ClaimRun.validate`; `guard_change` (l. 252) | A3: 13 citations in 10 claims (8.2% of 159 citations on claims stating a period end); A1/A2: 0 | 3 of A3's 15 harmful changes cite wrong-period evidence |
| 3 | Provenance validity is used as if it were support (no entailment check) | `guard_change`: one valid citation suffices for a decisive change | harmed cases: final citations entail the verdict in 0/15 *(manual)* | main driver of A3's −7 net |
| 4 | Overconfident SUPPORTED / CONTRADICTED on INSUFFICIENT_EVIDENCE claims | reconciliation prompt and guard asymmetry | overconfident: A1 23, A2 23, A3 32 of 44 INSUFFICIENT claims; A3 resolved 20/37 abstentions | 10 of A3's 15 harmful changes |
| 5 | Reconciliation output truncated | `max_output_tokens: 1500` (`configs/main_comparison.json`) | 5/150 A3 claims, no final verdict (A3 kept the initial verdict) | small; the stage silently did not run |

## 1. XBRL / derived-metric quote validation

**What happens.**
- `ClaimRun.validate` checks citations in three ways:
  - the evidence id was issued in this run;
  - the evidence belongs to the claim's company;
  - it was filed on or before the cutoff.
- It checks the quote verbatim only when `unit.kind == "filing_passage"`.
- For `xbrl_fact` and `derived_metric` evidence, any quote passes. A model can attach text from a passage to an
  XBRL id, and the citation is still marked `valid: true`.

**Observed in v1.**
- Six XBRL citations and one derived-metric citation in A3 carry quotes that do not contain the cited figure:
  - AMZN-03 E8; AMZN-04 E7;
  - GOOGL-01 E8 and E9 (derived);
  - GOOGL-04 E7 and E8;
  - META-01 E9 (derived).
- Example, GOOGL-04: E8 is the Sep-2025 long-term debt fact, 21,607M. The citation quotes "Total long-term debt
  $ 46,547 $ 125,102", a line from a different filing and period.
- All 5 claims ended correct, so the defect affects the faithfulness of the explanation, not the label.
- Quoted XBRL citations occur only in A3: its reconciliation stage cites ids loosely. Citations that the numeric
  verifier attaches without a quote (A2: 48; A3: 47) are not affected.

**Proposed v2 fix.**
- Validate XBRL / derived quotes by figure. The quote must contain the fact's value at a usual scale (the check
  `engine.error_analysis.value_in_quote` already implements), or it must be empty. Otherwise flag
  `QUOTE_VALUE_MISMATCH` and mark the citation invalid.
- Better still, stop accepting free-text quotes for structured evidence. Render XBRL citations from the fact
  itself (metric, period, value, accession) so they cannot be misquoted.
- Add a unit test with a misattributed XBRL quote, and bump `PROMPT_VERSION` / engine version.

## 2. Wrong-period citations

**What happens.**
- The validator checks `filed <= cutoff` but not that the evidence's period matches the claim's period. The
  numeric verifier does check periods, through `PERIOD_NOT_AVAILABLE` and `BASIS_MISMATCH`. Passages and
  counter-evidence do not get this check.
- A3's counter-retrieval searches the whole eligible corpus. On 75/150 claims it added a filing the initial
  retrieval did not include, often from another period.

**Observed in v1.**
- 13 A3 citations in 10 claims cite a period other than the claim's stated period end: AMZN-11, GOOGL-01,
  GOOGL-11, META-01, MSFT-11 (×2), NFLX-11, NVDA-08 (×2), NVDA-11 (×2), TSLA-03, TSLA-11.
- Of these 10 claims, 4 are correct after the second look, 3 went right → wrong, 3 stayed wrong and 1 went
  wrong → right.
- Examples:
  - NFLX-11 used the FY2025 10-K materiality statement against a Sep-2026 quarter claim.
  - MSFT-11 used Mar-2026 and FY2026 figures for a Sep-2026 quarter claim.
- The measure covers only the 63 claims whose text states "quarter / period / year ended <date>". Fiscal-year
  claims ("fiscal 2025") are not measured, so 8.2% is a lower bound.
- Comparative columns are a legitimate exception: a prior-year figure is often needed for a year-over-year
  claim. Not every mismatch is an error.

**Proposed v2 fix.**
- Add a structured `period` field (period end + basis) to every claim. The gold claims already carry
  `reporting_period` as a fiscal label (e.g. "FY2026 Q1"); v2 should resolve it to a period end and basis
  rather than parse the claim text.
- Tag every evidence unit with its period. Allow a citation's period only if it is:
  - the claim's period;
  - the comparison period of a change claim;
  - explicitly declared by the model as "context".

  Flag anything else as `PERIOD_MISMATCH`.
- In the guard, a verdict change may not rest only on `PERIOD_MISMATCH` citations.
- Restrict counter-retrieval to filings covering the claim's period and its comparison period, unless the
  hypothesis states why another period is relevant.

## 3. Evidence entailment failures

**What happens.**
- `guard_change` lets a verdict move to SUPPORTED or CONTRADICTED when any one supporting (or contradicting)
  citation is provenance-valid.
- Nothing checks that the cited text actually entails the new label. The guard therefore cannot detect a
  relevant but non-entailing passage.

**Observed in v1** *(manual, 23 discordant claims)*.
- In the 15 harmful changes:
  - the counter-evidence was genuine in 10 and partial in 4;
  - the interpretation was wrong in 13 and debatable in 2;
  - the final citations entailed the new verdict in none (no 10, partial 3, n.a. 2).
- Recurring patterns:
  - **evaluative predicates with no criterion:** "resilient", "adequate returns", "fully under control",
    "paying for themselves" (5);
  - **intent or strategy language taken as proof:** AMZN-11, NFLX-12;
  - **accounting-term misreading:** NFLX-09 "marketing" vs "advertising"; WMT-08 membership income in gross
    profit;
  - **level vs change:** NVDA-07;
  - **argument from silence:** TSLA-13, where all three challenges were NO_RELEVANT_EVIDENCE yet the verdict
    went INSUFFICIENT → SUPPORTED;
  - **figures retrieved but not combined:** MSFT-12 free cash flow.
- 7 of the 31 A3 changes happened with no challenge judged supported.

**Proposed v2 fix.**
- **Claim-evidence entailment check.** Before a verdict change is accepted, decompose the claim into its
  atomic assertions (metric, direction, period, causal attribution, evaluative predicate). Require each
  assertion the new label depends on to be linked to a citation that states it.
- **Who checks.** A deterministic check where possible (numeric assertions, already done by XBRL); otherwise a
  separate entailment judgement on the (assertion, quote) pairs only. That judgement would be an extra model
  call, so it needs a cost estimate and your approval before any paid run.
- **No change without a supported challenge.** A change with no CHALLENGE_SUPPORTED assessment is not allowed
  unless the new label is INSUFFICIENT_EVIDENCE.
- **Deterministic arithmetic** for derived quantities the model otherwise skips: free cash flow = operating
  cash flow − purchases of property and equipment; contribution shares; percentage-point changes against the
  comparison period.
- **Evaluate entailment, not only provenance.** Report a citation-entailment rate on a researcher-annotated
  sample. The review workbook prepared for v1 can serve as seed data.

## 4. Overconfident decisions on INSUFFICIENT_EVIDENCE claims

**What happens.**
- The second look turns abstentions into decisive answers. In 20 of 37 claims where A2 said
  INSUFFICIENT_EVIDENCE, A3 committed: 13 to SUPPORTED and 7 to CONTRADICTED.
- The guard deliberately allows moves toward INSUFFICIENT_EVIDENCE without evidence. It applies only the
  "one valid citation" test to moves away from it.

**Observed in v1.**
- Of the 20 resolutions, 5 matched the reference, 10 were INSUFFICIENT_EVIDENCE in the reference, and 5 had the
  opposite label: reference CONTRADICTED, A3 SUPPORTED.
- Predicted INSUFFICIENT_EVIDENCE: A3 21, A2 37, reference 44.
- Overconfident decisive answers on the 44 INSUFFICIENT claims: A1 23, A2 23, A3 32.
- Losses concentrate in Ambiguous claims, 23/50 of which are INSUFFICIENT_EVIDENCE in the reference.
  - Accuracy on Ambiguous claims: A2 52%, A3 38%.
  - Changes on Ambiguous claims: 11 harmful, 4 helpful.
- Under the lenient scoring, which accepts every such answer, A3 edges past A2 (+1.3 pts, p = 0.77). Under the
  researcher's case-by-case adjudication, only 5 of 44 decisive answers were acceptable.

**Proposed v2 fix.**
- **Decidability check before reconciliation.** If an evaluative predicate in the claim has no criterion
  stated in the claim or the filings, and no supplied definition, the claim stays INSUFFICIENT_EVIDENCE.
  The model must name the criterion it applies, and the guard checks that the criterion is quoted from the
  filing.
- **Symmetric guard.** A move from INSUFFICIENT_EVIDENCE to a decisive label needs at least one
  CHALLENGE_SUPPORTED assessment and an entailing citation (issue 3), not just any valid citation.
- **Ablation option.** Run the second look only on decisive initial verdicts (its stated purpose is to
  challenge a verdict). This tests whether the losses come from resolving abstentions.
- **Report abstention calibration.** Report abstention precision and recall alongside accuracy, so the
  trade-off is visible rather than hidden in one number.

## 5. Truncated reconciliation (secondary)

- **What happened.** For GOOGL-12, KO-10, KO-14, NFLX-10 and TSLA-08, the reconciliation response hit the
  1,500-token limit. A3 therefore kept the initial verdict, and these claims count as "A3" although the second
  look did not run.
- **Proposed v2 fix.** Raise the limit for the reconciliation stage only (e.g. 3,000), or shorten its
  required output (cap quotes per assessment). Report the count of incomplete second looks as a primary
  metric.

## Proposed v2 protocol

The v1 run stays frozen and tagged; v2 gets new version numbers and a new run id.

1. **Develop on the development split only.** Implement fixes 1–5 and bump the version numbers
   (`PROMPT_VERSION`, numeric / reconcile rule versions, `GRAPH_VERSION`). Add offline tests for each new
   check.
2. **Pre-register v2.** State in `configs/` the planned comparisons, A2 vs A3-v2 and A3-v1 vs A3-v2, before
   touching the gold split.
3. **Estimate cost before any paid run.** Use `--plan`, which reports the upper bound. The extra entailment
   judgement roughly adds one call per changed verdict. A gold run needs your explicit approval and a
   `--max-cost` cap.
4. **Compare on the same frozen inputs.** Use the same gold claims, reference v3-approved and corpus, under
   the strict, adjudicated and lenient scorings, and add citation-entailment and period-mismatch rates as
   secondary outcomes.
5. **Test run-to-run variance.** Repeat the live run at least twice with separate cache directories to
   estimate variance. v1 has a single run.
