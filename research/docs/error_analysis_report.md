# Post-experiment error analysis: why A3 did not outperform A2

Run `claimverif-main-v1-20261110T104207Z` (offline replay of live run `…091252Z`), 150 gold claims, reference
Final Gold v3 (approved). Analysis notebook: `notebooks/08_error_analysis.ipynb` (executed copy in
`results/executed_notebooks/`). Every number below is recomputed from the frozen predictions and traces.

Each finding has two parts. **Observed** is a count or measurement that anyone can reproduce from the
artifacts. **Interpretation** is a reading of those observations. The hypotheses in §4 are explanations that
this experiment did not test.

## 1. Integrity of the analysis

- **Frozen before analysis.** `scripts/freeze_experiment.py` wrote `results/freeze/claimverif-main-v1-20261110T104207Z.json`
  (read-only). It records:
  - the SHA-256 of the canonical and live run directories (both pass `verify_run_integrity`);
  - the config and per-approach config hashes;
  - the model (`claude-sonnet-4-5-20250929`, temperature 0) and prompt version `claim-prompts-1.0`, whose
    prompt, instruction and tool hashes match the current code (no drift);
  - the gold claims, development claims, corpus manifest, reference workbook, both adjudication variants and
    their source workbooks;
  - all 450 cached model responses the run replays from (0 missing);
  - the 21 result tables and figures that existed at freeze time;
  - the strict, adjudicated and lenient scores recomputed from the predictions.

  After the analysis, `--verify` reports 0 changed and 0 removed items. The 15 added items are the new notebook
  08 outputs.
- **No paid calls, no tuning.** No prompt, configuration, reference label or run file was modified, and no model
  was called. All new code is analysis-only, and 149 offline tests pass (10 new).
- **Git state.** Nothing has been committed yet (the manifest records `dirty: true`). The freeze record stands
  in for a commit until the work is committed and tagged.

## 2. Sensitivity scorings: provenance check

| Scoring | Source | Decisions | Re-read of workbook |
|---|---|---|---|
| strict (primary) | none | — | — |
| adjudicated | `INSUFFICIENT_adjudication_filled.xlsx` | 5 / 44 ACCEPTABLE | identical, 44/44 cases |
| lenient (upper bound) | `INSUFFICIENT_adjudication__claimverif-main-v1-20261110T104207Z.xlsx` | 44 / 44 ACCEPTABLE | identical, 44/44 cases |

- **Variants stay separate.** Each variant lives in its own file and records its source workbook and
  adjudicator. Swapping the workbooks makes the consistency check fail, so the check is discriminating.
- **Strict results are unchanged.** Recomputed: A1 62.67%, A2 68.67%, A3 64.00%.
  - A2 → A3: −4.67 pts [−10.67, +1.33], McNemar exact p = 0.210 (15 vs 8 discordant).
  - A1 → A2: +6.00 pts [+2.00, +10.67], p = 0.012.
- **Problem found (not fixed).** `results/metrics/claimverif-main-v1-20261110T104207Z__adjudicated_accuracy.csv`
  (written 10:13) is a superseded table. Its column `adjudicated_accuracy` holds the **lenient** scores
  (0.78 / 0.84 / 0.853). It was left in place because existing results are not modified. Report
  `__accuracy_by_scoring.csv` instead, and delete or rename the stale file once you decide.

## 3. Findings

### F1. Every A2/A3 difference comes from the A3 second look

- **Observed.**
  - A3's initial verdict equals A2's final verdict on 150/150 claims: same initial request, same numeric
    verification.
  - The second look changed 31 verdicts: 8 wrong → right, 15 right → wrong, 8 wrong → still wrong. Net −7
    claims (−4.7 pts).
  - The A2-vs-A3 2×2 table is therefore exactly A3's initial-vs-final transition table: both correct 88, only A2
    15, only A3 8, both wrong 39.
- **Interpretation.** The comparison measures the net effect of one added stage. Retrieval, model and initial
  prompt do not differ.

### F2. The losses are concentrated in Ambiguous claims

| Category (n = 50 each) | A1 | A2 | A3 | A3 changes: helped / harmed |
|---|---|---|---|---|
| Numerical | 76% | 94% | 96% | 1 / 0 |
| Interpretive | 62% | 60% | 58% | 3 / 4 |
| Ambiguous | 50% | 52% | 38% | 4 / 11 |

- **Observed.**
  - 11 of the 15 harmful changes are Ambiguous claims.
  - Numerical claims are nearly unaffected: A2's deterministic XBRL check already settles them, and A1 → A2 is
    +18 pts here.
  - In the reference, 23 of the 50 Ambiguous claims are INSUFFICIENT_EVIDENCE, against 16/50 Interpretive and
    5/50 Numerical.
