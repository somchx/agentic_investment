"""Rebuild lost dev-v0.2 run directories from the committed LLM response cache (incident 2026-11-18).

The original run directories (results/runs/, never committed) were deleted with the Kilo worktree.
This re-runs each one in OFFLINE mode (cache only; a cache miss stays a miss, nothing is called)
with its original config and claim set, under its original run id so the committed claims table
and tests that name it resolve. Each rebuilt directory gets RESTORED_FROM_CACHE.json saying so:
its manifest/status describe the rebuild (offline, today's commit), not the original live run.

    research/.venv/bin/python research/scripts/restore_dev_runs.py
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
import engine.runner as runner  # noqa: E402
from scripts.run_experiment import load_any_config  # noqa: E402

CLAIMS_TABLE = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
SMOKE12 = os.path.join(RESEARCH_ROOT, "configs", "batches", "dev_v0_2_smoke12.txt")


def plan() -> dict:
    """run id -> (config, claim ids), from the committed claims table and batch file."""
    by = {}
    for r in (json.loads(x) for x in open(CLAIMS_TABLE)):
        by.setdefault(r["trace_RG"].split("/")[2], []).append(r["claim_id"])
    out = {rid: ("configs/a3v2_1_1_dev_v0_2.json", sorted(ids)) for rid, ids in by.items()}
    smoke = [x.strip() for x in open(SMOKE12) if x.strip() and not x.startswith("#")]
    out["a3v2.1-dev-v0.2-20261117T085608Z"] = ("configs/a3v2_1_dev_v0_2.json", smoke)
    # the dev-v0.2 run behind the A3v2_2e 64/72 result (all 72 claims, its six arms; A1/SR were never run on dev)
    out["a3v2.2-dev-v0.2-20261118T052512Z"] = ("configs/a3v2_2_dev_v0_2.json", None,
                                               ["A2_rag_numeric", "A3v2_1_1_R", "A3v2_1_1_RG", "A3v2_2", "A3v2_2c", "A3v2_2e"])
    return out


def restore(rid: str, config: str, ids: list[str] | None, approaches: list[str] | None = None) -> dict:
    d = os.path.join(runner.RUNS_DIR, rid)
    if os.path.exists(d):
        raise SystemExit(f"{d} exists; not overwritten")
    cfg = load_any_config(config)
    claims, info = runner.select_claims(cfg, claim_ids=ids)
    original = runner.new_run_id
    runner.new_run_id = lambda experiment_id, mode: rid
    try:
        runner.run_experiment(cfg, claims, info, llm_mode="offline", approaches=approaches, progress=lambda *a: None)
    finally:
        runner.new_run_id = original
    st = json.load(open(os.path.join(d, "status.json")))
    note = {"restored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "original_run_id": rid,
            "config": config, "claims": ids or "all", "approaches": approaches or "all", "mode": "offline (LLM response cache only; no API call)",
            "why": "original run directory lost with the Kilo worktree on 2026-11-18 (docs/a3v2_2/10_gold150_run_log.md)",
            "state": st["state"], "completed": st.get("completed"), "cache_misses": st.get("cache_misses")}
    json.dump(note, open(os.path.join(d, "RESTORED_FROM_CACHE.json"), "w"), indent=1)
    return note


if __name__ == "__main__":
    for rid, spec in plan().items():
        if os.path.exists(os.path.join(runner.RUNS_DIR, rid)):
            print(rid, "exists; skipped")
            continue
        n = restore(rid, *spec)
        print(rid, n["state"], n["completed"], "misses", len(n["cache_misses"] or []))
