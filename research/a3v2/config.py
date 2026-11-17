"""A3 v2 configuration. engine/config.py is not edited (its defaults feed
v1 config hashes); v2 configs are merged here from the same pieces plus the
v2 sections, frozen and hashed the same way."""

import copy
import json
import os

from engine import RESEARCH_ROOT
from engine.config import DEFAULTS, KIND_SWITCHES, _freeze, _merge

from . import A3V2_VERSION, GRAPH_VERSION, GUARD_VERSION, KIND, REVIEW_PROMPT_VERSION

V2_DEFAULTS = {
    "review": {"enabled": True, "max_output_tokens": 3000, "passage_chars": 1200, "allow_partial_period": False},
    "guard": {"enabled": True},
    "analyzer": {"name": "default"},
    "decidability": {"name": "not_assessed"},
}


def approach_config(common: dict, approach: dict) -> dict:
    merged = _merge(_merge(_merge(_merge(DEFAULTS, common), KIND_SWITCHES["contradiction_aware"]), V2_DEFAULTS),
                    approach.get("overrides") or {})
    if merged["guard"]["enabled"] and not merged["review"]["enabled"]:
        raise ValueError(f"{approach['name']}: the reconciliation guard needs the evidence review")
    from agent_config import MODEL
    merged["llm"]["model"] = merged["llm"]["model"] or MODEL
    merged.update({"name": approach["name"], "kind": KIND, "description": approach.get("description", ""),
                   "versions": {"a3v2": A3V2_VERSION, "review_prompts": REVIEW_PROMPT_VERSION, "guard": GUARD_VERSION,
                                "graph": GRAPH_VERSION}})
    return _freeze(merged)


def load_v2_config(path_or_dict) -> dict:
    if isinstance(path_or_dict, str):
        path = path_or_dict if os.path.isabs(path_or_dict) else os.path.join(RESEARCH_ROOT, path_or_dict)
        with open(path) as f:
            raw = json.load(f)
    else:
        raw = copy.deepcopy(path_or_dict)
    if raw.get("dataset", {}).get("split") != "development":
        raise ValueError("A3 v2 is in development: configs may only target the development split")
    approaches = {a["name"]: approach_config(raw.get("common") or {}, a) for a in raw["approaches"]}
    return {"experiment_id": raw["experiment_id"], "description": raw.get("description", ""), "dataset": raw["dataset"],
            "approaches": approaches}
