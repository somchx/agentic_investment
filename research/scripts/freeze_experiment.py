"""Freeze a finished experiment (offline, read-only on every input).

    research/.venv/bin/python research/scripts/freeze_experiment.py --run <run_id> [--source-run <live_run_id> ...]
    research/.venv/bin/python research/scripts/freeze_experiment.py --run <run_id> --verify

The first form writes results/freeze/<run_id>.json once (read-only). The
second recomputes everything and exits 1 if any frozen checksum or score
has changed; outputs created after the freeze are listed as `added`.
"""
import argparse
import json
import os
import stat
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.freeze import FREEZE_DIR, build_freeze, diff_freeze, freeze_path  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--source-run", action="append", default=[], help="live run(s) the run was replayed from")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    path = freeze_path(args.run)
    if args.verify:
        old = json.load(open(path))
        new = build_freeze(args.run, list(old["runs"])[1:])
        d = diff_freeze(old, new)
        print(json.dumps({"freeze": path, "changed": d["changed"], "removed": d["removed"],
                          "added": len(d["added"])}, indent=1))
        return 1 if d["changed"] or d["removed"] else 0
    if os.path.exists(path):
        print(f"{path} exists; a run is frozen once (use --verify)")
        return 1
    rec = build_freeze(args.run, args.source_run)
    os.makedirs(FREEZE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    bad = {r: v["integrity_problems"] for r, v in rec["runs"].items() if v["integrity_problems"]}
    print(json.dumps({"wrote": path, "run_integrity_problems": bad, "prompt_drift": rec["prompts"]["drift"],
                      "llm_cache_missing": len(rec["llm_cache"]["missing"]), "results_files": len(rec["results"]),
                      "strict_accuracy": rec["scores"]["accuracy"]["strict"]}, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
