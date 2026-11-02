"""Run B0-B3 on a case file under the current protocol (b0b3-2.0).

    PYTHONPATH=app/core:. python scripts/run_b0b3.py --cases ../data/experiments/cases/dev_cases_v1.json --baselines B0
    PYTHONPATH=app/core:. python scripts/run_b0b3.py --cases ... --baselines B1,B2,B3 --repeats 3 --confirm-paid

B0 is free. B1-B3 call the Claude API and are refused unless --confirm-paid
is given (the estimate is printed first). Each run writes a new directory
data/experiments/<protocol>/<UTC timestamp>/ with manifest.json (versions,
model, prompt/tool hashes, git commit, case-file hash) and results.jsonl;
an existing directory is never overwritten, and earlier protocol results
(data/experiments/historical_v1) are never touched.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from agent_config import EXPERIMENT_BUDGET, EXPERIMENT_PROTOCOL_VERSION, config_manifest, estimate_cost
from baselines import BASELINES, run_case

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.path.join(ROOT, "data", "experiments")
# Rough upper bound per LLM case for the printed estimate only.
EST_TOKENS = {"B1": (6000, 1200), "B2": (30000, 2500), "B3": (40000, 3500)}


def git_state() -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--baselines", default="B0")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--confirm-paid", action="store_true")
    args = ap.parse_args()

    baselines = [b.strip() for b in args.baselines.split(",") if b.strip()]
    if any(b not in BASELINES for b in baselines):
        ap.error(f"baselines must be among {BASELINES}")
    raw = open(args.cases, "rb").read()
    cases = json.loads(raw)
    paid = [b for b in baselines if b != "B0"]
    runs = {b: len(cases) * (args.repeats if b != "B0" else 1) for b in baselines}
    estimate = sum(estimate_cost(*EST_TOKENS[b]) * runs[b] for b in paid)
    print(f"{len(cases)} cases; runs per baseline {runs}; estimated paid cost up to ${estimate:.2f}")
    if paid and not args.confirm_paid:
        print("Refusing to call the Claude API without --confirm-paid.")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = os.path.join(OUT_ROOT, EXPERIMENT_PROTOCOL_VERSION, stamp)
    os.makedirs(out_dir, exist_ok=False)
    manifest = {
        "protocol": EXPERIMENT_PROTOCOL_VERSION, "created_at": stamp, "git": git_state(),
        "cases_file": os.path.relpath(os.path.abspath(args.cases), ROOT), "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "baselines": baselines, "repeats": args.repeats, "budget": EXPERIMENT_BUDGET,
        "configs": {b: config_manifest(b, EXPERIMENT_BUDGET if b != "B0" else {}) for b in baselines},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    totals = {b: {"runs": 0, "cost_usd": 0.0, "errors": 0} for b in baselines}
    with open(os.path.join(out_dir, "results.jsonl"), "w") as out:
        for b in baselines:
            for rep in range(args.repeats if b != "B0" else 1):
                for case in cases:
                    try:
                        row = run_case(b, case)
                    except Exception as e:  # noqa: BLE001 -- failed runs are recorded, not hidden
                        row = {"case_id": case["case_id"], "baseline": b, "error": f"{type(e).__name__}: {e}"}
                        totals[b]["errors"] += 1
                    row["repeat"] = rep
                    totals[b]["runs"] += 1
                    totals[b]["cost_usd"] += (row.get("measures") or {}).get("cost_usd", 0.0)
                    out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                    print(b, rep, case["case_id"], row.get("stop_reason") or ("error" if "error" in row else "ok"))
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(totals, f, indent=2)
    print("wrote", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
