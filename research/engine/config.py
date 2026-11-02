"""Experiment configuration: one JSON file per experiment (research/configs).

A config has `common` settings (model, retrieval, budgets, dataset) and a
list of `approaches`, each naming its kind plus overrides. Every approach
receives its own deep-frozen merged config, and its hash is recorded with
every prediction, so (a) one approach cannot change another's settings at
run time and (b) a result can always be tied to the exact settings used.
Fairness checks (`fairness_problems`) refuse configs whose approaches differ
in anything other than the mechanism under study.
"""

import copy
import hashlib
import json
import os
from types import MappingProxyType

from . import RESEARCH_ROOT

APPROACH_KINDS = ("conventional_rag", "financial_verification", "contradiction_aware", "self_reflection")

DEFAULTS = {
    "llm": {"model": None, "temperature": 0, "max_output_tokens": 1500},
    "retrieval": {"top_k": 6, "chunk_chars": 1200, "chunk_overlap": 200,
                  "max_filings_per_form": {"10-K": 1, "10-Q": 2, "8-K": 2}, "passage_chars_in_prompt": 1200},
    "numeric": {"enabled": False, "max_assertions": 6, "override_final_label": True},
    "contradiction": {"enabled": False, "max_hypotheses": 3, "top_k_per_query": 3, "counter_retrieval": True,
                      "counter_numeric_checks": True},
    "reflection": {"enabled": False, "max_items": 3},
    "budget": {"max_llm_calls_per_claim": 3, "max_input_tokens_per_claim": 60000, "max_retrieval_queries_per_claim": 4},
}

# What each approach kind switches on; anything else comes from `common`.
KIND_SWITCHES = {
    "conventional_rag": {"numeric": {"enabled": False}, "contradiction": {"enabled": False}, "reflection": {"enabled": False}},
    "financial_verification": {"numeric": {"enabled": True}, "contradiction": {"enabled": False}, "reflection": {"enabled": False}},
    "contradiction_aware": {"numeric": {"enabled": True}, "contradiction": {"enabled": True}, "reflection": {"enabled": False}},
    "self_reflection": {"numeric": {"enabled": True}, "contradiction": {"enabled": False}, "reflection": {"enabled": True}},
}
# Settings that must be identical across approaches in one experiment.
SHARED_KEYS = ("llm", "retrieval", "budget")


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def _freeze(x):
    if isinstance(x, dict):
        return MappingProxyType({k: _freeze(v) for k, v in x.items()})
    if isinstance(x, list):
        return tuple(_freeze(v) for v in x)
    return x


def thaw(x):
    if isinstance(x, (dict, MappingProxyType)):
        return {k: thaw(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [thaw(v) for v in x]
    return x


def config_hash(cfg) -> str:
    return hashlib.sha256(json.dumps(thaw(cfg), sort_keys=True).encode()).hexdigest()[:16]


def load_config(path_or_dict) -> dict:
    if isinstance(path_or_dict, str):
        path = path_or_dict if os.path.isabs(path_or_dict) else os.path.join(RESEARCH_ROOT, path_or_dict)
        with open(path) as f:
            raw = json.load(f)
        raw["_path"] = os.path.relpath(path, RESEARCH_ROOT)
    else:
        raw = copy.deepcopy(path_or_dict)
    if "experiment_id" not in raw or not raw.get("approaches"):
        raise ValueError("config needs experiment_id and approaches")
    from agent_config import MODEL
    common = _merge(DEFAULTS, raw.get("common") or {})
    common["llm"]["model"] = common["llm"]["model"] or MODEL
    approaches = {}
    for a in raw["approaches"]:
        if a.get("kind") not in APPROACH_KINDS:
            raise ValueError(f"approach {a.get('name')}: kind must be one of {APPROACH_KINDS}")
        if a["name"] in approaches:
            raise ValueError(f"duplicate approach name {a['name']}")
        # kind switches first, so an explicit override (e.g. the ablation's
        # contradiction.enabled=false) wins and is recorded in the config hash
        merged = _merge(_merge(common, KIND_SWITCHES[a["kind"]]), a.get("overrides") or {})
        merged.update({"name": a["name"], "kind": a["kind"], "description": a.get("description", "")})
        approaches[a["name"]] = _freeze(merged)
    cfg = {"experiment_id": raw["experiment_id"], "description": raw.get("description", ""),
           "dataset": raw.get("dataset") or {"split": "development"}, "common": _freeze(common),
           "approaches": approaches, "comparisons": raw.get("comparisons") or [], "source_path": raw.get("_path")}
    problems = fairness_problems(cfg)
    if problems and not raw.get("allow_unfair"):
        raise ValueError("config breaks the fair-comparison rules: " + "; ".join(problems))
    cfg["fairness_problems"] = problems
    return cfg


def fairness_problems(cfg: dict) -> list[str]:
    """Approaches in one experiment must share model, retrieval and budget,
    and the main pair must differ only by the contradiction stage."""
    problems = []
    items = list(cfg["approaches"].values())
    for key in SHARED_KEYS:
        values = {json.dumps(thaw(a[key]), sort_keys=True) for a in items}
        if len(values) > 1:
            problems.append(f"approaches differ in shared setting '{key}'")
    contradiction = [a for a in items if a["kind"] == "contradiction_aware" and a["contradiction"]["enabled"]]
    for a in contradiction:
        if a["budget"]["max_retrieval_queries_per_claim"] < 1 + a["contradiction"]["max_hypotheses"]:
            problems.append(f"{a['name']}: retrieval budget smaller than 1 + max_hypotheses")
    for a in items:
        if a["kind"] != "self_reflection":
            continue
        for b in contradiction:
            if a["reflection"]["max_items"] != b["contradiction"]["max_hypotheses"]:
                problems.append(f"{a['name']}: reflection max_items must equal {b['name']} max_hypotheses (same number of second looks)")
    return problems
