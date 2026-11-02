"""Paid-call gate, response cache, budget, resumable immutable runs and
result serialization."""
import json
import os
import stat

import pytest

from engine.llm import (BudgetExceeded, CacheMiss, CachedLLM, PaidCallNotApproved, PaidRunApproval, Pricing, ScriptedLLM,
                        approve_paid_run)
from engine.runner import RunLocked, load_run, plan_run, run_experiment, select_claims, verify_run_integrity

VERDICT = {"label": "INSUFFICIENT_EVIDENCE", "claim_type": "interpretive", "numeric_assertions": [], "supporting_evidence": [],
           "contradicting_evidence": [], "reasoning_summary": "r"}


class FakeAPI:
    """Stands in for AnthropicClient: counts 'paid' calls, never touches the network."""
    version = "fake"

    def __init__(self):
        self.calls = 0

    def create(self, system, messages, tools, max_tokens, tool_choice=None):
        self.calls += 1
        return ScriptedLLM({tools[0]["name"]: VERDICT}).create(system, messages, tools, max_tokens, tool_choice)


def test_offline_mode_never_calls_api(tmp_path):
    api = FakeAPI()
    llm = CachedLLM(mode="offline", cache_dir=str(tmp_path), inner=api)
    with pytest.raises(CacheMiss):
        llm.create("s", [{"role": "user", "content": "x"}], [{"name": "t"}], 10)
    assert api.calls == 0


def test_live_mode_requires_approval():
    with pytest.raises(PaidCallNotApproved):
        CachedLLM(mode="live")


def test_approval_needs_exact_phrase(main_cfg):
    claims, _ = select_claims(main_cfg, claim_ids=["DEV-AAPL-01"])
    plan = plan_run(main_cfg, claims)
    assert plan["max_llm_calls"] == 1 + 1 + 3 + 3 and plan["max_cost_usd"] > 0
    for wrong in ("", "yes", plan["confirmation_phrase"].replace("$", "")):
        with pytest.raises(PaidCallNotApproved):
            approve_paid_run(plan, wrong)
    a = approve_paid_run(plan, plan["confirmation_phrase"])
    assert a.max_calls == plan["max_llm_calls"] and a.max_cost_usd == plan["max_cost_usd"]


def test_cache_prevents_repeat_paid_calls_and_budget_is_enforced(tmp_path):
    api = FakeAPI()
    approval = PaidRunApproval(max_cost_usd=1.0, max_calls=1, phrase="test")
    llm = CachedLLM(mode="live", cache_dir=str(tmp_path), inner=api, approval=approval)
    tools = [{"name": "submit_verdict"}]
    llm.create("s", [{"role": "user", "content": "a"}], tools, 100)
    again = llm.create("s", [{"role": "user", "content": "a"}], tools, 100)
    assert api.calls == 1 and again["_source"] == "cache"
    with pytest.raises(BudgetExceeded):
        llm.create("s", [{"role": "user", "content": "b"}], tools, 100)
    offline = CachedLLM(mode="offline", cache_dir=str(tmp_path))
    assert offline.create("s", [{"role": "user", "content": "a"}], tools, 100)["_source"] == "cache"


def test_cost_cap_blocks_expensive_call(tmp_path):
    llm = CachedLLM(mode="live", cache_dir=str(tmp_path), inner=FakeAPI(), approval=PaidRunApproval(0.0001, 10, "t"),
                    pricing=Pricing(3.0, 15.0, "t"))
    with pytest.raises(BudgetExceeded, match="exceed"):
        llm.create("s", [{"role": "user", "content": "a"}], [{"name": "submit_verdict"}], 2000)


def _run(cfg, tmp_path, ids, **kw):
    claims, info = select_claims(cfg, claim_ids=ids)
    return run_experiment(cfg, claims, info, runs_dir=str(tmp_path), progress=lambda s: None, **kw), claims, info


