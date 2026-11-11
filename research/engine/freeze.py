"""Freeze record for a finished experiment: checksums of the run
directories, the configuration, prompts, model settings, datasets,
reference and adjudication files, the cached model responses the run
replays from and the result tables / figures, plus the headline scores
recomputed from the frozen predictions. Read-only with respect to every
input; `diff_freeze` compares a stored record with a fresh one."""

import glob
import json
import os
from datetime import datetime, timezone

from . import RESEARCH_ROOT
from .datasets import file_sha256
from .runner import RUNS_DIR, git_state, load_run, verify_run_integrity

FREEZE_DIR = os.path.join(RESEARCH_ROOT, "results", "freeze")
DATASET_FILES = ("datasets/gold_claims.jsonl", "datasets/development_cases.jsonl", "datasets/corpus_manifest.json",
                 "datasets/workbooks/Final_Gold_v3_approved.xlsx", "engine/prompts.py", "engine/reference.py")
MAIN_COMPARISONS = (("A2_rag_numeric", "A3_contradiction_aware"), ("A1_conventional_rag", "A2_rag_numeric"))
# keys that legitimately differ between two freezes of the same run
VOLATILE = ("frozen_at", "git")


def _rel(path: str) -> str:
    return os.path.relpath(path, RESEARCH_ROOT)


def _hashes(paths) -> dict[str, str | None]:
    return {_rel(p): file_sha256(p) for p in sorted(paths)}


def freeze_path(run_id: str) -> str:
    return os.path.join(FREEZE_DIR, f"{run_id}.json")


def cache_entries(run: dict, cache_dir: str) -> dict:
    """Request keys a run replays from, with the sha256 of each cached
    response (None = missing: the run could not be replayed offline)."""
    keys = set()
    for path in glob.glob(os.path.join(run["run_dir"], "traces", "*", "*.json")):
        with open(path) as f:
            keys.update(c["request_key"] for c in json.load(f).get("llm_calls") or [] if c.get("request_key"))
    return {k: file_sha256(os.path.join(cache_dir, k[:2], f"{k}.json")) for k in sorted(keys)}


def build_freeze(run_id: str, source_run_ids: list[str] = (), runs_dir: str = RUNS_DIR,
                 cache_dir: str | None = None, n_boot: int = 5000) -> dict:
    from .error_analysis import scoring_summary
    from .notebook import load_gold_labels
    from .prompts import prompt_manifest
    from .reference import alternative_variants, load_alternatives, load_reference
    cache_dir = cache_dir or os.path.join(RESEARCH_ROOT, "results", "llm_cache")
    run = load_run(run_id, runs_dir)
    m = run["manifest"]
    runs = {}
    for rid in [run_id, *source_run_ids]:
        d = os.path.join(runs_dir, rid)
        runs[rid] = {"integrity_problems": verify_run_integrity(d),
                     "SHA256SUMS": file_sha256(os.path.join(d, "SHA256SUMS")),
                     "manifest": file_sha256(os.path.join(d, "manifest.json")),
                     "predictions": file_sha256(os.path.join(d, "predictions.jsonl")),
                     "status": json.load(open(os.path.join(d, "status.json")))}
    prompts_now = prompt_manifest()
    adj_dir = os.path.join(RESEARCH_ROOT, "datasets", "adjudication")
    variants = alternative_variants(run_id)
    provenance = {}
    for v in variants:
        path = os.path.join(adj_dir, f"insufficient_alternatives__{run_id}__{v}.jsonl")
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        books = sorted({r.get("source_workbook") for r in rows if r.get("source_workbook")})
        provenance[v] = {"file": _rel(path), "sha256": file_sha256(path), "cases": len(rows),
                         "acceptable": sum(r["decision"] == "ACCEPTABLE" for r in rows),
                         "adjudicators": sorted({r.get("adjudicator") for r in rows}),
                         "source_workbooks": {b: file_sha256(os.path.join(adj_dir, b)) for b in books}}
    scorings = {"strict": None, **{v: load_alternatives(run_id, v) for v in variants}}
    cache = cache_entries(run, cache_dir)
    results = glob.glob(os.path.join(RESEARCH_ROOT, "results", "metrics", f"{run_id}__*")) + \
        glob.glob(os.path.join(RESEARCH_ROOT, "results", "figures", f"*{run_id}*"))
    return {
        "run_id": run_id, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git": git_state(),
        "runs": runs,
        "model": m["llm"], "versions": m["versions"],
        "prompts": {"recorded": {k: m["versions"].get(k) for k in prompts_now},
                    "current_code": prompts_now,
                    "drift": sorted(k for k, v in prompts_now.items() if m["versions"].get(k) != v)},
        "config": {"path": m.get("config_path"), "sha256": file_sha256(os.path.join(RESEARCH_ROOT, m.get("config_path") or "")),
                   "approach_config_hashes": m.get("approach_config_hashes")},
        "dataset": {"split": m["dataset"]["split"], "claims_sha256_recorded": m["dataset"].get("sha256"),
                    "claims": len(m["dataset"].get("claim_ids") or [])},
        "files": _hashes(os.path.join(RESEARCH_ROOT, p) for p in DATASET_FILES),
        "reference": {k: load_reference()["provenance"].get(k) for k in ("dataset_version", "sheet", "sha256", "label_source")},
        "adjudication": provenance,
        "llm_cache": {"entries": len(cache), "missing": sorted(k for k, v in cache.items() if v is None),
                      "sha256": dict(cache)},
        "results": _hashes(results),
        "scores": scoring_summary(run["predictions"], load_gold_labels(), scorings, list(MAIN_COMPARISONS), n_boot=n_boot),
    }


def _flatten(d, prefix=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _flatten(v, f"{prefix}{k}/")
    else:
        yield prefix.rstrip("/"), d


def diff_freeze(old: dict, new: dict) -> dict[str, list[str]]:
    """`changed` / `removed`: frozen values that differ now (problems).
    `added`: values that did not exist at freeze time (e.g. new analysis
    figures) -- reported, not a problem."""
    a = {k: v for k, v in _flatten(old) if k.split("/")[0] not in VOLATILE}
    b = {k: v for k, v in _flatten(new) if k.split("/")[0] not in VOLATILE}
    return {"changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
            "removed": sorted(a.keys() - b.keys()), "added": sorted(b.keys() - a.keys())}
