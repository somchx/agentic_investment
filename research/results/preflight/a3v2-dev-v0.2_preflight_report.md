# A3 v2 on dev-v0.2: pre-flight audit report

- **Date:** 2026-11-17
- **No paid calls were made.** No commit, and no changes to Gold, frozen v1 or human annotations.
- **Classification:** PASS = verified and acceptable. WARNING = acceptable but must be disclosed. BLOCKER = must be fixed
  before paid execution.

## 1. Executive Summary

**Decision: READY for the 12-claim smoke test and then the remaining 60.** Paid execution still waits for your
explicit approval.

**Answers to the questions**

| Question | Answer |
|---|---|
| Is the full 72-claim experiment technically ready? | Yes. The runner supports A2, A3v2_R and A3v2_RG on dev-v0.2. The mock run completed 216/216 predictions with 0 errors, and the tests pass (218 tests). |
| Is the expected spend below $15? | Yes. Typical ≈ $9.0; pessimistic (p95 inputs, maximum outputs) ≈ $12.6. A ledger enforces an aggregate hard cap of $15. |
| Can R and RG reuse the same paid LLM outputs? | Yes. Their request keys are identical for all 4 calls. RG runs cache-only, so it cannot make a paid call. |
| Can the experiment resume without duplicate charges? | Yes. Tested: interruption followed by resume gives 12 unique requests, no duplicates, and the ledger keeps accumulating. |
| Is numerical claim handling controlled enough? | Partly. A2's numeric verification is deterministic, and the guard does not let narrative overturn A2's numeric conclusion. But the period check does not look at the duration of the figure, and 21/72 claims have a period the system cannot resolve. These are WARNINGs (§7). |
| Are model inputs free of reference labels? | Yes. Verified (§2). |
| Are frozen datasets and v1 results unchanged? | Yes. Freeze verify: changed [] and removed []. All hashes are unchanged. |
| What risks remain before interpreting accuracy? | See §7: provisional labels, the period-check limits, and the guard's bias toward A2. |

## 2. Phase 1–2 Verified Baseline (re-checked after integration)

| # | Item | Result |
|---|---|---|
| P1 | 72 unique claim ids; complete fields; ambiguous 30 / interpretive 22 / numerical 20 | PASS |
| P2 | Cutoffs: 216 retrieval sets have no filing after the cutoff; every filing is cached | PASS |
| P3 | Model input is limited to `claim_id, company, claim, as_of_date, reporting_period, allowed_sources`. The inference code reads no annotation, adjudication, design intent or workbook. | PASS (`test_leakage_config` passes) |
| P4 | Dataset hash `120d60d4…`. Gold, frozen v1 and every annotation version have unchanged hashes. | PASS |
| P5 | Through the real runner: R's initial request = A2's (cache hit); R initial_label = RG initial_label = A2 prediction for every claim | PASS (`test_full_run_rg_is_cache_only_and_costs_are_ledgered`) |
| P6 | Model, temperature, max output tokens, RAG settings and budget are identical across the three approaches (`fairness_problems` = []) | PASS |

## 3. Phase 3 Architecture Findings

### 3.1 Pipeline audit table

**1. A2 baseline: retrieve → initial_verdict → numeric_verification**
- **Input → output:** claim fields → label, citations, numeric_assertions, numeric checks.
- **Model / logic:** BM25 retrieval (deterministic), 1 LLM call, then deterministic XBRL checks.
- **Prompt / config:** `engine/prompts.py` (`claim-prompts-1.0`).
- **Can change the label:** numeric checks override the LLM label (NUMERIC_FALSE / NUMERIC_ALL_TRUE).
- **On failure:** NO_VERDICT → INSUFFICIENT_EVIDENCE.
- **Provenance:** every passage goes into the EvidenceLedger, and citations are checked against it.

**2. analyze_claim**
- **Input → output:** model_verdict → assertions (A0 plus numeric), claim_period, computations.
- **Model / logic:** deterministic. The DefaultAnalyzer makes no LLM call.
- **Prompt / config:** `a3v2/interfaces.py`.
- **Can change the label:** no.
- **On failure:** none.
- **Provenance:** the period comes from a date stated in the claim, or from the FY label matched to a 10-K.

