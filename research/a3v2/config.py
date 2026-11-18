"""A3 v2 configuration. engine/config.py is not edited (its defaults feed
v1 config hashes); v2 configs are merged here from the same pieces plus the
v2 sections, frozen and hashed the same way."""

import copy
import json
import os

from engine import RESEARCH_ROOT
from engine.config import APPROACH_KINDS, DEFAULTS, KIND_SWITCHES, _freeze, _merge, fairness_problems, thaw

from . import (A3V2_VERSION, A3V21_VERSION, A3V211_VERSION, A3V22_VERSION, GRAPH_VERSION, GUARD_VERSION, GUARD_VERSION_V02, GUARD_VERSION_V03, KIND, REVIEW_PROMPT_VERSION,
               REVIEW_PROMPT_VERSION_V21, REVIEW_PROMPT_VERSION_V211)

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
    versions = {"a3v2": A3V2_VERSION, "review_prompts": REVIEW_PROMPT_VERSION, "guard": GUARD_VERSION, "graph": GRAPH_VERSION}
    if (merged.get("periods") or {}).get("enabled"):
        from .periods import VERSIONS
        pv = (merged["periods"].get("version") or "1.0")
        if pv not in VERSIONS:
            raise ValueError(f"{approach['name']}: unknown periods version {pv!r}")
        versions.update({"a3v2": A3V21_VERSION if pv == "1.0" else A3V211_VERSION,
                         "review_prompts": REVIEW_PROMPT_VERSION_V21 if pv == "1.0" else REVIEW_PROMPT_VERSION_V211,
                         "periods": VERSIONS[pv]})
    gv = merged["guard"].get("version")
    if gv is not None:
        if gv not in ("0.1", "0.2", "0.3"):
            raise ValueError(f"{approach['name']}: unknown guard version {gv!r}")
        versions["guard"] = {"0.1": GUARD_VERSION, "0.2": GUARD_VERSION_V02, "0.3": GUARD_VERSION_V03}[gv]
    dname = (merged.get("decidability") or {}).get("name")
    if dname not in ("not_assessed", "llm_0.1"):
        raise ValueError(f"{approach['name']}: unknown decidability {dname!r}")
    if merged.get("quote_check") not in (None, "1.1"):
        raise ValueError(f"{approach['name']}: unknown quote_check {merged.get('quote_check')!r}")
    if dname == "llm_0.1":
        from .decidability import DECIDABILITY_PROMPT_VERSION, DECIDABILITY_VERSION
        d = merged["decidability"]
        if d.get("downgrade") not in (None, False, True, "supported") or not isinstance(d.get("scope_gate", False), bool):
            raise ValueError(f"{approach['name']}: decidability.downgrade must be false / true / 'supported', scope_gate a boolean")
        if not merged["guard"]["enabled"]:
            raise ValueError(f"{approach['name']}: the decidability gate runs inside the reconciliation guard")
        versions.update({"a3v2": A3V22_VERSION, "decidability": DECIDABILITY_VERSION, "decidability_prompt": DECIDABILITY_PROMPT_VERSION})
    if merged.get("quote_check"):
        from .checks import QUOTE_CHECK_V11
        versions["quote_check"] = QUOTE_CHECK_V11
    if merged.get("contribution") not in (None, "0.1b"):
        raise ValueError(f"{approach['name']}: unknown contribution {merged.get('contribution')!r}")
    if merged.get("contribution"):
        if (merged.get("decidability") or {}).get("name") != "llm_0.1":
            raise ValueError(f"{approach['name']}: the contribution test needs the decidability record")
        from .contribution import CONTRIBUTION_RULES_V01B, EXTRACTION_PROMPT_VERSION
        versions.update({"contribution_rules": CONTRIBUTION_RULES_V01B, "contribution_prompt": EXTRACTION_PROMPT_VERSION})
    if merged.get("coverage") not in (None, "0.1"):
        raise ValueError(f"{approach['name']}: unknown coverage {merged.get('coverage')!r}")
    if merged.get("coverage"):
        if not merged["guard"]["enabled"]:
            raise ValueError(f"{approach['name']}: the coverage rule runs inside the reconciliation guard")
        from .numeric_checks import COVERAGE_VERSION
        versions["coverage"] = COVERAGE_VERSION
    if merged.get("numeric_checks") not in (None, "0.1"):
        raise ValueError(f"{approach['name']}: unknown numeric_checks {merged.get('numeric_checks')!r}")
    if merged.get("numeric_checks"):
        if not merged["guard"]["enabled"]:
            raise ValueError(f"{approach['name']}: numeric_checks run inside the reconciliation guard")
        from .numeric_checks import NUMERIC_CHECKS_VERSION
        versions["numeric_checks"] = NUMERIC_CHECKS_VERSION
    merged.update({"name": approach["name"], "kind": KIND, "description": approach.get("description", ""), "versions": versions})
    return _freeze(merged)


