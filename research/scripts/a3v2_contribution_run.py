"""Contribution-figure extraction (A3 v2.2, item ข) on dev-v0.2: one isolated call per claim the decidability
record marks PRIMARY_DRIVER / LARGEST_FACTOR. The model sees the claim and the passages the v2.1.1 reviewer saw
(reviewed_evidence_ids of the A3v2_1_1_R trace, 1,200-character excerpts), nothing else.

    research/.venv/bin/python research/scripts/a3v2_contribution_run.py plan --max-cost 1.00
    research/.venv/bin/python research/scripts/a3v2_contribution_run.py run --mode live --max-cost 1.00 --approve "<phrase>"

Writes results/dev_v0_2/contribution/<prompt version>.jsonl (never overwritten). Responses are cached, so the
pipeline run that makes the same requests later is free.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.cost_ledger import CostLedger  # noqa: E402
from engine.llm import CachedLLM, Pricing, approve_paid_run, confirmation_phrase  # noqa: E402
from a3v2.contribution import EXTRACTION_PROMPT_VERSION, EXTRACTION_TOOL, extraction_request  # noqa: E402

CLAIMS_TABLE = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
DECIDABILITY = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "decidability", "a3v2-decidability-prompt-0.1.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "contribution")
LEDGER = "a3v2-dev-v0.2"


def jobs() -> list[dict]:
    rec = {json.loads(x)["claim_id"]: json.loads(x)["record"] for x in open(DECIDABILITY)}
    out = []
    for row in (json.loads(x) for x in open(CLAIMS_TABLE)):
        c = rec.get(row["claim_id"]) or {}
        if (c.get("contribution") or {}).get("type") not in ("PRIMARY_DRIVER", "LARGEST_FACTOR"):
            continue
        t = json.load(open(os.path.join(RESEARCH_ROOT, row["trace_RG"].replace("A3v2_1_1_RG", "A3v2_1_1_R"))))
        rv = next(s for s in t["stages"] if s["stage"] == "evidence_review")
        ev = {e["evidence_id"]: e for e in t["evidence"]}
        passages = [ev[i] for i in rv["reviewed_evidence_ids"] if i in ev]
        out.append({"claim_id": row["claim_id"], "request": extraction_request(t["claim"], c["contribution"], passages),
                    "test": c["contribution"]["type"]})
    return out


def plan(max_cost: float) -> dict:
    js, pricing = jobs(), Pricing()
    bound = round(sum(pricing.cost((len(json.dumps(j["request"][:3], default=str)) // 3) * 3 // 2, j["request"][3]) for j in js), 4)
    cap = round(min(max_cost, bound), 2)
    return {"claims": len(js), "max_llm_calls": len(js), "reservation_bound_usd": bound, "max_cost_usd": cap,
            "phrase": confirmation_phrase(cap, len(js)), "prompt_version": EXTRACTION_PROMPT_VERSION}


def run(llm: CachedLLM, out_dir: str = OUT_DIR) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{EXTRACTION_PROMPT_VERSION}.jsonl")
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; not overwritten")
    recs = []
    for j in jobs():
        payload = llm.create(*j["request"])
        use = next((b for b in payload.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == EXTRACTION_TOOL["name"]), None)
        u = payload.get("usage") or {}
        recs.append({"claim_id": j["claim_id"], "test": j["test"], "output": use["input"] if use else None,
                     "request_key": payload.get("_request_key"), "source": payload.get("_source"), "stop_reason": payload.get("stop_reason"),
                     "cost_usd": Pricing().cost(u.get("input_tokens", 0), u.get("output_tokens", 0)) if payload.get("_source") == "live" else 0.0})
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
    approval = ledger = None
    if args.mode == "live":
        approval, ledger = approve_paid_run(p, args.approve or ""), CostLedger(LEDGER)
        if ledger.remaining() < p["max_cost_usd"]:
            raise SystemExit(f"ledger {LEDGER} has ${ledger.remaining():.2f} left, below ${p['max_cost_usd']:.2f}")
    llm = CachedLLM(mode=args.mode, approval=approval, ledger=ledger, retry={"max_retries": 5})
    out = run(llm)
    recs = [json.loads(x) for x in open(out)]
    print(json.dumps({"wrote": os.path.relpath(out, RESEARCH_ROOT), "claims": len(recs), "llm_stats": llm.stats,
                      "paid_spend_usd": round(sum(r["cost_usd"] for r in recs), 4),
                      "no_tool_output": [r["claim_id"] for r in recs if r["output"] is None]}, indent=1))


if __name__ == "__main__":
    main()
