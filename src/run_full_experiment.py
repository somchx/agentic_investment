"""Full experiment: LLM-only (baseline1) vs single-shot RAG (baseline2) vs
rule-based (free) vs this project's tool-using agent, scored against an
independently-derived reference status -- not against check_reason_status's
own output, which is what every earlier comparison in this session did.

Reference status per (ticker, reason_key) is built the same way
score_against_gold.py verifies the live pipeline (classify_independent,
not reason_engine.py's own function -- an independent reimplementation so
a bug there wouldn't silently reproduce here), but sourced from
data/primary_source_verification_set.json rather than data/gold_set.json.
A first attempt used gold_set.json and only found a usable reference for
20/45 (ticker, reason_key) pairs -- and some of those (e.g. TSLA, whose
most recent gold-confirmed quarter was 2019) were badly stale, nowhere
near what baseline1/baseline2/agent actually evaluate when they check
"the latest quarter." primary_source_verification_set.json's 352 entries
(spanning up to 8 historical quarters per pair, built for the review
packet) give far denser, far more current coverage for the same
classify_independent logic to run against.

Real, budgeted run (~$1.5-2 estimated) -- see README.md for the cost
breakdown agreed before running.

Usage:
    python3 run_full_experiment.py
"""

import json
import time
from collections import defaultdict

from agent import run_rule_based, run_with_llm
from baseline1 import run_baseline1
from baseline2 import run_baseline2
from score_against_gold import THRESHOLDS, _nearest_prior_year, classify_independent
from sec_client import KNOWN_CIKS
from tools import REASON_DEFS

PRIMARY_SOURCE_PATH = "../data/primary_source_verification_set.json"
OUT_PATH = "../data/full_experiment_results.json"
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0


def build_reference() -> dict:
    """(ticker, reason_key) -> {"status", "computed", "period_end"} for the
    most recent quarter each pair has a primary-filing-confirmed value for.
    """
    with open(PRIMARY_SOURCE_PATH) as f:
        primary = json.load(f)
    trustworthy = [
        e for e in primary
        if e.get("category") == "Primary-filing-verified" and e.get("agrees_with_xbrl") and e.get("period_end")
    ]

    value_by = defaultdict(dict)
    for e in trustworthy:
        key = (e["ticker"], e["metric"])
        value_by[key][e["period_end"]] = e["xbrl_pipeline_value"]

    reference = {}
    for reason_key, reason in REASON_DEFS.items():
        comparison, threshold = THRESHOLDS[reason_key]
        tickers = {e["ticker"] for e in trustworthy}
        for ticker in tickers:
            if reason.kind == "margin_level":
                num_vals = value_by.get((ticker, reason.metric), {})
                den_vals = value_by.get((ticker, reason.denominator_metric), {})
                common = [p for p in num_vals if p in den_vals and den_vals[p] != 0]
                if not common:
                    continue
                period_end = max(common)
                computed = num_vals[period_end] / den_vals[period_end]
            else:
                vals = value_by.get((ticker, reason.metric), {})
                if not vals:
                    continue
                period_end = max(vals.keys())
                prior_end = _nearest_prior_year(list(vals.keys()), period_end)
                if prior_end is None or vals[prior_end] == 0:
                    continue
                computed = (vals[period_end] - vals[prior_end]) / abs(vals[prior_end])

            status = classify_independent(comparison, computed, threshold)
            reference[(ticker, reason_key)] = {
                "status": status, "computed": computed, "period_end": period_end,
            }
    return reference


def cost(usage: dict) -> float:
    return usage.get("input_tokens", 0) / 1e6 * COST_PER_M_INPUT + usage.get("output_tokens", 0) / 1e6 * COST_PER_M_OUTPUT