- **Interpretation.** Per-category tests are exploratory (n = 50, 15 discordant pairs in Ambiguous).

### F3. The second look mostly resolves abstentions, and the reference often says abstention was right

- **Observed.**
  - Direction of the 31 changes:
    - INSUFFICIENT → decisive: 20 (13 to SUPPORTED, 7 to CONTRADICTED);
    - SUPPORTED ↔ CONTRADICTED: 7;
    - decisive → INSUFFICIENT: 4.
  - A3 resolved 20 of the 37 claims where A2 abstained. Of those 20:
    - 5 matched the reference;
    - 10 were INSUFFICIENT_EVIDENCE in the reference (overconfident);
    - 5 went to the opposite decisive label (all reference CONTRADICTED, A3 SUPPORTED).
  - Label distribution:
    - A3 predicts INSUFFICIENT_EVIDENCE on 21 claims, against 37 for A2 and 44 in the reference.
    - SUPPORTED predictions rise from 69 (A2) to 84; the reference has 68.
  - Error types, A2 → A3:
    - over-abstention 16 → 9;
    - overconfident SUPPORTED 12 → 19;
    - overconfident CONTRADICTED 11 → 13;
    - SUPPORTED ↔ CONTRADICTED 8 → 13.
- **Interpretation.** A3 trades 7 fewer abstention errors for 14 more commitment errors (+7 overconfident SUPPORTED, +2 overconfident CONTRADICTED, +5 SUPPORTED ↔ CONTRADICTED), a net loss of 7 claims. Its main behavioural
  effect is to make the system more decisive, and in particular more likely to say SUPPORTED. Under the strict
  reference, which treats 29% of claims as undecidable from the filings, this is penalised.

### F4. Counter-evidence was usually real; the failures were in interpreting it

- **Observed: automatic checks, all 150 A3 claims.**
  - Assessment of the 435 hypotheses: 193 NO_RELEVANT_EVIDENCE (44%), 171 CHALLENGE_REFUTED (39%),
    71 CHALLENGE_SUPPORTED (16%). All 71 supported challenges cite at least one provenance-valid passage.
  - Counter-retrieval brought a filing not in the initial retrieval on 75/150 claims.
  - 7 of the 31 changes happened with no challenge judged supported (for example TSLA-13: all three
    NO_RELEVANT_EVIDENCE, yet INSUFFICIENT → SUPPORTED).
  - 5 reconciliations ended without a final verdict (output truncated at `max_output_tokens`; A3 then keeps the
    initial verdict). The guard reverted 5 changes made without valid evidence.
- **Observed: manual review of the 23 discordant claims.** Source:
  `datasets/error_analysis/discordant_case_review__<run>.csv`. Read from the traces by an AI analyst and
  **not yet researcher-verified**.

  | | Genuine counter-evidence (yes / partial / no) | Interpreted correctly (yes / debatable / no) | Final citations entail verdict (yes / partial / no / n.a.) |
  |---|---|---|---|
  | Harmed (15) | 10 / 4 / 1 | 0 / 2 / 13 | 0 / 3 / 10 / 2 |
  | Helped (8) | 7 / 0 / 1 | 7 / 1 / 0 | 4 / 3 / 0 / 1 |

  - Mechanisms in the harmful changes:
    - decisive answer to a claim whose key predicate has no criterion ("resilient", "adequate returns",
      "fully under control", "paying for themselves", "deteriorating"): 5;
    - management intent or strategy text taken as proof: 2;
    - accounting-term misreading: 2 (NFLX-09 "marketing" vs "advertising" for the same $222M; WMT-08
      membership income treated as part of gross profit);
    - one case each:
      - argument from silence (TSLA-13);
      - level read as change (NVDA-07: 2.6 pp FY2026 H20 effect, ignoring the 2.3 pp prior-year effect in the
        same sentence);
      - FY2025 statement applied to a Q3 2026 claim (NFLX-11);
      - free cash flow not computed from available figures (MSFT-12);
      - over-literal premise (GOOGL-15);
      - over-strict causal requirement (TSLA-07).
  - The helpful changes were mostly real missing evidence found: 5 cases (GOOGL-04, KO-09, KO-12, NFLX-13,
    NVDA-11). The others were a segment-rename scope correction (MSFT-08), re-reasoning on the same evidence
    (META-06) and a re-judged threshold (MSFT-13).
- **Interpretation.**
  - Retrieval is not the bottleneck. The investigation finds relevant filings, and the harm arises when the
    model draws a decisive conclusion the evidence does not license.
  - 3 of the 23 readings are marked "debatable" (AAPL-12, KO-11, MSFT-13). There the reference itself is open to
    argument.

### F5. Valid citations are not the same as supporting evidence