# keys that may differ between an arm and the arm it replays: the guard runs
# after every LLM call, so a replay makes the same requests
REPLAY_FREE_KEYS = ("name", "description", "guard", "replay_of")


def baseline_config(common: dict, approach: dict) -> dict:
    """A v1 approach (e.g. A2) built exactly as engine.config.load_config
    builds it, so its requests -- and their cache keys -- are the same."""
    from agent_config import MODEL
    merged = _merge(_merge(_merge(DEFAULTS, common), KIND_SWITCHES[approach["kind"]]), approach.get("overrides") or {})
    merged["llm"]["model"] = merged["llm"]["model"] or MODEL
    merged.update({"name": approach["name"], "kind": approach["kind"], "description": approach.get("description", "")})
    return _freeze(merged)


def _preregistration_problem(raw: dict) -> str | None:
    """A gold-split config must carry {"preregistration": {"path", "sha256"}} naming a plan file marked LOCKED
    whose current sha256 matches; editing the plan after locking breaks the match."""
    from engine.datasets import file_sha256
    pre = raw.get("preregistration") or {}
    if not pre.get("path") or not pre.get("sha256"):
        return "no preregistration path / sha256"
    path = os.path.join(RESEARCH_ROOT, pre["path"])
    if not os.path.exists(path):
        return f"{pre['path']} not found"
    if file_sha256(path) != pre["sha256"]:
        return f"{pre['path']} changed since it was locked"
    if "STATUS: LOCKED" not in open(path, encoding="utf-8").read():
        return f"{pre['path']} is not marked 'STATUS: LOCKED'"
    return None


def _replay_view(key, value):
    """A replay may run another guard version, so the guard entry of `versions` is free like `guard` itself."""
    v = thaw(value)
    return {k: x for k, x in v.items() if k != "guard"} if key == "versions" and isinstance(v, dict) else v


def load_v2_config(path_or_dict) -> dict:
    """A v2 experiment: A3 v2 arms plus, optionally, v1 baselines (an
    approach with a v1 `kind`). An arm with `replay_of` must equal the arm it
    names except for the guard; the runner answers it from the response cache
    only, so it can never make a paid call."""
    if isinstance(path_or_dict, str):
        path = path_or_dict if os.path.isabs(path_or_dict) else os.path.join(RESEARCH_ROOT, path_or_dict)
        with open(path) as f:
            raw = json.load(f)
        source = os.path.relpath(path, RESEARCH_ROOT)
    else:
        raw, source = copy.deepcopy(path_or_dict), None
    if raw.get("dataset", {}).get("split") != "development":
        prereg_problem = _preregistration_problem(raw)
        if prereg_problem:
            raise ValueError("A3 v2 is in development: configs may only target the development split, unless they "
                             f"name a locked preregistration ({prereg_problem})")
    from agent_config import MODEL
    common = _merge(DEFAULTS, raw.get("common") or {})
    common["llm"]["model"] = common["llm"]["model"] or MODEL
    approaches = {}
    for a in raw["approaches"]:
        if a["name"] in approaches:
            raise ValueError(f"duplicate approach name {a['name']}")
        if a.get("kind") in APPROACH_KINDS:
            approaches[a["name"]] = baseline_config(raw.get("common") or {}, a)
        elif a.get("kind", KIND) == KIND:
            approaches[a["name"]] = approach_config(raw.get("common") or {}, a)
            if a.get("replay_of"):
                approaches[a["name"]] = _freeze({**thaw(approaches[a["name"]]), "replay_of": a["replay_of"]})
        else:
            raise ValueError(f"approach {a.get('name')}: unknown kind {a.get('kind')!r}")
    order = list(approaches)
    for name, a in approaches.items():
        target = a.get("replay_of")
        if not target:
            continue
        if target not in approaches or approaches[target].get("replay_of") or approaches[target]["kind"] != KIND:
            raise ValueError(f"{name}: replay_of must name a non-replay A3 v2 arm of this config")
        if order.index(target) > order.index(name):
            raise ValueError(f"{name}: the arm it replays ({target}) must run first")
        diff = sorted(k for k in set(a) | set(approaches[target]) if k not in REPLAY_FREE_KEYS
                      and _replay_view(k, a.get(k)) != _replay_view(k, approaches[target].get(k)))
        if diff:
            raise ValueError(f"{name}: differs from {target} in {diff}; a replay may differ only in the guard")
    cfg = {"experiment_id": raw["experiment_id"], "description": raw.get("description", ""), "dataset": raw["dataset"],
           "common": _freeze(common), "approaches": approaches, "comparisons": raw.get("comparisons") or [], "source_path": source,
           "api_retry": raw.get("api_retry")}  # run-level transport setting (engine.llm); not part of any approach hash
    problems = fairness_problems(cfg)
    if problems:
        raise ValueError("config breaks the fair-comparison rules: " + "; ".join(problems))
    cfg["fairness_problems"] = problems
    return cfg
