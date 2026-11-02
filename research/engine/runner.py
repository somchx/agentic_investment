"""Experiment runner: cost plan, paid-call gate, resumable immutable runs.

A run lives in research/results/runs/<run_id>/:

    manifest.json        everything needed to reproduce it (config + hashes,
                         model, prompt/tool hashes, code commit, dataset
                         hashes, retrieval settings, budgets, LLM mode)
    predictions.jsonl    one row per (approach, claim), appended + fsynced
                         as each finishes -- an interrupted run keeps them
    traces/<approach>/<claim_id>.json   full investigation trace
    status.json          running | incomplete | complete, counters
    corpus.json          SEC documents actually used, with sha256
    SHA256SUMS           written when complete; files are then read-only

Resuming (`resume_run_id=`) skips (approach, claim) pairs already in
predictions.jsonl, and the LLM response cache means a claim interrupted
mid-way does not repeat a paid call either. A completed run is never
written again; a new run gets a new directory.
"""

import hashlib
import json
import os
import platform
import stat
import subprocess
import time
from datetime import datetime, timezone

from . import ENGINE_VERSION, REPO_ROOT, RESEARCH_ROOT
from .config import config_hash, thaw
from .corpus import CLEANING_VERSION, RETRIEVAL_VERSION, document_sha256, facts_path
from .datasets import DEV_PATH, GOLD_PATH, check_split_separation, file_sha256, load_split
from .llm import BudgetExceeded, CachedLLM, CacheMiss, PaidCallNotApproved, Pricing, confirmation_phrase
from .numeric import NUMERIC_VERSION, RECONCILE_VERSION
from .prompts import prompt_manifest

# Overridable so tests can execute the notebooks against a temporary store.
RUNS_DIR = os.environ.get("RC_RESEARCH_RUNS_DIR") or os.path.join(RESEARCH_ROOT, "results", "runs")

# Calls per claim when every stage runs.
CALLS = {"conventional_rag": 1, "financial_verification": 1, "contradiction_aware": 3, "self_reflection": 3}


class RunLocked(RuntimeError):
    pass


def git_state() -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    porcelain = git("status", "--porcelain") or ""
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(porcelain),
            "dirty_research_files": sorted({line[3:] for line in porcelain.splitlines() if line[3:].startswith("research/")})[:200]}


def _code_hashes() -> dict:
    """sha256 of every research engine/experiment source file, so a run is
    tied to the exact code even when the working tree is uncommitted."""
    out = {}
    for sub in ("engine", "experiments"):
        d = os.path.join(RESEARCH_ROOT, sub)
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                out[f"{sub}/{name}"] = file_sha256(os.path.join(d, name))
    for name in ("evidence_ledger.py", "xbrl_extract.py", "sec_client.py", "agent_config.py", "investigation_engine.py"):
        out[f"backend/app/core/{name}"] = file_sha256(os.path.join(REPO_ROOT, "backend", "app", "core", name))
    return out


# ----------------------------------------------------------------- claims

def select_claims(cfg: dict, split: str | None = None, claim_ids: list[str] | None = None, allow_gold: bool = False):
    split = split or cfg["dataset"].get("split", "development")
    if split == "gold" and not allow_gold:
        raise PermissionError("gold (held-out) claims are only for final evaluation; pass allow_gold=True deliberately")
    dev_path = os.path.join(RESEARCH_ROOT, cfg["dataset"].get("development_path", os.path.relpath(DEV_PATH, RESEARCH_ROOT)))
    gold_path = os.path.join(RESEARCH_ROOT, cfg["dataset"].get("gold_path", os.path.relpath(GOLD_PATH, RESEARCH_ROOT)))
    dev, gold = load_split("development", dev_path), load_split("gold", gold_path)
    problems = check_split_separation(dev, gold)
    if problems:
        raise ValueError("development / gold separation broken: " + "; ".join(problems))
    claims = dev if split == "development" else gold
    if claim_ids:
        wanted = set(claim_ids)
        claims = [c for c in claims if c.claim_id in wanted]
        missing = wanted - {c.claim_id for c in claims}
        if missing:
            raise ValueError(f"unknown claim ids for split {split}: {sorted(missing)}")
    return claims, {"split": split, "path": os.path.relpath(dev_path if split == "development" else gold_path, RESEARCH_ROOT),
                    "sha256": file_sha256(dev_path if split == "development" else gold_path),
                    "claim_ids": [c.claim_id for c in claims]}