**3. generate_hypotheses → counter_investigation (v1)**
- **Input → output:** verdict → up to 3 hypotheses → counter passages and counter numeric checks.
- **Model / logic:** 1 LLM call + BM25 + deterministic XBRL.
- **Prompt / config:** `engine/prompts.py`.
- **Can change the label:** no. Hypotheses are questions, not facts.
- **On failure:** BUDGET/NO_FINAL → A2's label.
- **Provenance:** counter passages go into the ledger.

**4. evidence_review**
- **Input → output:** claim, period, assertions and every evidence id → findings with relation ENTAILS / CONTRADICTS /
  RELATED_NOT_DECIDING / IRRELEVANT.
- **Model / logic:** deterministic checks, then 1 isolated LLM call (fresh conversation, without A2's label, reasoning or
  hypotheses), then deterministic validation.
- **Prompt / config:** `a3v2/prompts.py` (`a3v2-review-prompts-0.1`), max_output 3000.
- **Can change the label:** no, directly. A deciding relation is downgraded when the quote is not in the evidence, the
  period is wrong, the period is partial, the evidence is a management intent or forward-looking, or the company or
  cutoff is wrong.
- **On failure:** NoStructuredOutput → NO_FINAL_VERDICT → A2's label.
- **Provenance:** the key_quote must match the evidence verbatim (normalised for typographic quotes), or match a figure by
  value.

**5. reconcile_v2**
- **Input → output:** A2 label, hypotheses, counter evidence, counter numeric, assertions, review table → proposed label
  and citations.
- **Model / logic:** 1 LLM call (the v1 conversation plus the review table).
- **Prompt / config:** `RECONCILIATION_INSTRUCTION_V2`.
- **Can change the label:** the LLM proposes a change.
- **On failure:** output truncated at 1500 tokens → NO_FINAL_VERDICT → A2's label.
- **Provenance:** citations are checked again in the guards.

**6. apply_guards (v1)**
- **Input → output:** proposed label → label after the v1 guards.
- **Model / logic:** deterministic.
- **Prompt / config:** `graphs/nodes.py`.
- **Can change the label:** reverts changes without valid citations, and preserves numeric results.
- **On failure:** none.
- **Provenance:** citations must exist in the ledger and the quote must match.

**7. reconciliation_guard (RG only)**
- **Input → output:** A2 label and rule, proposed label, citations, review findings → final label, reason code, trace.
- **Model / logic:** deterministic.
- **Prompt / config:** `a3v2/guard.py` (`a3v2-guard-0.1`).
- **Can change the label:** ACCEPT / REJECT per the rules in §3.2.
- **On failure:** none.
- **Provenance:** invalid citations are removed first. On REJECT, A2's citations are restored.

**8. finalize**
- **Input → output:** final state → prediction and trace.
- **Model / logic:** deterministic.
- **Prompt / config:** `graphs/nodes.py`.
- **Can change the label:** no.
- **Provenance:** stop_reason, all calls and every stage are written to the trace.

**Logging and reproducibility (all stages):** request_key per call, tokens, source (live / cache), stage trace, config
hash, code sha256 including `a3v2/`, prompt hashes, dataset sha and XBRL facts sha.

### 3.2 When R and RG change A2's label

**R.** Changes A2's label when the reconciliation LLM proposes a change and the change passes the v1 guards:
- the citations exist and the quote matches;
- the change does not conflict with A2's decisive numeric result.

**RG.** Applies these rules to the change that comes out of R's path:

| Change | ACCEPT when | REJECT when |
|---|---|---|
| To SUPPORTED | At least one VALID ENTAILS finding whose evidence is still cited, and no VALID CONTRADICTS finding | Otherwise: CONFLICTING_DECIDING_EVIDENCE, DECIDING_EVIDENCE_NOT_CITED, INVALID_DECIDING_EVIDENCE:*, ARGUMENT_FROM_SILENCE, REFUTED_CHALLENGES_ONLY or CONTEXT_ONLY |
| To CONTRADICTED | At least one VALID CONTRADICTS finding whose evidence is still cited | Same reasons as above |
| Decisive → INSUFFICIENT | No valid evidence still decides A2's label, or there is a definition mismatch | INITIAL_VERDICT_STILL_DECIDED |
| Away from A2's NUMERIC_FALSE / NUMERIC_ALL_TRUE | A counter numeric check reaches the opposite result, or there is a definition mismatch | A2_NUMERIC_CONCLUSION_PRESERVED |