- **Observed.**
  - **Leakage:** 0 future-data citations in any approach (independently recomputed from the evidence ledger).
  - **Pipeline validity rate:** A1 93.2%, A2 94.5%, A3 92.9%.
  - **Unchecked quotes.**
    - The pipeline checks passage quotes verbatim but not quotes attached to XBRL facts or derived metrics.
    - A3 has 65 such citations. 18 of them carry a quote, and in 7 of those the quote does not contain the cited
      figure (misattribution). Example: GOOGL-04 attributes "Total long-term debt $ 46,547 $ 125,102" to an
      XBRL fact whose value is 21,607M.
    - A1 and A2 have no quoted XBRL citations.
  - **Period alignment:** 8.2% of A3's citations on claims that state a period end come from another period, in
    10 claims. A1 and A2 have 0%.
  - **Entailment of the harmed cases:** all 15 carry provenance-valid citations, yet in none of them do the
    final citations entail the verdict (manual review).
- **Interpretation.** Citation validity measures provenance, not support. The extra retrieval rounds widen the
  evidence pool across periods and evidence types, and A3's citations become less tightly bound to the claim.

### F6. A3 costs about 4× more per claim

| Per claim | A1 | A2 | A3 |
|---|---|---|---|
| LLM calls | 1 | 1 | 3 |
| Tool calls (retrieval + numeric) | 1.00 | 1.43 | 4.92 |
| Input / output tokens | 3,927 / 516 | 3,927 / 516 | 17,840 / 1,878 |
| Estimated API cost | $0.020 | $0.020 | $0.082 |
| Mean latency (live run) | 9.9 s | 9.9 s | 34.5 s (n = 148) |
| Cost per correct answer | $0.031 | $0.028 | $0.128 |

- **Observed.**
  - Total estimated cost: $2.93 for A1, $2.93 for A2 and $12.25 for A3 (A1 and A2 share the identical initial
    request).
  - Latency is summed from live per-request timings. Two A3 claims lack them (AMZN-10, KO-08, whose live traces
    failed).
  - In the live run, 7 A3 claims ended with an error: 5 truncated reconciliations and 2 exceptions fixed before
    the canonical replay.
- **Interpretation.** A3 is about 4.6× more expensive per correct answer, with no accuracy gain.

### F7. The ranking reverses only under lenient scoring

- **Observed.**
  - Strict: A2 → A3 −4.7 pts (p = 0.21). Adjudicated: −4.0 pts (p = 0.29). Lenient: +1.3 pts (p = 0.77).
  - Under lenient scoring, 32 of A3's decisive answers on INSUFFICIENT claims are accepted, against 23 for A2.
  - A1 → A2 is +6.0 pts (p = 0.012) under all three scorings.
- **Interpretation.** The lenient reversal comes from the same behaviour as F3: A3 answers decisively more often.
  It is an upper bound, not a gain. When a person judged those answers case by case, only 5 of 44 were
  acceptable.

## 4. Why A3 may not outperform A2: hypotheses (not tested here)

Each hypothesis is supported by the findings above, but none was isolated experimentally. Testing them needs new
runs on the development split, which require approval.

1. **The second look works as a second retrieval round, not as falsification.** Many hypotheses are phrased as
   searches for support ("Does the filing contain … that would support the claim?"). 13 of 20 resolutions went
   to SUPPORTED, and 7 changes had no supported challenge (F3, F4).
   *Test:* code each hypothesis's polarity on the development split, or ablate the second look for initial
   INSUFFICIENT verdicts (`configs/ablation_contradiction.json`).
2. **Evaluative claims lack a decision criterion.** More evidence raises the model's confidence without making
   the claim decidable. This mechanism is the most frequent in the harmed cases (F4).
   *Test:* add a decidability check before reconciliation and measure on development claims first.
3. **The errors are interpretive, and the guards check provenance only.** The guard blocks changes without valid
   evidence. It cannot detect a valid citation that does not entail the verdict, a cross-period citation or an
   uncomputed derived figure (F4, F5). A2's gains on Numerical claims came from a deterministic check.
   *Test:* extend deterministic checks to period alignment, derived metrics such as FCF, and XBRL quote fidelity.
4. **The reference rewards abstention on ambiguous claims.** 29% of reference labels, and 46% of Ambiguous ones,
   are INSUFFICIENT_EVIDENCE. A method that makes the system more decisive is penalised under strict scoring,
   whatever the quality of its reasoning (F2, F3, F7). The reference is LLM-annotated with AI-assisted
   adjudication and researcher review, not independent human gold.
5. **Statistical power is limited.** 23 discordant pairs give wide intervals (−10.7 to +1.3 pts). The data are
   consistent with A3 being somewhat worse or roughly equal to A2. They are not consistent with a large A3
   advantage.

