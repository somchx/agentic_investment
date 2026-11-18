"""One claim-level comparison table for the A3 v2.1.1 development experiment.

    research/.venv/bin/python research/scripts/a3v2_dev_consolidate.py \
        --runs a3v2.1.1-dev-v0.2-20261117T092214Z a3v2.1.1-dev-v0.2-20261117T093519Z a3v2.1.1-dev-v0.2-20261117T100923Z

Reads the completed, locked runs (never writes to them) and writes
results/dev_v0_2/a3v2.1.1_claims.{jsonl,csv} plus a manifest with each run's
SHA256SUMS check and the file hashes. It refuses unless the runs share one
configuration, every run is complete and intact, and the union holds each
dev-v0.2 claim exactly once with A2, A3v2_1_1_R and A3v2_1_1_RG predictions
(72 claims, 216 predictions). No reference label is read.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import file_sha256, load_claims  # noqa: E402
from engine.runner import RUNS_DIR, verify_run_integrity  # noqa: E402

APPROACHES = ("A2_rag_numeric", "A3v2_1_1_R", "A3v2_1_1_RG")
DEFAULT_RUNS = ("a3v2.1.1-dev-v0.2-20261117T092214Z", "a3v2.1.1-dev-v0.2-20261117T093519Z", "a3v2.1.1-dev-v0.2-20261117T100923Z")
DATASET = os.path.join(RESEARCH_ROOT, "datasets", "development_cases_dev-v0.2.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2")


def _stage(trace: dict, name: str) -> dict:
    return next((s for s in trace.get("stages") or [] if s.get("stage") == name), {})


def claim_row(cid: str, claim, run_id: str, preds: dict, traces: dict) -> dict:
    a2, r, rg = (preds[a] for a in APPROACHES)
    t = traces["A3v2_1_1_RG"]
    review, guard, analysis = _stage(t, "evidence_review"), _stage(t, "reconciliation_guard"), _stage(t, "analyze_claim")
    findings = review.get("findings") or []
    period = (analysis.get("analysis") or {}).get("claim_period") or {}
    calls = [c for a in ("A2_rag_numeric", "A3v2_1_1_R") for c in traces[a].get("llm_calls") or []]
    rv_call = next((c for c in traces["A3v2_1_1_R"].get("llm_calls") or [] if c["stage"] == "evidence_review"), {})
    return {
        "claim_id": cid, "company": claim.company, "claim_type": claim.claim_category, "difficulty": claim.difficulty,
        "reporting_period": claim.reporting_period, "as_of_date": claim.as_of_date, "run_id": run_id,
        "pred_A2": a2["predicted_label"], "pred_R": r["predicted_label"], "pred_RG": rg["predicted_label"],
        "initial_label_R": r.get("initial_label"), "stop_reason_A2": a2["stop_reason"], "stop_reason_R": r["stop_reason"],
        "stop_reason_RG": rg["stop_reason"],
        "R_changed_vs_A2": r["predicted_label"] != a2["predicted_label"], "RG_changed_vs_A2": rg["predicted_label"] != a2["predicted_label"],
        "guard_outcome": guard.get("outcome"), "guard_reason": guard.get("reason_code"), "guard_proposed_label": guard.get("proposed_label"),
        "guard_deciding_findings": ";".join(guard.get("deciding_findings") or []),
        "guard_excluded_citations": len(guard.get("excluded_citations") or []),
        "review_llm_called": review.get("llm_called"), "review_findings": len(findings),
        "review_valid_deciding": sum(1 for f in findings if f.get("validation_status") == "VALID" and f.get("relation") in ("ENTAILS", "CONTRADICTS")),
        "review_downgrades": json.dumps(dict(Counter(f["downgraded_reason"] for f in findings if f.get("downgraded_reason"))), sort_keys=True),
        "review_dropped_findings": len(review.get("dropped_findings") or []),
        "review_output_tokens": rv_call.get("output_tokens"), "review_stop_reason": rv_call.get("stop_reason"),
        "period_claim_label": period.get("label"), "period_claim_source": period.get("source"),
        "period_status_counts": json.dumps(dict(Counter(s for f in findings for s in f.get("period_compatibility") or [])), sort_keys=True),
        "statement_time_counts": json.dumps(dict(Counter(s for f in findings for s in f.get("statement_time") or [])), sort_keys=True),
        "period_derivations": len(review.get("period_derivations") or []),
        "llm_calls_live": sum(1 for c in calls if c.get("source") == "live"),
        "llm_calls_cache": sum(1 for c in calls if c.get("source") == "cache"),
        "input_tokens_live": sum(c.get("input_tokens", 0) for c in calls if c.get("source") == "live"),
        "output_tokens_live": sum(c.get("output_tokens", 0) for c in calls if c.get("source") == "live"),
        "rg_llm_sources": json.dumps(dict(Counter(c.get("source") for c in t.get("llm_calls") or [])), sort_keys=True),
        "trace_RG": os.path.join("results", "runs", run_id, rg["trace_path"]),
    }


def consolidate(run_ids=DEFAULT_RUNS, runs_dir: str = RUNS_DIR, dataset: str = DATASET) -> tuple[list[dict], dict]:
    claims = {c.claim_id: c for c in load_claims(dataset)}
    rows, seen, problems, runs_meta, hashes = [], Counter(), [], {}, set()
    for rid in run_ids:
        d = os.path.join(runs_dir, rid)
        st, man = json.load(open(os.path.join(d, "status.json"))), json.load(open(os.path.join(d, "manifest.json")))
        bad = verify_run_integrity(d)
        if st["state"] != "complete" or bad:
            problems.append(f"{rid}: state {st['state']}, integrity {bad}")
        hashes.add(json.dumps(man["approach_config_hashes"], sort_keys=True))
        if man["dataset"]["sha256"] != file_sha256(dataset):
            problems.append(f"{rid}: dataset hash differs")
        preds = [json.loads(x) for x in open(os.path.join(d, "predictions.jsonl"))]
        by = {}
        for p in preds:
            by.setdefault(p["claim_id"], {})[p["approach"]] = p
        runs_meta[rid] = {"claims": len(by), "predictions": len(preds), "paid_spend_usd": st.get("paid_spend_usd"),
                          "llm_stats": st.get("llm_stats"), "replay_llm_stats": st.get("replay_llm_stats"),
                          "sha256sums": file_sha256(os.path.join(d, "SHA256SUMS")), "config_path": man.get("config_path")}
        for cid, ps in sorted(by.items()):
            seen[cid] += 1
            if set(ps) != set(APPROACHES) or any(ps[a]["stop_reason"] != "COMPLETED" for a in APPROACHES):
                problems.append(f"{rid}/{cid}: approaches {sorted(ps)} / stop reasons {[ps[a].get('stop_reason') for a in ps]}")
                continue
            traces = {a: json.load(open(os.path.join(d, ps[a]["trace_path"]))) for a in APPROACHES}
            rows.append(claim_row(cid, claims[cid], rid, ps, traces))
    if len(hashes) != 1:
        problems.append("runs do not share one configuration")
    dup = sorted(c for c, n in seen.items() if n > 1)
    missing = sorted(set(claims) - set(seen))
    if dup or missing:
        problems.append(f"duplicates {dup}, missing {missing}")
    n_pred = sum(m["predictions"] for m in runs_meta.values())
    if len(rows) != len(claims) or n_pred != 3 * len(claims):
        problems.append(f"{len(rows)} complete claims / {n_pred} predictions (expected {len(claims)} / {3 * len(claims)})")
    if problems:
        raise SystemExit("cannot consolidate:\n  " + "\n  ".join(problems))
    meta = {"dataset": os.path.relpath(dataset, RESEARCH_ROOT), "dataset_sha256": file_sha256(dataset), "claims": len(rows),
            "predictions": n_pred, "approaches": list(APPROACHES), "approach_config_hashes": json.loads(next(iter(hashes))), "runs": runs_meta}
    return sorted(rows, key=lambda r: r["claim_id"]), meta


def write(rows: list[dict], meta: dict, out_dir: str = OUT_DIR) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "a3v2.1.1_claims")
    for p in (base + ".jsonl", base + ".csv", base + ".manifest.json"):
        if os.path.exists(p):
            raise SystemExit(f"{p} exists; consolidated outputs are not overwritten")
    with open(base + ".jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = {**meta, "outputs": {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in (base + ".jsonl", base + ".csv")}}
    with open(base + ".manifest.json", "w") as f:
        json.dump(meta, f, indent=1)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", default=list(DEFAULT_RUNS))
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args(argv)
    rows, meta = consolidate(args.runs)
    meta = write(rows, meta, args.out_dir)
    print(json.dumps({k: meta[k] for k in ("claims", "predictions", "outputs")}, indent=1))


if __name__ == "__main__":
    main()