### 3.3 Findings

| ID | Finding | Class |
|---|---|---|
| F1 | The reviewer is isolated from A2's reasoning, hypotheses and label (tested) | PASS |
| F2 | Evidence relevance: IRRELEVANT or RELATED_NOT_DECIDING cannot carry a change in RG (`test_irrelevant_evidence_cannot_carry_a_change`). In R it can: R follows the LLM. | PASS (RG) / WARNING (R, by design) |
| F3 | A contradiction whose quote is not in the evidence is downgraded and rejected (`test_false_contradiction_with_invented_quote_is_downgraded`) | PASS |
| F4 | A management intent or forward-looking statement cannot decide (`test_management_intention_is_not_a_contradiction`) | PASS |
| F5 | A genuine same-period contradiction is accepted (`test_genuine_same_period_contradiction_is_accepted`) | PASS |
| F6 | Conflicting valid evidence blocks a move to SUPPORTED (`test_conflicting_valid_evidence_blocks_a_move_to_supported`) | PASS |
| F7 | Narrative cannot overturn A2's decisive numeric result (existing test `test_a2_numeric_conclusion_is_preserved`) | PASS |
| F8 | The guard uses only inference-time information: the decide() inputs contain no reference label | PASS |
| F9 | Hypotheses are not treated as facts. Every change must rest on cited evidence from the ledger. | PASS |
| F10 | **Period checks compare end dates only.** A nine-month figure ending on the quarter's end date counts as MATCH (`test_period_check_ignores_duration_known_limitation`). PERIOD_TRAP claims (ADBE-11, INTC-11, PG-10, CAT-12) therefore depend on the LLM. | WARNING |
| F11 | **Unresolved periods.** 21/72 claims (29%) have a period the checks cannot resolve: quarter claims with no date stated in the claim text. For these claims the period check is off (status UNKNOWN). Includes INTC-11 and CAT-12. | WARNING |
| F12 | Decidability is `NOT_ASSESSED` (placeholder). The DefaultAnalyzer requests no computation, so the FCF derivation does not run in the real experiment (affects ADBE-12). | WARNING |
| F13 | The ENTAILS / CONTRADICTS relation is an LLM judgement. The deterministic checks verify provenance and period, not logical entailment. An LLM-set `definition_mismatch` flag can unlock a numeric override and a move to INSUFFICIENT. | WARNING |
| F14 | The guard defaults to keeping A2's label when in doubt. If A2 is wrong and the correction cites no valid evidence, RG returns to A2's wrong label. | WARNING |
| F15 | The reconciliation output cap is 1500 tokens. v1 hit the cap on 5/150 claims, which gave NO_FINAL_VERDICT and A2's label. v2 sends a longer packet, so this may happen more often. Not changed (needs approval). | WARNING |
| F16 | Every failure after the initial stage falls back to A2's label, with stop_reason recorded (`test_reviewer_failure_falls_back_to_a2_label`). Failures must be reported separately, not counted as "no change". | WARNING |
| F17 | Empty retrieval does not create a decisive change. The v1 guards block it before RG. | PASS |
| F18 | Missing XBRL facts give UNAVAILABLE, not a number (`test_missing_xbrl_facts_give_unavailable_not_a_number`) | PASS |

## 4. Phase 4 Integration Changes

**Code**

