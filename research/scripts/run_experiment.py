"""Run an experiment config from the command line.

    # cost plan only (default; never calls the API)
    research/.venv/bin/python research/scripts/run_experiment.py configs/main_comparison.json --plan

    # offline: answer only from the LLM response cache (free; incomplete if anything is not cached)
    research/.venv/bin/python research/scripts/run_experiment.py configs/main_comparison.json --mode offline

    # mock LLM: exercises the whole pipeline without credentials (NOT results)
    research/.venv/bin/python research/scripts/run_experiment.py configs/main_comparison.json --mode mock

    # live (paid): requires the exact phrase printed by --plan
    research/.venv/bin/python research/scripts/run_experiment.py configs/main_comparison.json --mode live \
        --approve "I approve up to N paid Claude API calls costing at most $X.XX"

    --claims DEV-AAPL-01,DEV-MSFT-01   restrict to some claims
    --approaches A2_rag_numeric,...     restrict to some approaches
    --resume RUN_ID                     continue an interrupted run
    --split gold --allow-gold           held-out evaluation (final runs only)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config import load_config  # noqa: E402
from engine.llm import approve_paid_run  # noqa: E402
from engine.runner import plan_run, run_experiment, select_claims  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--mode", choices=["offline", "mock", "live"], default=None)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--approve", default="")
    ap.add_argument("--claims", default="")
    ap.add_argument("--approaches", default="")
    ap.add_argument("--resume", default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--allow-gold", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    claims, info = select_claims(cfg, split=args.split, claim_ids=[c for c in args.claims.split(",") if c] or None,
                                 allow_gold=args.allow_gold)
    approaches = [a for a in args.approaches.split(",") if a] or None
    plan = plan_run(cfg, claims, approaches)
    print(json.dumps(plan, indent=2))
    if args.plan or args.mode is None:
        print("Plan only. Choose --mode offline | mock | live to run.")
        return 0
    approval = approve_paid_run(plan, args.approve) if args.mode == "live" else None
    run_experiment(cfg, claims, info, llm_mode=args.mode, approval=approval, approaches=approaches, resume_run_id=args.resume)
    return 0


if __name__ == "__main__":
    sys.exit(main())