# ------------------------------------------------------------------- plan

def plan_run(cfg: dict, claims, approaches: list[str] | None = None, pricing: Pricing | None = None) -> dict:
    """Upper bound on calls and cost before anything runs. The bound assumes
    every call uses the full per-claim input budget share and the full
    output cap; the typical estimate assumes ~2.5k input tokens for the
    initial call (passages + instructions) and ~4k for later calls."""
    pricing = pricing or Pricing()
    names = approaches or list(cfg["approaches"])
    rows, max_calls, max_cost, typical = [], 0, 0.0, 0.0
    for name in names:
        a = cfg["approaches"][name]
        calls = CALLS[a["kind"]] if (a["kind"] != "contradiction_aware" or a["contradiction"]["enabled"]) else 1
        out_cap = a["llm"]["max_output_tokens"]
        n = len(claims)
        worst = n * pricing.cost(a["budget"]["max_input_tokens_per_claim"], calls * out_cap)
        typ = n * pricing.cost(2500 + (calls - 1) * 4000, 600 * calls)
        rows.append({"approach": name, "kind": a["kind"], "claims": n, "llm_calls": n * calls,
                     "upper_bound_usd": round(worst, 2), "typical_usd": round(typ, 2)})
        max_calls += n * calls
        max_cost += worst
        typical += typ
    max_cost = round(max_cost + 0.005, 2)
    return {"claims": len(claims), "approaches": rows, "max_llm_calls": max_calls, "max_cost_usd": max_cost,
            "typical_cost_usd": round(typical, 2),
            "note": ("Initial-stage requests are byte-identical across approaches, so the response cache serves them once; "
                     "already-cached requests cost nothing. Figures are bounds, not quotes."),
            "confirmation_phrase": confirmation_phrase(max_cost, max_calls), "pricing_version": pricing.version}


# -------------------------------------------------------------- run files