| File | Change |
|---|---|
| `a3v2/config.py` | `load_v2_config` accepts v1 baselines (A2, built exactly as engine.config builds them) and `replay_of`. A replay arm must be identical to its source arm except for the guard, and must run after it. Returns `common`, `source_path` and the fairness check. |
| `engine/cost_ledger.py` (new) | Shared append-only JSONL ledger with flock. Reservation before each call, settle after it, fail for failed calls, reconcile from the cache. The cap is fixed when the ledger is opened. |
| `engine/llm.py` | BudgetGuard takes a ledger, and CachedLLM passes the request_key. The settle line is written after the cache write. A failed call keeps its reservation. The heuristic mock gains `submit_evidence_review` (MOCK_VERSION 1.1). |
| `engine/runner.py` | Dispatches `contradiction_aware_v2`. A replay arm uses an offline (cache-only) LLM. `plan_run` counts each request once for v2 configs only; v1 configs keep their original count. The manifest gains the ledger, replays, a3v2 prompt hashes and the sha256 of `a3v2/` code. The status gains the ledger state and the replay LLM stats. |
| `scripts/run_experiment.py` | Loads v2 configs; adds `--claims-file`, `--categories`, `--ledger`, `--ledger-cap` and `--ledger-status`. A live v2 run requires `--ledger`. `--plan` never creates or writes a ledger. |

**Configuration and batches (new)**

| File | Content |
|---|---|
| `configs/a3v2_dev_v0_2.json` | A2_rag_numeric, A3v2_R, A3v2_RG (`replay_of` A3v2_R). The model and parameters are the same as `a3v2_development.json`. |
| `configs/batches/dev_v0_2_smoke12.txt` | 12 claims drawn with seed 20261117, 4 per category. No label or design intent was used. |
| `configs/batches/dev_v0_2_remaining60.txt` | The other 60 claims |

**Tests and outputs (new)**

| File | Content |
|---|---|
| `tests/test_a3v2_preflight.py` | 20 tests |
| `results/preflight/a3v2-dev-v0.2_reproducibility_manifest.json` | Reproducibility manifest |
| `results/preflight/a3v2-dev-v0.2_preflight_report.md` | This report |

**Not changed:** `experiments/` (A3 v2 is not in the v1 `RUNNERS`), `graphs/`, all prompts (v1 and v2), the guard and
reviewer logic, model / retrieval parameters, Gold, frozen v1 and every annotation.

**Output directories**
- Each batch is one run: `results/runs/a3v2-dev-v0.2-<UTC>/`.
- Traces are separated per approach: `traces/A2_rag_numeric/`, `traces/A3v2_R/`, `traces/A3v2_RG/`.
- `predictions.jsonl` holds every approach with an `approach` column. A run directory is not split per approach
  (WARNING W12).

## 5. Offline and Mock Test Results (executed)

- **Full suite: 218 passed** (198 before + 20 in `test_a3v2_preflight.py`).
- **CLI mock run, 72 claims × 3 arms:** 216 predictions, 0 errors, 0 cache misses, identical claim ids across arms,
  state complete with SHA256SUMS. Output in the scratchpad, not in `results/runs`.

| Scenario | Test | Result |
|---|---|---|
| Normal execution + RG zero paid calls + cost accounting + metadata | `test_full_run_rg_is_cache_only_and_costs_are_ledgered` | PASS: 12 requests to the API, RG live 0 / cache 12, ledger settled = 12 × cost(1000, 200) |
| RG with no cache cannot pay | `test_replay_arm_never_pays_even_without_cache` | PASS: 0 requests, incomplete |
| Plan counts each request once | `test_plan_counts_each_paid_request_once` | PASS |
| Interrupt + resume without duplicates + ledger not reset | `test_interrupt_and_resume_do_not_pay_twice_or_reset_the_ledger` | PASS: 5 + 7 = 12 with no overlapping keys; ledger 12; cap cannot be changed |
| Aggregate cap stops the run | `test_ledger_stops_the_run_before_the_aggregate_cap` | PASS |
| Cross-process concurrency + in-flight + failed + reconcile | `test_ledger_is_safe_across_processes_and_counts_calls_in_flight` | PASS: 4 processes × 6 reservations on a $10 cap gives exactly 10 |
| API failure + retry | `test_transient_api_errors_are_retried_and_reserved_conservatively` | PASS: 529×2 then success; 2 failed calls stay reserved |
| Fatal billing error | `test_fatal_billing_error_stops_without_recording_predictions` | PASS |
| Cache invalidation + resume with a changed config | `test_changed_prompt_or_config_is_a_cache_miss_and_resume_is_refused` | PASS |
| Irrelevant evidence / false contradiction / intent / genuine contradiction / conflicting | 5 tests | PASS |
| Empty retrieval / reviewer failure / missing XBRL / period duration (limitation) | 4 tests | PASS |
| Manifest records the v2 code and prompt hashes | `test_manifest_records_v2_code_and_prompt_hashes` | PASS |