## 5. Limitations of this analysis

- **Single unverified reviewer.** The mechanism coding and entailment judgements come from one AI analyst and are
  not researcher-verified. Columns `researcher_confirmed` and `researcher_note` are provided for that.
- **Partial manual coverage.** Only the 23 discordant claims were reviewed manually. The 8 changes that stayed
  wrong and the unchanged errors were analysed automatically only.
- **Entailment is not measured automatically.** The automatic checks cover provenance, cutoff, period and XBRL
  quote fidelity.
- **Latency.** It comes from a single sequential live run, with network conditions of that day.
- **Cost.** Costs use list prices (`anthropic-2025-09:sonnet-4.5`).
- **Scope.** All results hold for one model snapshot, one prompt version, 10 companies and 150 claims.

## 6. Summary for Results and Discussion

**Results.**

- **Main comparison.** On 150 claims scored strictly against the Final Gold v3 reference, deterministic numeric
  verification improved conventional RAG from 62.7% to 68.7% (+6.0 pts, 95% CI [+2.0, +10.7], McNemar
  p = 0.012). The contradiction-aware second look reached 64.0% (−4.7 pts vs A2, 95% CI [−10.7, +1.3],
  p = 0.21).
- **How A3 differs from A2.** A3 starts from A2's final verdict on every claim, so the difference is entirely
  due to the second look. It changed 31 verdicts: 8 wrong → right, 15 right → wrong, 8 still wrong.
- **Where the changes landed.** Changes were concentrated in Ambiguous claims (A2 52% vs A3 38%). Numerical
  claims were unaffected (94% vs 96%).
- **Direction of the changes.** Twenty of the 31 changes turned an INSUFFICIENT_EVIDENCE verdict into a decisive
  one. Half of these were claims the reference judges undecidable from the filings.
- **Effect on errors.** Over-abstention errors fell from 16 to 9, but overconfident decisive answers rose from 23
  to 32, and SUPPORTED/CONTRADICTED reversals rose from 8 to 13.
- **Investigation and citations.** The investigation retrieved relevant counter-evidence. Of 435 challenges,
  16% were judged supported, and every supported challenge cited a provenance-valid passage. No evidence filed
  after a claim's cutoff was used by any approach.
- **Cost.** A3 cost 4.1× more per claim ($0.082 vs $0.020) and took 3.5× longer (34.5 s vs 9.9 s).
- **Sensitivity.** The A2 → A3 difference stayed non-significant under the adjudicated scoring (−4.0 pts,
  p = 0.29) and the lenient upper bound (+1.3 pts, p = 0.77). The A1 → A2 gain was unchanged under all three.

**Discussion.**

- **The investigation retrieved evidence but drew conclusions from it that the evidence did not license.** In the
  15 claims A3 got wrong after A2 got them right, the counter-evidence was genuine or partly genuine in 14. But
  the final citations entailed the new verdict in none of them (manual review, not yet researcher-verified).
- **Recurring failure patterns.** Decisive answers to claims whose key term has no criterion, management intent
  taken as proof, accounting-term misreadings, and period mismatches.
- **What the stage did in practice.** It acted less as a falsification step than as a second retrieval round
  that makes the system more decisive, particularly more willing to say SUPPORTED. That is penalised when the
  reference reserves INSUFFICIENT_EVIDENCE for ambiguous evaluative claims.
- **What helped.** Gains came from a deterministic check (A2's XBRL verification), not from more LLM reasoning.
- **Implications.** Further improvement is more likely from deterministic checks on period alignment, derived
  figures and citation fidelity, and from an explicit decidability criterion, than from additional
  investigation rounds.
- **Caveats.** These explanations are hypotheses. The study has limited power (23 discordant pairs), a single
  model and prompt version, and an LLM-annotated reference with researcher review.

## 7. Artifacts

| What | Where |
|---|---|
| Freeze record | `results/freeze/claimverif-main-v1-20261110T104207Z.json` (`scripts/freeze_experiment.py --verify`) |
| Notebook | `notebooks/08_error_analysis.ipynb`; executed: `results/executed_notebooks/08_error_analysis.ipynb` |
| Figures | `results/figures/08_{paired_quadrants,change_direction,error_types,confusion,discordant_mechanisms,accuracy_vs_cost}_<run>.png` |
| Tables | `results/metrics/<run>__ea_*.csv`: paired claims, second look, error types, counter-evidence audit, discordant review, citation audit (+ summary), efficiency, case studies |
| Manual review (to confirm) | `datasets/error_analysis/discordant_case_review__<run>.csv` |
| Code | `engine/error_analysis.py`, `engine/freeze.py`, `engine/plots.py` (§ error analysis); tests `tests/test_error_analysis.py` |
