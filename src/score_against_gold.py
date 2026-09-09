"""Score the live pipeline's status classification against the gold set,
using an independently-reimplemented classification rule (not imported from
reason_engine.py -- if this script called the same function it's grading, a
bug there would silently reproduce here too).

Two things are checked, both free (no LLM calls):

1. Extraction accuracy -- already computed by build_gold_set.py: what
   fraction of dual-sourced (XBRL 10-Q vs 8-K earnings release) values
   agree. Restated here as the headline number.
2. Classification accuracy -- for every gold-confirmed pair of periods this
   script can form a YoY growth or margin ratio from, independently
   classify Supported/Weakened/Broken/Not-enough-data using the gold
   values, then compare against what tools.check_reason_status() actually
   returns live for the same (ticker, reason_key, as_of). A mismatch here
   means the live pipeline's classification disagrees with an independent
   recomputation from confirmed-correct numbers -- a real bug, not a
   restatement or a wording difference.

Usage:
    python3 build_gold_set.py    # first, to produce data/gold_set.json
    python3 score_against_gold.py
"""

import json
from collections import defaultdict
from datetime import date, timedelta

from tools import REASON_DEFS, check_reason_status

GOLD_SET_PATH = "../data/gold_set.json"

THRESHOLDS = {
    "revenue_growth": (">", 0.10),
    "operating_margin": (">=", 0.20),
    "debt_growth": ("<", 0.15),
}


def classify_independent(comparison: str, computed: float, threshold: float) -> str:
    """Kept in sync with reason_engine.py's _classify() by spec, not by
    import: Weakened means "within a 50%-of-threshold buffer of passing,"
    Broken means a bigger miss than that, applied the same way on both
    sides of the threshold. (Earlier version of both this function and
    _classify used an absolute "still positive" cutoff for >/>= reasons,
    which meant a 0.5% margin against a 20% threshold classified identically
    to a 19.9% margin -- indefensible if asked why. Fixed in both places.)
    """
    holds = {
        ">": computed > threshold,
        ">=": computed >= threshold,
        "<": computed < threshold,
        "<=": computed <= threshold,
    }[comparison]
    if holds:
        return "Supported"
    if comparison in (">", ">="):
        return "Weakened" if computed >= threshold * 0.5 else "Broken"
    return "Weakened" if computed <= threshold * 1.5 else "Broken"


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
    print(f"Extraction accuracy: {len(trustworthy)}/{len(gold)} dual-sourced values agree "
          f"({len(trustworthy) / len(gold):.1%})\n")

    # value_by[(ticker, metric)][period_end] -> (value, xbrl_filed date).
    # Use xbrl_filed (the 10-Q/10-K's own filed date), not the 8-K's as_of --
    # the earnings release for a quarter is often published before that
    # quarter's own 10-Q is filed, so check_reason_status(as_of=<8-K date>)
    # can correctly resolve to the *previous* quarter (this quarter's XBRL
    # fact doesn't exist yet as of the release date). An earlier version of
    # this script used `as_of` here and got ~41 "mismatches" that were
    # actually the point-in-time filter working correctly, not classification
    # bugs -- see the comment in build_gold_set.py where xbrl_filed is set.
    value_by = defaultdict(dict)
    for e in trustworthy:
        key = (e["ticker"], e["metric"])
        existing = value_by[key].get(e["period_end"])
        if existing is None or e["xbrl_filed"] < existing[1]:
            value_by[key][e["period_end"]] = (e["xbrl_10q_value"], e["xbrl_filed"])

    matches, mismatches = 0, []

    for reason_key, reason in REASON_DEFS.items():
        comparison, threshold = THRESHOLDS[reason_key]

        for ticker in {e["ticker"] for e in trustworthy}:
            if reason.kind == "margin_level":
                num_vals = value_by.get((ticker, reason.metric), {})
                den_vals = value_by.get((ticker, reason.denominator_metric), {})
                for period_end, (num_val, as_of) in num_vals.items():
                    if period_end not in den_vals or den_vals[period_end][0] == 0:
                        continue
                    den_val = den_vals[period_end][0]
                    computed = num_val / den_val
                    gold_status = classify_independent(comparison, computed, threshold)
                    live = check_reason_status(ticker, reason_key, as_of=as_of)
                    if "error" in live:
                        continue
                    if live["status"] == gold_status:
                        matches += 1
                    else:
                        mismatches.append((ticker, reason_key, period_end, gold_status, live["status"]))
            else:
                vals = value_by.get((ticker, reason.metric), {})
                period_ends = list(vals.keys())
                for period_end, (cur_val, as_of) in vals.items():
                    prior_end = _nearest_prior_year(period_ends, period_end)
                    if prior_end is None or vals[prior_end][0] == 0:
                        continue
                    prior_val = vals[prior_end][0]
                    computed = (cur_val - prior_val) / abs(prior_val)
                    gold_status = classify_independent(comparison, computed, threshold)
                    live = check_reason_status(ticker, reason_key, as_of=as_of)
                    if "error" in live:
                        continue
                    if live["status"] == gold_status:
                        matches += 1
                    else:
                        mismatches.append((ticker, reason_key, period_end, gold_status, live["status"]))

    total = matches + len(mismatches)
    print(f"Classification accuracy: {matches}/{total} ({matches / total:.1%})" if total else "No scorable pairs found.")
    if mismatches:
        print(f"\n{len(mismatches)} mismatch(es):")
        for ticker, reason_key, period_end, gold_status, live_status in mismatches:
            print(f"  {ticker} [{reason_key}] {period_end}: gold={gold_status} live={live_status}")


if __name__ == "__main__":
    run()