## 6. Phase 5 Cost Plan

**Sources of the estimates**
- **Per-stage token counts:** actual figures from the frozen v1 traces (150 claims). Mean input / output: initial
  3,927 / 516; plan 4,992 / 335; reconciliation 8,921 / 1,027.
- **Review call:** input ≈ 7,500 tokens. Measured from request sizes in the 72-claim mock run, calibrated at 3.16
  characters per token. Output assumed ≈ 1,200 tokens (cap 3,000).
- **Pricing:** Sonnet 4.5 at $3 / $15 per million tokens.

**Per claim (4 new paid calls)**

| Case | Cost | Basis |
|---|---|---|
| Typical | ≈ $0.125 | Input ≈ 26.3k, output ≈ 3.1k tokens |
| Pessimistic | ≈ $0.175 | p95 inputs and maximum outputs |

**Plans** (`--plan` output from the real runner)

| | Plan A (smoke 12) | Plan B (other 60) | Plan C (all 72) |
|---|---|---|---|
| Claims | 12 | 60 | 72 |
| New paid LLM calls (unique) | 48 | 240 | 288 |
| Calls served from cache | 60 | 300 | 360 |
| Estimated input tokens | ≈ 315k | ≈ 1.58M | ≈ 1.89M |
| Estimated output tokens | ≈ 37k | ≈ 185k | ≈ 222k |
| Estimated cost (typical / pessimistic) | $1.50 / $2.10 | $7.50 / $10.50 | $9.00 / $12.60 |
| Runner "typical" (simple formula) | $1.06 | $5.31 | $6.37 |
| Upper bound (80k input per claim at the output cap) | $7.11 | $35.55 → capped at $15.00 | $42.66 → capped at $15.00 |
| Approval phrase (with a fresh ledger) | "I approve up to 48 paid Claude API calls costing at most $7.11" | "…up to 240 … at most $15.00" | "…up to 288 … at most $15.00" |

**Aggregate cap safeguards**

| Requirement | How it is met |
|---|---|
| The cap counts only new spend in this experiment | The ledger `a3v2-dev-v0.2` starts at $0 and records only paid calls made through it. Cache hits and earlier spend are not counted. |
| Plan B is capped by what Plan A has already spent | B's approval cap = min(upper bound, remaining in the ledger). After A, re-run `--plan` to get the exact phrase. |
| Resume does not reset the budget | The ledger lives in a file; tested. |
| Calls in flight are counted | A reservation is made before each call at the worst case (input = characters / 2, output = the cap) and stays in the total until settled. A failed call stays reserved (conservative). Reservations are taken under flock, so they are safe across processes. |
| The run stops safely | It raises BudgetExceeded before the call, and the status becomes incomplete. |
| Actual usage is recorded | The settle line stores the usage returned by the API. |
| Prompt, config, dataset and code are traceable | See the reproducibility manifest: snapshot sha256 `cc2c1d67…`, git HEAD `caf2cb31` plus the sha256 of every file. |

**Reproducibility manifest** (`results/preflight/a3v2-dev-v0.2_reproducibility_manifest.json`)

| Item | Value |
|---|---|
| Experiment | `a3v2-dev-v0.2` |
| Dataset | dev-v0.2, sha `120d60d4…` |
| Model | claude-sonnet-4-5-20250929, temperature 0 |
| Max output | 1500 (review: 3000) |
| RAG | bm25-1.0, top-k 6, chunk 1200 / 200 |
| v1 prompt hashes | system `7831e3cb…`, instructions `a24d1e47…`, tools `eb1ad0fb…` |
| A3 v2 prompt hashes | review system `2253898b…`, instructions `d57426b7…`, tool `dd8ff8e6…` |
| Response cache | `results/llm_cache`, keyed by sha256 of the full request |
| Ledger | `a3v2-dev-v0.2`, cap $15 |