def run() -> None:
    reference = build_reference()
    print(f"Reference status available for {len(reference)}/45 (ticker, reason_key) pairs\n")

    tickers = sorted(KNOWN_CIKS.keys())
    rows = []
    totals = {name: {"input": 0, "output": 0, "seconds": 0.0, "calls": 0} for name in
              ("baseline1", "baseline2", "rule_based", "agent")}

    for ticker in tickers:
        print(f"--- {ticker} ---")

        t0 = time.time()
        agent_result = run_with_llm(ticker)
        agent_seconds = time.time() - t0
        totals["agent"]["input"] += agent_result["usage"]["input_tokens"]
        totals["agent"]["output"] += agent_result["usage"]["output_tokens"]
        totals["agent"]["seconds"] += agent_seconds
        totals["agent"]["calls"] += 1
        agent_by_key = {r["reason_key"]: r for r in agent_result["reasons"]}

        t0 = time.time()
        rule_result = run_rule_based(ticker)
        rule_seconds = time.time() - t0
        totals["rule_based"]["seconds"] += rule_seconds
        totals["rule_based"]["calls"] += 1
        rule_by_key = {r["reason_key"]: r for r in rule_result["reasons"] if "error" not in r}

        for reason_key in REASON_DEFS:
            ref = reference.get((ticker, reason_key))

            t0 = time.time()
            b1 = run_baseline1(ticker, reason_key)
            b1_seconds = time.time() - t0
            totals["baseline1"]["input"] += b1["usage"]["input_tokens"]
            totals["baseline1"]["output"] += b1["usage"]["output_tokens"]
            totals["baseline1"]["seconds"] += b1_seconds
            totals["baseline1"]["calls"] += 1

            t0 = time.time()
            b2 = run_baseline2(ticker, reason_key)
            b2_seconds = time.time() - t0
            totals["baseline2"]["input"] += b2["usage"]["input_tokens"]
            totals["baseline2"]["output"] += b2["usage"]["output_tokens"]
            totals["baseline2"]["seconds"] += b2_seconds
            totals["baseline2"]["calls"] += 1

            rb = rule_by_key.get(reason_key, {})
            ag = agent_by_key.get(reason_key, {})

            row = {
                "ticker": ticker,
                "reason_key": reason_key,
                "reference_status": ref["status"] if ref else None,
                "baseline1_status": b1.get("status"),
                "baseline1_review": b1.get("human_review_recommended"),
                "baseline2_status": b2.get("status"),
                "baseline2_review": b2.get("human_review_recommended"),
                "rule_based_status": rb.get("status"),
                "rule_based_review": rb.get("human_review_recommended"),
                "agent_status": ag.get("status"),
                "agent_review": ag.get("human_review_recommended"),
            }
            rows.append(row)
            print(f"  [{reason_key}] ref={row['reference_status']} "
                  f"b1={row['baseline1_status']} b2={row['baseline2_status']} "
                  f"rule={row['rule_based_status']} agent={row['agent_status']}")

    with open(OUT_PATH, "w") as f:
        json.dump({"rows": rows, "totals": totals}, f, indent=2)

    print("\n" + "=" * 100)
    scorable = [r for r in rows if r["reference_status"]]
    print(f"Scorable rows (have a reference status): {len(scorable)}/{len(rows)}\n")

    for name, key in (("Baseline 1", "baseline1_status"), ("Baseline 2", "baseline2_status"),
                       ("Rule-based", "rule_based_status"), ("Agent", "agent_status")):
        correct = sum(1 for r in scorable if r[key] == r["reference_status"])
        print(f"{name} accuracy: {correct}/{len(scorable)} ({correct/len(scorable):.1%})")

    print()
    severe = [r for r in scorable if r["reference_status"] in ("Broken",)]
    print(f"Severe (reference=Broken) cases: {len(severe)}")
    for name, key in (("Baseline 1", "baseline1_review"), ("Baseline 2", "baseline2_review"),
                       ("Rule-based", "rule_based_review"), ("Agent", "agent_review")):
        escalated = sum(1 for r in severe if r[key] is True)
        print(f"  {name} escalation rate on severe cases: {escalated}/{len(severe)}"
              f" ({escalated/len(severe):.1%})" if severe else f"  {name}: no severe cases")

    print("\nCost and latency:")
    for name in ("baseline1", "baseline2", "rule_based", "agent"):
        t = totals[name]
        c = cost({"input_tokens": t["input"], "output_tokens": t["output"]})
        avg_latency = t["seconds"] / t["calls"] if t["calls"] else 0
        print(f"  {name}: ${c:.3f}, {t['calls']} calls, avg {avg_latency:.1f}s/call, total {t['seconds']:.0f}s")


if __name__ == "__main__":
    run()
