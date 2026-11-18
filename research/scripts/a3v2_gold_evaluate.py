"""Preregistered evaluation of A3 v2.2 on the Gold 150 set (docs/a3v2_2/08_preregistration_gold150.md).

    research/.venv/bin/python research/scripts/a3v2_gold_evaluate.py --run <run id> [--v1-run claimverif-main-v1-20261110T104207Z]
    # tool check on the frozen v1 run only (reproduces the v1 strict accuracies; reads no v2.2 result):
    research/.venv/bin/python research/scripts/a3v2_gold_evaluate.py --check-v1

Reference: datasets/workbooks/Final_Gold_v3_approved.xlsx via engine.reference
(strict scoring = exact label match; the v1 adjudicated / lenient variants exist
only for v1's own answers and are not used for new runs). The run must be
complete, intact, on all 150 gold claims, with no ERROR prediction (a NO_FINAL_VERDICT fallback
keeps its label and is scored, as in v1); otherwise nothing is scored. Preregistered exception: ERRORs that remain
after at most two `--resume --retry-errors` rounds are scored as wrong with --errors-as-wrong (label "ERROR",
listed in the output); no claim is ever dropped. Output: results/gold150/<run id>/evaluation.{json,md}
(never overwritten).
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import file_sha256, load_claims  # noqa: E402
from engine.llm import DEFAULT_CACHE_DIR  # noqa: E402
from engine.metrics import classification_metrics  # noqa: E402
from engine.reference import REFERENCE_PATH, load_reference  # noqa: E402
from engine.runner import RUNS_DIR, verify_run_integrity  # noqa: E402
from engine.stats import bootstrap_ci, bootstrap_diff, mcnemar  # noqa: E402

GOLD = os.path.join(RESEARCH_ROOT, "datasets", "gold_claims.jsonl")
V1_RUN = "claimverif-main-v1-20261110T104207Z"
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "gold150")
CANDIDATE = "A3v2_2e"  # final candidate (pre-flight audit 2026-11-18)
PRIMARY = ("A2_rag_numeric", CANDIDATE)
# P3 vs P2 is the advisor's critical comparison (structured contradiction search vs generic self-critique)
SECONDARY = (("SR_self_reflection", CANDIDATE), ("A3v2_1_1_RG", CANDIDATE), ("V1:A3_contradiction_aware", CANDIDATE))
DESCRIPTIVE = (("A1_conventional_rag", "A2_rag_numeric"), ("A1_conventional_rag", "SR_self_reflection"))  # not in Holm
DECISIVE = ("SUPPORTED", "CONTRADICTED")
SEED, N_BOOT = 20261118, 10000


def wilson(k: int, n: int, z: float = 1.959964) -> dict:
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci": [None, None]}
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "rate": p, "ci": [max(0.0, c - h), min(1.0, c + h)]}


def holm(pvals: dict) -> dict:
    order = sorted(pvals, key=pvals.get)
    out, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * pvals[k]))
        out[k] = running
    return out


def load_run(run_id: str, approaches=None, errors_as_wrong: bool = False, errors: dict | None = None) -> dict:
    d = os.path.join(RUNS_DIR, run_id)
    st, man = json.load(open(os.path.join(d, "status.json"))), json.load(open(os.path.join(d, "manifest.json")))
    problems = [] if st["state"] == "complete" else [f"state {st['state']}"]
    problems += [f"integrity {x}" for x in verify_run_integrity(d)]
    if man["dataset"]["split"] != "gold" or man["dataset"]["sha256"] != file_sha256(GOLD):
        problems.append("not the gold dataset")
    preds = {}
    for line in open(os.path.join(d, "predictions.jsonl")):
        p = json.loads(line)
        if approaches is None or p["approach"] in approaches:
            preds.setdefault(p["approach"], {})[p["claim_id"]] = p
    for a, ps in preds.items():
        bad = [c for c, p in ps.items() if p.get("stop_reason") == "ERROR"]
        if bad and errors_as_wrong and errors is not None:
            errors[a] = sorted(bad)
        if len(ps) != 150 or (bad and not errors_as_wrong):
            problems.append(f"{a}: {len(ps)} predictions, ERROR: {bad[:5]}")
    if problems:
        raise SystemExit(f"{run_id}: cannot score:\n  " + "\n  ".join(problems))
    return {a: {c: "ERROR" if p.get("stop_reason") == "ERROR" else p["predicted_label"] for c, p in ps.items()} for a, ps in preds.items()}


def evaluate(preds: dict, ref: dict, claims: dict) -> dict:
    ids = sorted(ref)
    y = [ref[c] for c in ids]
    cat = {c: claims[c].claim_category for c in ids}
    out = {"n": len(ids), "arms": {}}
    a2 = [preds["A2_rag_numeric"][c] for c in ids] if "A2_rag_numeric" in preds else None
    for arm, p in preds.items():
        pv = [p[c] for c in ids]
        cm = classification_metrics(y, pv)
        right = [x == t for x, t in zip(pv, y)]
        row = {"correct": sum(right), "accuracy": cm["accuracy"], "macro_f1": cm["macro_f1"], "ci": bootstrap_ci(y, pv, n_boot=N_BOOT, seed=SEED),
               "insufficient_recall": wilson(sum(right[i] for i in range(len(ids)) if y[i] == "INSUFFICIENT_EVIDENCE"), y.count("INSUFFICIENT_EVIDENCE")),
               "by_category": {k: wilson(sum(right[i] for i in range(len(ids)) if cat[ids[i]] == k), sum(1 for c in ids if cat[c] == k))
                               for k in ("numerical", "ambiguous", "interpretive")}}
        if a2 is not None and arm != "A2_rag_numeric":
            a2r = [x == t for x, t in zip(a2, y)]
            changed = [i for i in range(len(ids)) if pv[i] != a2[i] and pv[i] in DECISIVE]
            row.update({"correction_vs_A2": wilson(sum(right[i] for i in range(len(ids)) if not a2r[i]), a2r.count(False)),
                        "regression_vs_A2": wilson(sum(not right[i] for i in range(len(ids)) if a2r[i]), a2r.count(True)),
                        "accepted_decisive_change_precision": wilson(sum(right[i] for i in changed), len(changed))})
        out["arms"][arm] = row
    tests = {}
    for a, b in (PRIMARY,) + SECONDARY:
        if a in preds and b in preds:
            pa, pb = [preds[a][c] for c in ids], [preds[b][c] for c in ids]
            tests[f"{b} vs {a}"] = {"mcnemar": mcnemar(y, pa, pb), "bootstrap": bootstrap_diff(y, pa, pb, n_boot=N_BOOT, seed=SEED)}
    adj = holm({k: v["mcnemar"]["p_value_exact"] for k, v in tests.items()})
    for k in tests:
        tests[k]["p_holm"] = adj[k]
    out["tests"] = tests
    out["descriptive_tests"] = {}
    for a, b in DESCRIPTIVE:
        if a in preds and b in preds:
            pa, pb = [preds[a][c] for c in ids], [preds[b][c] for c in ids]
            out["descriptive_tests"][f"{b} vs {a}"] = {"mcnemar": mcnemar(y, pa, pb), "bootstrap": bootstrap_diff(y, pa, pb, n_boot=N_BOOT, seed=SEED)}
    return out


def _api_latency(call: dict, cache_dir: str) -> int:
    """Latency of the API call that produced this response: measured now for a live call, else the value the
    cache recorded when the response was first fetched (a cache hit itself takes ~0 ms)."""
    if call.get("source") == "live" or not call.get("request_key"):
        return call.get("latency_ms") or 0
    p = os.path.join(cache_dir, call["request_key"][:2], f"{call['request_key']}.json")
    return (json.load(open(p)).get("latency_ms") or 0) if os.path.exists(p) else 0


def efficiency(run_id: str, cache_dir: str = DEFAULT_CACHE_DIR) -> dict:
    """Per arm, medians over claims: tokens, LLM calls (live / cache), retrieval calls, LLM latency (this run, and
    the original API latency of every response, so arms served from the cache stay comparable), estimated cost."""
    import statistics
    d = os.path.join(RUNS_DIR, run_id)
    rows = {}
    for line in open(os.path.join(d, "predictions.jsonl")):
        p = json.loads(line)
        t = json.load(open(os.path.join(d, p["trace_path"])))
        calls = t.get("llm_calls") or []
        rows.setdefault(p["approach"], []).append({
            "input_tokens": (t.get("token_usage") or {}).get("input", 0), "output_tokens": (t.get("token_usage") or {}).get("output", 0),
            "llm_calls": len(calls), "llm_calls_live": sum(c.get("source") == "live" for c in calls),
            "retrieval_calls": sum(x.get("tool") == "retrieve_passages" for x in t.get("tool_calls") or []),
            "llm_latency_ms": sum(c.get("latency_ms") or 0 for c in calls),
            "api_latency_ms": sum(_api_latency(c, cache_dir) for c in calls), "cost_usd": t.get("estimated_cost_usd") or 0.0})
    return {a: {k: {"median": statistics.median(r[k] for r in rs), "total": sum(r[k] for r in rs)} for k in rs[0]} for a, rs in rows.items()}


def acceptance(res: dict) -> dict:
    """AC1-AC6 of the preregistration (AC7 = run integrity, enforced by load_run)."""
    v, a2 = res["arms"].get(CANDIDATE), res["arms"].get("A2_rag_numeric")
    rg = res["arms"].get("A3v2_1_1_RG")
    if not (v and a2 and rg):
        return {}
    t = res["tests"][f"{CANDIDATE} vs A2_rag_numeric"]["bootstrap"]["accuracy"]
    return {"AC1_accuracy_ge_A2_and_ci_low_gt_-8pp": v["accuracy"] >= a2["accuracy"] and t["ci_low"] > -0.08,
            "AC2_accuracy_gt_RG_v2.1.1": v["accuracy"] > rg["accuracy"],
            "AC3_accepted_change_precision_ge_70pct": (v["accepted_decisive_change_precision"]["rate"] or 0) >= 0.70,
            "AC4_regression_vs_A2_le_7pct": (v["regression_vs_A2"]["rate"] or 0) <= 0.07,
            "AC5_insufficient_recall_ge_A2_minus_5pp": v["insufficient_recall"]["rate"] >= a2["insufficient_recall"]["rate"] - 0.05,
            "AC6_numerical_ge_RG_minus_1_claim": v["by_category"]["numerical"]["k"] >= rg["by_category"]["numerical"]["k"] - 1}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run")
    ap.add_argument("--v1-run", default=V1_RUN)
    ap.add_argument("--check-v1", action="store_true")
    ap.add_argument("--errors-as-wrong", action="store_true", help="score ERRORs left after two --retry-errors rounds as wrong")
    args = ap.parse_args(argv)
    reference = load_reference()
    ref = {c: e["label"] for c, e in reference["labels"].items()}
    claims = {c.claim_id: c for c in load_claims(GOLD)}
    if args.check_v1:
        res = evaluate(load_run(args.v1_run, ("A1_conventional_rag", "A2_rag_numeric", "A3_contradiction_aware")), ref, claims)
        print(json.dumps({a: round(v["accuracy"], 4) for a, v in res["arms"].items()}))
        print(json.dumps({a: {k: v[k]["median"] for k in ("input_tokens", "llm_calls", "retrieval_calls")} for a, v in efficiency(args.v1_run).items()}))
        return
    errors = {}
    preds = load_run(args.run, errors_as_wrong=args.errors_as_wrong, errors=errors)
    preds.update({f"V1:{a}": p for a, p in load_run(args.v1_run, ("A3_contradiction_aware",)).items()})
    res = evaluate(preds, ref, claims)
    res.update({"acceptance": acceptance(res), "efficiency": efficiency(args.run), "run": args.run, "reference_sha256": file_sha256(REFERENCE_PATH),
                "gold_sha256": file_sha256(GOLD), "errors_scored_wrong": errors, "label_counts": dict(Counter(ref.values()))})
    d = os.path.join(OUT_DIR, args.run)
    if os.path.exists(d):
        raise SystemExit(f"{d} exists; not overwritten")
    os.makedirs(d)
    json.dump(res, open(os.path.join(d, "evaluation.json"), "w"), indent=1, default=str)
    print(json.dumps({a: {"correct": v["correct"], "accuracy": round(v["accuracy"], 4)} for a, v in res["arms"].items()}, indent=1))
    print(json.dumps(res["acceptance"], indent=1))


if __name__ == "__main__":
    main()
