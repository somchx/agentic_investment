# Research methodology

*Evaluating Contradiction-Aware Agentic AI for Evidence-Grounded Financial Claim Verification*

## 1. Research question and hypotheses

**RQ.** Does contradiction-aware investigation improve the accuracy and evidence grounding of financial claim
verification compared with conventional RAG and RAG with deterministic financial verification?

- **H1 (main).** A3 (contradiction-aware) achieves higher accuracy / macro-F1 than A2 (RAG + deterministic
  verification) on the same claims.
- **H2 (mechanism).** A3 outperforms SR (self-reflection), i.e. the gain comes from contradiction-directed
  evidence retrieval, not from giving the model a second look.
- **H3 (grounding).** A3 has a lower unsupported-conclusion rate and equal or higher evidence precision/recall.
- **Exploratory.** For which claim categories (numerical / interpretive / ambiguous) does A3 help or harm?

Planned comparisons are fixed in `configs/main_comparison.json` (`main`: A2 vs A3; `second_look_control`:
SR vs A3; `numeric_stage`: A1 vs A2). Anything else is reported as exploratory.

## 2. Task definition

Input (`ClaimInput`): `claim_id`, `company` (ticker), `claim` (text), `as_of_date` (evidence cutoff),
`allowed_sources` (`SEC_10K`, `SEC_10Q`, optionally `SEC_8K`), optional `reporting_period`.

Output (per approach, per claim): `predicted_label` ∈ {SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE},
`initial_label`, `supporting_evidence`, `contradicting_evidence`, `citations` (each validated), `reasoning_summary`,
`investigation_trace_id`, `token_usage` {input, output}, `latency_ms`, `estimated_cost_usd`, `stop_reason`, plus
approach-specific records (numeric checks, contradiction investigation, reflection). Label definitions are the
same in the system prompt and the annotation guidelines.

## 3. Evidence corpus and point-in-time control

- Corpus: SEC EDGAR filings of the claim's company. A filing is eligible iff its form is in the claim's allowed
  sources **and** `filed ≤ as_of_date`. The filter is applied before any text is read.
- Per claim the retriever indexes the most recent eligible 10-K (1) and 10-Qs (2) (`max_filings_per_form`).
- Text: the primary document, cleaned (inline-XBRL header, scripts and styles removed; `clean-1.0`), split into
  ~1,200-character passages with 200-character overlap, ranked by BM25 (`bm25-1.0`). Passage ids
  (`accession:start-end`) are stable across runs.
- Numbers: XBRL company facts restricted to 10-K/10-Q facts with `filed ≤ as_of_date`; the latest version of a
  period filed by the cutoff is used and restated versions are counted.
- Provenance: every passage / fact / computed figure is an `EvidenceUnit` with accession number, form, filing
  date, period, source URL and locator. Models can cite only ids issued in their own run.
- Reproducibility: the run manifest records sha256 of the company-facts files and `corpus.json` the sha256 of
  every document used. Experiments read the cache directly and never refresh it.

## 4. Approaches

All share: the same system prompt, the same initial instruction and verdict tool, the same retrieval
configuration, the same model snapshot (`claude-sonnet-4-5-20250929` by default, from `agent_config.MODEL`),
temperature 0, the same output cap per call, the same per-claim budget. The initial model request is
**byte-identical** across the four approaches (tested), so it is served once from the response cache and every
approach starts from the same initial verdict.

**A1 — Conventional RAG.** Claim (+ reporting period) as the query → top-6 passages → one model call →
label. The model also lists `numeric_assertions` (schema shared with A2) but nothing checks them.

**A2 — RAG + deterministic financial verification.** A1, then each numeric assertion (metric, measure,
basis, period, comparison, threshold, stated value) is recomputed from XBRL facts with no model involvement:
concept supported? period available at the cutoff with the right basis? ratio units as decimals? stated value
within rounding (±0.6 pp for ratios, ±1.5 % for amounts)? relation holds? Result: TRUE / FALSE / UNVERIFIABLE.
Deterministic reconcile rule (`numeric-reconcile-1.0`):

