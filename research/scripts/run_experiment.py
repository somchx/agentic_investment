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
    --max-cost 20                       cap the approved dollars below the plan's upper bound
                                        (the run stops before exceeding it; resume later)
    --claims-file batches/x.txt         restrict to the claim ids listed in a file (one per line)
    --categories ambiguous,interpretive restrict to claim categories
    --ledger NAME [--ledger-cap 15]     aggregate cap shared by every batch, process and resume
                                        (results/cost_ledger/NAME.jsonl; the cap is fixed when opened)
    --ledger-status NAME                print a ledger's spend and exit

A config whose approaches include A3 v2 arms (no v1 `kind`, or kind
contradiction_aware_v2) is loaded with a3v2.config.load_v2_config. A live A3 v2
run requires --ledger.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.config import APPROACH_KINDS, load_config  # noqa: E402
from engine.cost_ledger import CostLedger, ledger_path  # noqa: E402
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
    ap.add_argument("--max-cost", type=float, default=None, help="approved dollar cap (default: the plan's upper bound)")
    ap.add_argument("--claims-file", default=None)
    ap.add_argument("--categories", default="")
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--ledger-cap", type=float, default=None)
    ap.add_argument("--ledger-status", action="store_true", help="print the ledger named by --ledger and exit")
    ap.add_argument("--retry-errors", action="store_true", help="with --resume: run ERROR predictions again (old rows are kept aside)")
    args = ap.parse_args()

    if args.ledger_status:
        print(json.dumps(CostLedger(args.ledger).status(), indent=2))
        return 0
    cfg = load_any_config(args.config)
    ids = [c for c in args.claims.split(",") if c]
    if args.claims_file:
        ids += [line.strip() for line in open(args.claims_file) if line.strip() and not line.startswith("#")]
    claims, info = select_claims(cfg, split=args.split, claim_ids=ids or None, allow_gold=args.allow_gold)
    cats = [c for c in args.categories.split(",") if c]
    if cats:
        claims = [c for c in claims if c.claim_category in cats]
        info = {**info, "claim_ids": [c.claim_id for c in claims], "categories": cats}
    if not claims:
        raise SystemExit("no claims selected")
    approaches = [a for a in args.approaches.split(",") if a] or None
    is_v2 = any(a["kind"] == "contradiction_aware_v2" for a in cfg["approaches"].values())
    if args.mode == "live" and is_v2 and not args.ledger:
        raise SystemExit("a live A3 v2 run needs --ledger NAME (aggregate cap across batches)")
    ledger, remaining = None, None
    if args.ledger and (args.plan or args.mode is None):  # a plan never creates or writes a ledger
        remaining = CostLedger(args.ledger).remaining() if os.path.exists(ledger_path(args.ledger)) else args.ledger_cap
    elif args.ledger and args.mode == "live":
        ledger = CostLedger(args.ledger, args.ledger_cap)
        remaining = ledger.remaining()
    plan = plan_run(cfg, claims, approaches, cost_cap_usd=args.max_cost, ledger_remaining_usd=remaining)
    print(json.dumps(plan, indent=2))
    if args.plan or args.mode is None:
        print("Plan only. Choose --mode offline | mock | live to run.")
        return 0
    approval = approve_paid_run(plan, args.approve) if args.mode == "live" else None
    if args.retry_errors and not args.resume:
        raise SystemExit("--retry-errors needs --resume RUN_ID")
    run_experiment(cfg, claims, info, llm_mode=args.mode, approval=approval, approaches=approaches, resume_run_id=args.resume,
                   ledger=ledger, retry_errors=args.retry_errors)
    return 0


def load_any_config(path: str) -> dict:
    with open(path if os.path.isabs(path) else os.path.join(os.path.dirname(__file__), "..", path)) as f:
        raw = json.load(f)
    if all(a.get("kind") in APPROACH_KINDS for a in raw.get("approaches") or []):
        return load_config(path)
    from a3v2.config import load_v2_config
    return load_v2_config(path)


if __name__ == "__main__":
    sys.exit(main())
