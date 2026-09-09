"""Personalization experiment (PROPOSAL.md Contribution 4). For each of a
set of (ticker, reason_key) cases with an already-computed evidence status
(reused from full_experiment_results.json's agent_status -- no new evidence
retrieval, no new evidence-layer LLM calls), apply 4 synthetic investor
profiles and compare:

1. Evidence integrity: does the LLM-derived tier ever echo back a DIFFERENT
   evidence status than it was given? Should be 0/N -- any failure here
   means personalization is leaking into the fact layer, which is the one
   outcome this design is not allowed to produce.
2. Priority divergence: does the same evidence produce different tiers for
   different profiles? (it should, for non-Supported cases -- that's the
   whole point of Contribution 4).
3. Agreement with the free rule-based baseline, as a sanity check that the
   LLM's tier decisions are in the right ballpark rather than arbitrary.

Hard-budgeted: stops before any call that would push projected total cost
over BUDGET_CAP_USD. Real, paid run.

Usage:
    python3 run_personalization_experiment.py
"""

import json

from investor_profile import ALL_PROFILES
from personalization import llm_tier, rule_based_tier
from tools import REASON_DEFS

OUT_PATH = "../data/personalization_experiment_results.json"
SOURCE_PATH = "../data/full_experiment_results.json"
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0
BUDGET_CAP_USD = 1.00
EST_COST_PER_CALL_USD = 0.015  # conservative pre-call estimate for the budget guard


def select_cases(rows: list[dict]) -> list[dict]:
    """All non-Supported cases (where personalization actually has something
    to differentiate) plus 2 Supported controls (should stay "Monitor" for
    every profile -- confirms rule_based_tier's short-circuit and gives the
    LLM a case where the "right" answer is to NOT escalate regardless of
    profile).
    """
    non_supported = [r for r in rows if r["agent_status"] != "Supported"]
    controls = [r for r in rows if r["agent_status"] == "Supported"][:2]
    return non_supported + controls


def run() -> None:
    with open(SOURCE_PATH) as f:
        source = json.load(f)
    cases = select_cases(source["rows"])
    print(f"{len(cases)} cases x {len(ALL_PROFILES)} profiles = {len(cases) * len(ALL_PROFILES)} planned LLM calls")

    total_input_tokens, total_output_tokens = 0, 0
    results = []
    stopped_early = False

    for case in cases:
        reason = REASON_DEFS[case["reason_key"]]
        status = case["agent_status"]
        for profile in ALL_PROFILES:
            projected = (
                total_input_tokens / 1e6 * COST_PER_M_INPUT
                + total_output_tokens / 1e6 * COST_PER_M_OUTPUT
                + EST_COST_PER_CALL_USD
            )
            if projected > BUDGET_CAP_USD:
                print(f"\nBudget guard: next call would push projected cost past ${BUDGET_CAP_USD:.2f}. Stopping early.")
                stopped_early = True
                break

            rule_result = rule_based_tier(status, profile)
            llm_result = llm_tier(case["ticker"], reason.description, status, profile)
            total_input_tokens += llm_result["usage"]["input_tokens"]
            total_output_tokens += llm_result["usage"]["output_tokens"]

            integrity_ok = llm_result["echoed_evidence_status"] == status
            row = {
                "ticker": case["ticker"],
                "reason_key": case["reason_key"],
                "evidence_status": status,
                "profile": profile.name,
                "rule_based_tier": rule_result,
                "llm_tier": llm_result["tier"],
                "llm_rationale": llm_result["rationale"],
                "integrity_ok": integrity_ok,
                "agree_with_rule": rule_result == llm_result["tier"],
            }
            results.append(row)
            flag = "" if integrity_ok else "  *** INTEGRITY FAILURE ***"
            print(f"  {case['ticker']:<6}{case['reason_key']:<18}{status:<18}{profile.name:<45}"
                  f"rule={rule_result:<12}llm={llm_result['tier']:<12}{flag}")
        if stopped_early:
            break

    cost = total_input_tokens / 1e6 * COST_PER_M_INPUT + total_output_tokens / 1e6 * COST_PER_M_OUTPUT

    with open(OUT_PATH, "w") as f:
        json.dump({
            "results": results,
            "stopped_early": stopped_early,
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            "cost_usd": cost,
        }, f, indent=2)

    n = len(results)
    integrity_failures = [r for r in results if not r["integrity_ok"]]
    agree = sum(r["agree_with_rule"] for r in results)

    print("\n" + "=" * 100)
    print(f"Total calls: {n}{' (stopped early by budget guard)' if stopped_early else ''}")
    print(f"Evidence integrity: {n - len(integrity_failures)}/{n} passed"
          f"{' -- ' + str(len(integrity_failures)) + ' FAILURES, see results file' if integrity_failures else ' (100%)'}")
    print(f"Agreement with rule-based baseline: {agree}/{n} ({agree/n:.1%})" if n else "no results")

    # Divergence: for each (ticker, reason_key), how many distinct tiers did
    # the 4 profiles produce on the same evidence?
    by_case = {}
    for r in results:
        key = (r["ticker"], r["reason_key"])
        by_case.setdefault(key, set()).add(r["llm_tier"])
    divergent = sum(1 for tiers in by_case.values() if len(tiers) > 1)
    print(f"Cases where profile changed the tier: {divergent}/{len(by_case)}")

    print(f"\nTotal cost: ${cost:.3f} ({n} calls, {total_input_tokens} input + {total_output_tokens} output tokens)")


if __name__ == "__main__":
    run()