| numeric checks | final label |
|---|---|
| none (qualitative claim) | model label |
| any FALSE | CONTRADICTED |
| all TRUE, claim type numeric | SUPPORTED |
| all TRUE, claim interpretive / mixed | model label (a number moving does not establish its cause) |
| some UNVERIFIABLE, none FALSE | model label (flagged) |

**A3 — Contradiction-aware (proposed).** A2's result is the initial verdict. Then:
1. *Contradiction investigation* — the model writes up to 3 questions that could challenge that verdict (did
   the metric move as stated; was it the stated cause or mix / pricing / currency / one-time / accounting
   effects; do other disclosures weaken it), each with an English search query and optionally a numeric check.
2. The retriever returns up to 3 **new** passages per query (passages already shown are excluded); requested
   numeric checks are computed deterministically.
3. *Reconciliation* — the model assesses each challenge (CHALLENGE_SUPPORTED / CHALLENGE_REFUTED /
   NO_RELEVANT_EVIDENCE) with cited evidence and gives the final label and whether / why it changed.
4. *Guards* (deterministic, shared with SR): a challenge asserted without a valid citation is downgraded and
   flagged; a change **to** SUPPORTED or CONTRADICTED without a valid citation for it is reverted to the initial
   verdict; a change to INSUFFICIENT_EVIDENCE (the cautious direction) is allowed. Then A2's numeric rule is
   re-applied.

Stored: initial verdict, hypotheses, queries, retrieved counter-evidence ids, counter numeric checks, per-challenge
assessments (declared vs accepted), final verdict, whether / why it changed, guard decisions.
Ablation switches: `contradiction.enabled`, `counter_retrieval`, `counter_numeric_checks`, `max_hypotheses`.

**SR — Self-reflection control.** A2's result, then a self-critique call (up to 3 weaknesses — the same number as
A3's hypotheses) and a revision call that assesses each weakness on the evidence already supplied. No new
retrieval, no numeric checks of its own, same guards and numeric re-application, same call count (3) and output
cap as A3. A3 − SR therefore estimates the contribution of contradiction-directed retrieval itself.

## 5. Fairness and leakage controls

- Same claims, corpus, cutoffs, model, temperature, prompt, retrieval config and per-claim budget for every
  approach in an experiment; `config.fairness_problems` refuses configs whose approaches differ in `llm`,
  `retrieval` or `budget`, or whose SR critique size differs from A3's hypothesis count.
- Each approach gets a frozen (read-only) copy of its config; its hash is stored with each prediction.
- Model input is built from `ClaimInput` by whitelist; a claim record that carries label / reviewer / gold
  evidence fields is refused. A test plants a canary string in an annotation and asserts that no model request
  contains it, nor any gold / reviewer / category / difficulty field.
- Development and gold claims live in separate files; ids and normalised texts must not overlap; running on the
  gold split requires an explicit `allow_gold=True`.
- Gold labels come only from human reviewers (`reviewer_type == "human"`, model-like reviewer ids rejected).
- Known residual leakage: the model may remember post-cutoff facts from pre-training. The prompt forbids using
  them and every citation is checked against the cutoff, but a label could still be influenced. Mitigations to
  consider: cutoffs before the model's training cutoff, or claims whose ground truth is not public knowledge.

## 6. Gold dataset

- Target ≈150 claims: ≈50 numerical, ≈50 interpretive, ≈50 ambiguous; AAPL / MSFT / AMZN first, other tickers
  with a known CIK supported.
- Annotation schema (per reviewer): claim id, reviewer id / type, label, supporting and contradictory evidence
  (accession, form, locator, verbatim quote or XBRL concept + period), notes, timestamp, guideline version.
  Claim records hold company, text, category, reporting period, evidence cutoff, allowed sources, relevant
  filings, difficulty.
- ≥2 independent reviewers per claim; agreement finalizes; disagreements go to an adjudicator (append-once
  record). Only AGREED / ADJUDICATED claims are scored. Report Cohen's κ before adjudication.
- Guidelines: `datasets/annotation_guidelines.md`.

## 7. Metrics

- **Classification** (finalized gold only): accuracy; per-class precision, recall, F1; macro-F1 over classes
  present in the gold set; 3×3 confusion matrix plus a NO_PREDICTION column (errors count as wrong).
