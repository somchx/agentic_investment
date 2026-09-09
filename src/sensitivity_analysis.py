"""Sensitivity analysis for the Weakened/Broken buffer in reason_engine.py's
_classify(): the 50%-of-threshold boundary is an operational definition
this project set for the prototype, not a finance principle -- this script
checks how much the resulting status distribution actually moves if that
buffer were 25% or 75% instead, using the gold set's confirmed-correct
values (no LLM calls, free).

If the distribution barely moves, that's evidence the rule is robust to
the exact buffer chosen. If it moves a lot, that's a real finding about
how sensitive this project's classification is to a number nobody could
derive from finance theory.

Usage:
    python3 build_gold_set.py    # first, if not already run
    python3 sensitivity_analysis.py
"""

import json
from collections import Counter, defaultdict
from datetime import date, timedelta

from tools import REASON_DEFS

GOLD_SET_PATH = "../data/gold_set.json"

THRESHOLDS = {
    "revenue_growth": (">", 0.10),
    "operating_margin": (">=", 0.20),
    "debt_growth": ("<", 0.15),
}

BUFFERS_TO_TEST = [0.25, 0.50, 0.75]


def classify(comparison: str, computed: float, threshold: float, buffer: float) -> str:
    holds = {
        ">": computed > threshold,
        ">=": computed >= threshold,
        "<": computed < threshold,
        "<=": computed <= threshold,
    }[comparison]
    if holds:
        return "Supported"
    if comparison in (">", ">="):
        return "Weakened" if computed >= threshold * (1 - buffer) else "Broken"
    return "Weakened" if computed <= threshold * (1 + buffer) else "Broken"


def _nearest_prior_year(period_ends: list[str], current: str) -> str | None:
    cur = date.fromisoformat(current)
    target = cur - timedelta(days=365)
    window = timedelta(days=35)
    candidates = [p for p in period_ends if p != current and abs(date.fromisoformat(p) - target) <= window]
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs(date.fromisoformat(p) - target))


def run() -> None:
    with open(GOLD_SET_PATH) as f:
        gold = json.load(f)
    trustworthy = [e for e in gold if e["sources_agree"]]

    value_by = defaultdict(dict)
    for e in trustworthy:
        key = (e["ticker"], e["metric"])
        existing = value_by[key].get(e["period_end"])
        if existing is None or e["xbrl_filed"] < existing[1]:
            value_by[key][e["period_end"]] = (e["xbrl_10q_value"], e["xbrl_filed"])

    # Compute the growth/margin ratio once per (ticker, reason_key, period_end);
    # classify it at every buffer level so the comparison is apples-to-apples.
    computed_values = []  # (ticker, reason_key, period_end, computed)
    for reason_key, reason in REASON_DEFS.items():
        for ticker in {e["ticker"] for e in trustworthy}:
            if reason.kind == "margin_level":
                num_vals = value_by.get((ticker, reason.metric), {})
                den_vals = value_by.get((ticker, reason.denominator_metric), {})
                for period_end, (num_val, _) in num_vals.items():
                    if period_end not in den_vals or den_vals[period_end][0] == 0:
                        continue
                    computed_values.append((ticker, reason_key, period_end, num_val / den_vals[period_end][0]))
            else:
                vals = value_by.get((ticker, reason.metric), {})
                period_ends = list(vals.keys())
                for period_end, (cur_val, _) in vals.items():
                    prior_end = _nearest_prior_year(period_ends, period_end)
                    if prior_end is None or vals[prior_end][0] == 0:
                        continue
                    prior_val = vals[prior_end][0]
                    computed_values.append((ticker, reason_key, period_end, (cur_val - prior_val) / abs(prior_val)))

    print(f"{len(computed_values)} scorable (ticker, reason, period) cases from the gold set\n")

    results = {}  # buffer -> {(ticker, reason_key, period_end): status}
    for buffer in BUFFERS_TO_TEST:
        statuses = {}
        for ticker, reason_key, period_end, computed in computed_values:
            comparison, threshold = THRESHOLDS[reason_key]
            statuses[(ticker, reason_key, period_end)] = classify(comparison, computed, threshold, buffer)
        results[buffer] = statuses
        dist = Counter(statuses.values())
        print(f"Buffer {buffer:.0%}: {dict(dist)}")

    baseline = 0.50
    print(f"\nHow many cases change status vs the {baseline:.0%} baseline used in the live pipeline:")
    for buffer in BUFFERS_TO_TEST:
        if buffer == baseline:
            continue
        changed = [
            key for key in results[baseline]
            if results[baseline][key] != results[buffer][key]
        ]
        pct = len(changed) / len(computed_values)
        print(f"  {buffer:.0%} vs {baseline:.0%}: {len(changed)}/{len(computed_values)} cases change ({pct:.1%})")
        for ticker, reason_key, period_end in changed[:10]:
            print(f"    {ticker} [{reason_key}] {period_end}: {results[baseline][(ticker, reason_key, period_end)]} -> {results[buffer][(ticker, reason_key, period_end)]}")
        if len(changed) > 10:
            print(f"    ... and {len(changed) - 10} more")


if __name__ == "__main__":
    run()