def test_mock_run_is_complete_locked_and_serializable(main_cfg, tmp_path):
    run_id, claims, _ = _run(main_cfg, tmp_path, ["DEV-AAPL-01", "DEV-MSFT-04"], llm_mode="mock")
    assert run_id.startswith("MOCK-")
    run = load_run(run_id, str(tmp_path))
    assert run["status"]["state"] == "complete" and len(run["predictions"]) == 2 * 4
    assert run["manifest"]["is_mock"] and run["manifest"]["llm"]["mode"] == "mock"
    for key in ("approach_config_hashes", "versions", "code", "dataset", "xbrl_facts_sha256"):
        assert run["manifest"][key]
    assert run["manifest"]["versions"]["prompt_version"] and run["manifest"]["code"]["files_sha256"]
    assert verify_run_integrity(run["run_dir"]) == []
    pred_file = os.path.join(run["run_dir"], "predictions.jsonl")
    assert not os.stat(pred_file).st_mode & stat.S_IWUSR  # read-only
    p = run["predictions"][0]
    trace = json.load(open(os.path.join(run["run_dir"], p["trace_path"])))
    assert trace["trace_id"] == p["investigation_trace_id"] and p["is_mock"]
    with pytest.raises(RunLocked):
        run_experiment(main_cfg, claims, run["manifest"]["dataset"], llm_mode="mock", resume_run_id=run_id,
                       runs_dir=str(tmp_path), progress=lambda s: None)


def test_tampering_is_detected(main_cfg, tmp_path):
    run_id, _, _ = _run(main_cfg, tmp_path, ["DEV-AAPL-01"], llm_mode="mock", approaches=["A1_conventional_rag"])
    d = os.path.join(str(tmp_path), run_id)
    path = os.path.join(d, "predictions.jsonl")
    os.chmod(path, 0o644)
    with open(path, "a") as f:
        f.write("{}\n")
    assert verify_run_integrity(d) == ["predictions.jsonl"]


def test_offline_run_with_missing_cache_stays_incomplete_then_resumes(main_cfg, tmp_path):
    cache = str(tmp_path / "cache")
    ids = ["DEV-AAPL-01", "DEV-AMZN-04"]
    offline = CachedLLM(mode="offline", cache_dir=cache)
    run_id, claims, info = _run(main_cfg, tmp_path / "runs", ids, llm_mode="offline", llm=offline, approaches=["A1_conventional_rag"])
    run = load_run(run_id, str(tmp_path / "runs"))
    assert run["status"]["state"] == "incomplete" and len(run["status"]["cache_misses"]) == 2 and not run["predictions"]

    api = FakeAPI()
    live = CachedLLM(mode="live", cache_dir=cache, inner=api, approval=PaidRunApproval(1.0, 1, "t"))
    with pytest.raises(BudgetExceeded):  # second claim exceeds the 1-call approval: partial results kept
        run_experiment(main_cfg, claims, info, llm_mode="live", llm=live, approaches=["A1_conventional_rag"], resume_run_id=run_id,
                       runs_dir=str(tmp_path / "runs"), progress=lambda s: None)
    run = load_run(run_id, str(tmp_path / "runs"))
    assert run["status"]["state"] == "incomplete" and len(run["predictions"]) == 1 and api.calls == 1

    live2 = CachedLLM(mode="live", cache_dir=cache, inner=api, approval=PaidRunApproval(1.0, 1, "t"))
    run_experiment(main_cfg, claims, info, llm_mode="live", llm=live2, approaches=["A1_conventional_rag"], resume_run_id=run_id,
                   runs_dir=str(tmp_path / "runs"), progress=lambda s: None)
    run = load_run(run_id, str(tmp_path / "runs"))
    assert run["status"]["state"] == "complete" and len(run["predictions"]) == 2
    assert api.calls == 2  # the first claim was not re-run or re-paid
    assert len({p["claim_id"] for p in run["predictions"]}) == 2


def test_resume_refuses_changed_config(main_cfg, tmp_path):
    from engine.config import load_config
    offline = CachedLLM(mode="offline", cache_dir=str(tmp_path / "c"))
    run_id, claims, info = _run(main_cfg, tmp_path, ["DEV-AAPL-01"], llm_mode="offline", llm=offline, approaches=["A1_conventional_rag"])
    raw = json.load(open("configs/main_comparison.json"))
    raw["common"]["retrieval"]["top_k"] = 3
    changed = load_config(raw)
    with pytest.raises(ValueError, match="config changed"):
        run_experiment(changed, claims, info, llm_mode="offline", llm=offline, approaches=["A1_conventional_rag"],
                       resume_run_id=run_id, runs_dir=str(tmp_path), progress=lambda s: None)
