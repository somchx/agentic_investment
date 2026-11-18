"""Decidability classifier (A3 v2.2, Approach A) over the dev-v0.2 claims: one isolated call per claim.

    # plan (no call): prints the upper bound and the confirmation phrase
    research/.venv/bin/python research/scripts/a3v2_decidability_run.py plan --max-cost 1.50
    # live run (paid): needs the exact phrase from `plan`; charges the shared ledger
    research/.venv/bin/python research/scripts/a3v2_decidability_run.py run --mode live --max-cost 1.50 --approve "<phrase>"

The model sees each claim's text, company and reporting period only (no
filing, label, design intent or system output). Responses go to the shared
request cache, so a re-run is free. Output:
results/dev_v0_2/decidability/<prompt version>.jsonl (never overwritten).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.cost_ledger import CostLedger  # noqa: E402
from engine.llm import CachedLLM, Pricing, approve_paid_run, confirmation_phrase  # noqa: E402
from a3v2.decidability import (DECIDABILITY_MAX_TOKENS, DECIDABILITY_PROMPT_VERSION, DECIDABILITY_TOOL,  # noqa: E402
                               decidability_request, record_from_output)

DATASET = os.path.join(RESEARCH_ROOT, "datasets", "development_cases_dev-v0.2.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "decidability")
LEDGER = "a3v2-dev-v0.2"


def claims() -> list[dict]:
    return [json.loads(x) for x in open(DATASET, encoding="utf-8") if x.strip()]


def plan(max_cost: float, rows=None) -> dict:
    rows = rows or claims()
    pricing = Pricing()
    per = []
    for c in rows:
        system, messages, tools, mt, _ = decidability_request(c)
        est_in = len(json.dumps([system, messages, tools], default=str)) // 3
        per.append(pricing.cost(est_in * 3 // 2, mt))  # what the ledger reserves per call
    bound = round(sum(per), 4)
    cap = min(max_cost, bound)
    return {"claims": len(rows), "max_llm_calls": len(rows), "reservation_bound_usd": bound, "max_cost_usd": round(cap, 2) if cap >= 0.01 else 0.01,
            "phrase": confirmation_phrase(round(cap, 2), len(rows)), "prompt_version": DECIDABILITY_PROMPT_VERSION,
            "max_output_tokens": DECIDABILITY_MAX_TOKENS}


def run(llm: CachedLLM, rows=None, out_dir: str = OUT_DIR) -> str:
    rows = rows or claims()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{DECIDABILITY_PROMPT_VERSION}{'' if llm.mode == 'live' or llm.mode == 'offline' else '.' + llm.mode}.jsonl")
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; not overwritten")
    recs = []
    for c in rows:
        payload = llm.create(*decidability_request(c))
        use = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == DECIDABILITY_TOOL["name"]), None)
        usage = payload.get("usage") or {}
        recs.append({"claim_id": c["claim_id"], "record": record_from_output(use["input"] if use else None), "raw": use["input"] if use else None,
                     "request_key": payload.get("_request_key"), "source": payload.get("_source"), "stop_reason": payload.get("stop_reason"),
                     "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                     "cost_usd": Pricing().cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0)) if payload.get("_source") == "live" else 0.0})
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("plan", "run"))
    ap.add_argument("--mode", choices=("offline", "live"), default="offline")
    ap.add_argument("--max-cost", type=float, required=True)
    ap.add_argument("--approve")
    args = ap.parse_args(argv)
    p = plan(args.max_cost)
    if args.cmd == "plan":
        print(json.dumps(p, indent=1))
        return
    approval, ledger = None, None
    if args.mode == "live":
        approval = approve_paid_run(p, args.approve or "")
        ledger = CostLedger(LEDGER)
        if ledger.remaining() < p["max_cost_usd"]:
            raise SystemExit(f"ledger {LEDGER} has ${ledger.remaining():.2f} left, below the approved ${p['max_cost_usd']:.2f}")
    llm = CachedLLM(mode=args.mode, approval=approval, ledger=ledger, retry={"max_retries": 5})
    out = run(llm)
    recs = [json.loads(x) for x in open(out)]
    print(json.dumps({"wrote": os.path.relpath(out, RESEARCH_ROOT), "claims": len(recs), "llm_stats": llm.stats,
                      "paid_spend_usd": round(sum(r["cost_usd"] for r in recs), 4),
                      "missing_tool_output": [r["claim_id"] for r in recs if r["raw"] is None]}, indent=1))


if __name__ == "__main__":
    main()