def _write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _append_jsonl(path: str, row: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _lock(run_dir: str) -> None:
    sums = []
    for root, _, files in os.walk(run_dir):
        for name in sorted(files):
            p = os.path.join(root, name)
            if name == "SHA256SUMS":
                continue
            with open(p, "rb") as f:
                sums.append(f"{hashlib.sha256(f.read()).hexdigest()}  {os.path.relpath(p, run_dir)}")
    with open(os.path.join(run_dir, "SHA256SUMS"), "w") as f:
        f.write("\n".join(sorted(sums, key=lambda s: s.split("  ")[1])) + "\n")
    for root, _, files in os.walk(run_dir):
        for name in files:
            p = os.path.join(root, name)
            os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def verify_run_integrity(run_dir: str) -> list[str]:
    """Files whose content no longer matches SHA256SUMS (empty = intact)."""
    path = os.path.join(run_dir, "SHA256SUMS")
    if not os.path.exists(path):
        return ["SHA256SUMS missing (run not complete)"]
    bad = []
    for line in open(path).read().splitlines():
        digest, rel = line.split("  ", 1)
        p = os.path.join(run_dir, rel)
        if not os.path.exists(p) or file_sha256(p) != digest:
            bad.append(rel)
    return bad


def new_run_id(experiment_id: str, mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{'MOCK-' if mode == 'mock' else ''}{experiment_id}-{stamp}"


# -------------------------------------------------------------------- run

def run_experiment(cfg: dict, claims, dataset_info: dict, *, llm_mode: str = "offline", approval=None,
                   approaches: list[str] | None = None, resume_run_id: str | None = None, llm=None,
                   runs_dir: str = RUNS_DIR, progress=print) -> str:
    from experiments import RUNNERS

    names = approaches or list(cfg["approaches"])
    unknown = [n for n in names if n not in cfg["approaches"]]
    if unknown:
        raise ValueError(f"unknown approaches {unknown}")
    common = cfg["common"]
    llm = llm or CachedLLM(mode=llm_mode, model=common["llm"]["model"], temperature=common["llm"]["temperature"], approval=approval)
    if llm.mode != llm_mode:
        raise ValueError("injected LLM mode differs from llm_mode")

    if resume_run_id:
        run_id = resume_run_id
        run_dir = os.path.join(runs_dir, run_id)
        status = json.load(open(os.path.join(run_dir, "status.json")))
        if status["state"] == "complete":
            raise RunLocked(f"run {run_id} is complete and immutable; start a new run")
        manifest = json.load(open(os.path.join(run_dir, "manifest.json")))
        expected = {n: config_hash(cfg["approaches"][n]) for n in names}
        if any(manifest["approach_config_hashes"].get(n) != h for n, h in expected.items()):
            raise ValueError("config changed since this run started; resume only with the identical config")
        if manifest["dataset"]["claim_ids"] != dataset_info["claim_ids"]:
            raise ValueError("claims differ from the run being resumed")
        # offline and live share the response cache, so an offline run may be
        # completed live; mock and real responses must never mix in one run
        if (manifest["llm"]["mode"] == "mock") != (llm_mode == "mock") or manifest["llm"]["model"] != llm.model:
            raise ValueError("LLM mode (mock vs real) or model differs from the run being resumed")
        _append_jsonl(os.path.join(run_dir, "resume_log.jsonl"), {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": llm_mode, "git": git_state(),
            "approval": None if approval is None else {"max_cost_usd": approval.max_cost_usd, "max_calls": approval.max_calls}})
    else:
        run_id = new_run_id(cfg["experiment_id"], llm_mode)
        run_dir = os.path.join(runs_dir, run_id)
        os.makedirs(os.path.join(run_dir, "traces"), exist_ok=False)
        from agent_config import AGENT_WORKFLOW_VERSION, EVIDENCE_GATE_VERSION
        manifest = {
            "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "experiment_id": cfg["experiment_id"], "description": cfg.get("description"), "config_path": cfg.get("source_path"),
            "approaches": names, "approach_configs": {n: thaw(cfg["approaches"][n]) for n in names},
            "approach_config_hashes": {n: config_hash(cfg["approaches"][n]) for n in names},
            "comparisons": cfg.get("comparisons"), "fairness_problems": cfg.get("fairness_problems"),
            "dataset": dataset_info, "llm": llm.describe(), "is_mock": llm_mode == "mock",
            "versions": {"engine": ENGINE_VERSION, **prompt_manifest(), "numeric": NUMERIC_VERSION, "reconcile": RECONCILE_VERSION,
                         "retrieval": RETRIEVAL_VERSION, "cleaning": CLEANING_VERSION,
                         "app_agent_workflow": AGENT_WORKFLOW_VERSION, "app_evidence_gate": EVIDENCE_GATE_VERSION},
            "evidence_cutoff_rule": "per claim: SEC filings with filed <= as_of_date and form in allowed_sources",
            "xbrl_facts_sha256": {t: file_sha256(facts_path(t)) for t in sorted({c.company for c in claims})},
            "code": {"git": git_state(), "files_sha256": _code_hashes()},
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "approval": None if approval is None else {"max_cost_usd": approval.max_cost_usd, "max_calls": approval.max_calls,
                                                         "phrase": approval.phrase},
        }
        _write_json(os.path.join(run_dir, "manifest.json"), manifest)
        status = {"state": "running"}

    pred_path = os.path.join(run_dir, "predictions.jsonl")
    done = set()
    if os.path.exists(pred_path):
        for line in open(pred_path):
            if line.strip():
                r = json.loads(line)
                done.add((r["approach"], r["claim_id"]))
    counters = {"completed": len(done), "cache_misses": [], "errors": 0, "resumed_skipped": len(done)}
    corpus = {}

    def save_status(state: str, note: str | None = None):
        _write_json(os.path.join(run_dir, "status.json"), {
            "state": state, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "expected_predictions": len(names) * len(claims), **counters, "note": note,
            "llm_stats": llm.stats, "paid_spend_usd": round(llm.guard.spent_usd, 6)})

    save_status("running")
    meta = {c.claim_id: c for c in claims}
    try:
        for name in names:
            a_cfg = cfg["approaches"][name]
            os.makedirs(os.path.join(run_dir, "traces", name), exist_ok=True)
            for c in claims:
                if (name, c.claim_id) in done:
                    continue
                t0 = time.monotonic()
                try:
                    pred, trace = RUNNERS[a_cfg["kind"]](c.to_input(), a_cfg, llm, run_id)
                except CacheMiss as e:
                    counters["cache_misses"].append(f"{name}:{c.claim_id}")
                    progress(f"  {name} {c.claim_id}: not cached ({e})")
                    continue
                except (PaidCallNotApproved, BudgetExceeded, KeyboardInterrupt):
                    raise
                except Exception as e:  # noqa: BLE001 -- recorded as a failed prediction, never hidden
                    counters["errors"] += 1
                    pred = {"claim_id": c.claim_id, "approach": name, "approach_kind": a_cfg["kind"], "predicted_label": None,
                            "stop_reason": "ERROR", "error": f"{type(e).__name__}: {e}"[:500],
                            "latency_ms": round((time.monotonic() - t0) * 1000)}
                    trace = {"error": pred["error"], "claim": c.to_input().to_dict()}
                for f in (trace.get("corpus") or {}).get("filings", []):
                    corpus[f["accession_number"]] = {**f, "company": c.company}
                trace_path = os.path.join(run_dir, "traces", name, f"{c.claim_id}.json")
                _write_json(trace_path, trace)
                pred.update({"run_id": run_id, "is_mock": llm_mode == "mock", "split": dataset_info["split"],
                             "company": c.company, "claim_category": c.claim_category, "difficulty": c.difficulty,
                             "as_of_date": c.as_of_date, "trace_path": os.path.relpath(trace_path, run_dir)})
                _append_jsonl(pred_path, pred)
                counters["completed"] += 1
                progress(f"  {name} {c.claim_id}: {pred.get('predicted_label')} ({pred.get('stop_reason')})")
    except (PaidCallNotApproved, BudgetExceeded, KeyboardInterrupt) as e:
        save_status("incomplete", f"stopped: {type(e).__name__}: {e}")
        _merge_corpus(run_dir, corpus)
        raise
    _merge_corpus(run_dir, corpus)
    complete = counters["completed"] == len(names) * len(claims)
    save_status("complete" if complete else "incomplete",
                None if complete else f"{len(counters['cache_misses'])} (approach, claim) pairs not cached; resume in live mode")
    if complete:
        _lock(run_dir)
    progress(f"run {run_id}: {'complete' if complete else 'incomplete'} -> {run_dir}")
    return run_id


def _merge_corpus(run_dir: str, corpus: dict) -> None:
    path = os.path.join(run_dir, "corpus.json")
    existing = json.load(open(path)) if os.path.exists(path) else {}
    existing.update(corpus)
    for f in existing.values():
        f["sha256_now"] = document_sha256(f["accession_number"], f["primary_document"])
    _write_json(path, existing)


# ------------------------------------------------------------------- load

def list_runs(runs_dir: str = RUNS_DIR) -> list[dict]:
    out = []
    if not os.path.isdir(runs_dir):
        return out
    for name in sorted(os.listdir(runs_dir)):
        d = os.path.join(runs_dir, name)
        if not os.path.isfile(os.path.join(d, "manifest.json")):
            continue
        m = json.load(open(os.path.join(d, "manifest.json")))
        s = json.load(open(os.path.join(d, "status.json"))) if os.path.exists(os.path.join(d, "status.json")) else {}
        out.append({"run_id": name, "experiment_id": m.get("experiment_id"), "created_at": m.get("created_at"),
                    "llm_mode": m["llm"]["mode"], "is_mock": m.get("is_mock"), "split": m["dataset"]["split"],
                    "claims": len(m["dataset"]["claim_ids"]), "approaches": m["approaches"], "state": s.get("state")})
    return out


def load_run(run_id: str, runs_dir: str = RUNS_DIR) -> dict:
    d = os.path.join(runs_dir, run_id)
    preds = [json.loads(line) for line in open(os.path.join(d, "predictions.jsonl")) if line.strip()] \
        if os.path.exists(os.path.join(d, "predictions.jsonl")) else []
    return {"run_dir": d, "manifest": json.load(open(os.path.join(d, "manifest.json"))),
            "status": json.load(open(os.path.join(d, "status.json"))), "predictions": preds}


def load_trace(run: dict, prediction: dict) -> dict:
    return json.load(open(os.path.join(run["run_dir"], prediction["trace_path"])))