## 7. Research Validity Risks

| ID | Risk | Class |
|---|---|---|
| W9 | **Reference labels are provisional.** AAPL-05 is not yet adjudicated. The 48 new claims have one labeller (`rev_person2`). The second review is not independent of Codex output, so no κ exists. **Do not report accuracy as final, and do not tune A3 v2 on these labels without recording that.** | WARNING (high) |
| W10 | The claims were AI-drafted by the same model family that is evaluated (Claude) | WARNING |
| W11 | The 24 old dev claims share companies with Gold (AAPL, MSFT, AMZN). Claim-level separation passes. | WARNING |
| F10, F11 | The period checks do not cover duration, and 29% of claims have an unresolved period. Report RG separately on the period-trap claims. | WARNING |
| F14 | RG is biased toward A2. Report R and RG separately and look at the reason codes. | WARNING |
| F15, F16 | NO_FINAL_VERDICT and errors fall back to A2's label. Report them separately from "no change". | WARNING |
| W7 | A claim that ends as ERROR (transient errors not fixed after 3 tries) counts as done when resuming. Re-run it in a new run with `--claims`. | WARNING |
| W12 | One run directory per batch (traces separated per approach) | WARNING (low) |
| W13 | Temperature 0 is not fully deterministic on the API side. The cache makes replays deterministic, but a new run may differ. | WARNING (low) |

## 8. Remaining Blockers and Warnings

**Blockers found and fixed**

| ID | Blocker | Fix |
|---|---|---|
| B1 | The runner did not support A3 v2 or dev-v0.2 | Wired in (§4) |
| B2 | `--max-cost` is per process, so it could not guarantee an aggregate cap across batches and resumes | Shared ledger |
| B3 | RG could make a paid call if the cache was incomplete | Cache-only replay |
| B4 | Run manifests did not record hashes of the `a3v2/` code | Added |
| B5 | `--mode mock` could not run A3 v2 (the mock had no review tool) | Added to the mock |

**Remaining blockers: none.** The warnings are in §3.3 and §7.

## 9. Exact Commands for Paid Execution (run only after approval)

```bash
cd research
PY=/Users/somchx/Desktop/Invesment/research/.venv/bin/python

# Plan A: 12-claim smoke test (opens the ledger at $15)
$PY scripts/run_experiment.py configs/a3v2_dev_v0_2.json --claims-file configs/batches/dev_v0_2_smoke12.txt \
    --ledger a3v2-dev-v0.2 --ledger-cap 15 --plan
$PY scripts/run_experiment.py configs/a3v2_dev_v0_2.json --claims-file configs/batches/dev_v0_2_smoke12.txt \
    --ledger a3v2-dev-v0.2 --ledger-cap 15 --mode live \
    --approve "I approve up to 48 paid Claude API calls costing at most \$7.11"

# check spend after A
$PY scripts/run_experiment.py configs/a3v2_dev_v0_2.json --ledger a3v2-dev-v0.2 --ledger-status

# Plan B: remaining 60 (re-plan: the phrase now uses what is left in the ledger)
$PY scripts/run_experiment.py configs/a3v2_dev_v0_2.json --claims-file configs/batches/dev_v0_2_remaining60.txt \
    --ledger a3v2-dev-v0.2 --plan
$PY scripts/run_experiment.py configs/a3v2_dev_v0_2.json --claims-file configs/batches/dev_v0_2_remaining60.txt \
    --ledger a3v2-dev-v0.2 --mode live --approve "<phrase printed by the plan above>"

# if interrupted: resume the same run (same arguments + --resume <run_id>)
```

**Output:** `results/runs/a3v2-dev-v0.2-<UTC timestamp>/`, one directory per batch.

## 10. Final Readiness Decision

**READY.** Start with Plan A (smoke 12, ≈ $1.5–2.1), then check the following before running Plan B:
- every stop_reason;
- the number of NO_FINAL_VERDICT outcomes;
- the ledger's actual spend.

**Do not start until you approve explicitly.**