- **Evidence:** evidence precision = matched valid citations / valid citations; evidence recall = gold evidence
  references matched / gold references. A citation matches a reference if it is the same filing and its passage
  contains ≥80 % of the reference quote's words (XBRL: same filing and period). Undefined values stay empty.
- **Unsupported-conclusion rate:** share of SUPPORTED / CONTRADICTED predictions without a valid citation
  backing that label (unknown id, wrong company, post-cutoff, or quote not verbatim → invalid). Gold-free.
- **Second-look analysis (A3, SR):** change rate, initial → final transitions, helped (wrong→right), harmed
  (right→wrong), false contradictions (final CONTRADICTED, gold not), challenges asserted without valid evidence,
  guard reversions — by claim category.
- **Efficiency:** latency, input / output tokens, LLM calls, estimated cost (pricing version recorded) — averaged
  only over rows that measured them, with counts.
- Grouping: approach × company / claim category / difficulty.

## 8. Statistical analysis

- **McNemar's test** on paired per-claim correctness (A2 vs A3; SR vs A3). The exact binomial p-value is primary
  (preferred when discordant pairs < 25); the continuity-corrected χ² is reported for reference.
- **Paired bootstrap** (claims resampled with replacement, 5,000 resamples, fixed seed) for the difference in
  accuracy and in macro-F1, percentile 95 % CI.
- **Effect size:** accuracy / macro-F1 difference with CI; discordant-pair odds ratio (Haldane-corrected).
- **Sample size:** report n paired claims and claims dropped (no gold / unpaired). With ≈150 claims and a
  10-point accuracy difference the test has modest power; per-category results are exploratory.
- **Interpretation:** a significant result applies to this claim set, model snapshot, corpus and prompt version.
  Claims about the same company and period share filings, so effective n is below the claim count; per-company
  results are reported alongside. Two planned comparisons; further ones are exploratory or Holm-corrected.

## 9. Reproducibility record

Each run directory stores: config and per-approach config hashes; model, temperature, pricing version; prompt
version and hashes of the system prompt, instructions and tool schemas; numeric / reconcile / retrieval /
cleaning versions; app agent-workflow and evidence-gate versions; git commit, dirty flag and sha256 of every
research and relevant core source file; dataset path, sha256 and claim ids; XBRL file hashes; corpus document
hashes; budgets and evidence-cutoff rule; LLM mode and (for paid runs) the approval cap. Completed runs are made
read-only with SHA256SUMS (`verify_run_integrity`). Model responses are cached by full-request hash, so a run
can be replayed offline.

## 10. Limitations and outstanding work

1. **No gold labels and no held-out claims yet.** Accuracy, macro-F1, evidence P/R and the statistical tests
   cannot be computed on real data until annotation is done.
2. **No real-model run yet.** Only mock runs exist; the first paid run needs explicit approval (pilot first).
3. **Retrieval scope.** Main 10-K/10-Q documents only; exhibits and 8-K earnings releases are not indexed by
   default; BM25 is lexical (no embeddings).
4. **Fiscal Q4.** Apple's fourth-quarter figures are not derived from FY − 9M (only Microsoft's are, in the app's
   extractor), so claims about Apple's fiscal Q4 quarter return UNVERIFIABLE numeric checks. (The app's known AMZN
   earnings-release column issue affects the 8-K cross-check tool, which this pipeline does not use.)
5. **Numeric assertions come from the model.** A mis-extracted assertion (wrong period or basis) produces a wrong
   deterministic check; these cases are visible in the trace and should be counted in error analysis.
6. **Numeric override.** Because A2's numeric rule is re-applied after the second look, A3 and SR cannot change
   labels of purely numeric claims whose checks are all TRUE or any FALSE; their effect is expected mainly on
   interpretive and ambiguous claims (a design choice, switchable with `numeric.override_final_label`).
7. **Pre-training knowledge** (see §5).
8. **Mock LLM** is a keyword heuristic; it validates plumbing only.
9. **Variance.** Temperature 0 is not fully deterministic; repeated live runs are needed to estimate run-to-run
   variation.
