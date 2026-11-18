"""Pre-flight checks of the A3 v2 experiment runner on dev-v0.2, with no paid
call: a fake API (ScriptedLLM behind CachedLLM in live mode, temp cache, temp
ledger, temp runs dir) and mock-mode graph runs. Covers the runner wiring
(A2 -> A3v2_R -> cache-only A3v2_RG), the aggregate cost ledger, resume,
failures, and the evidence scenarios the guard must handle."""
import json
import multiprocessing
import os

import pytest
import requests

from a3v2.checks import period_status
from a3v2.config import load_v2_config
from a3v2.derived import free_cash_flow
from a3v2.graph import run as run_v2
from engine.corpus import Retriever
from engine.cost_ledger import CostLedger, LedgerExceeded
from engine.llm import BudgetExceeded, CachedLLM, PaidRunApproval, Pricing, ScriptedLLM, request_key
from engine.runner import plan_run, run_experiment, select_claims
from test_a3v2_graph import change_to_contradicted, review_with
from test_approaches import PLAN, verdict

CFG_PATH = "configs/a3v2_dev_v0_2.json"
IDS = ["DEV-ADBE-04", "DEV-CAT-12", "DEV-PG-05"]
APPROVAL = PaidRunApproval(max_cost_usd=50.0, max_calls=1000, phrase="test")


@pytest.fixture(scope="module")
def cfg():
    return load_v2_config(CFG_PATH)


@pytest.fixture
def claims(cfg):
    return select_claims(cfg, claim_ids=IDS)


def responses(review=None, reconcile=None):
    return {"submit_verdict": verdict(ctype="interpretive"), "submit_contradiction_plan": PLAN,
            "submit_evidence_review": review or review_with("RELATED_NOT_DECIDING"),
            "submit_reconciliation": reconcile or change_to_contradicted}


class FlakyAPI(ScriptedLLM):
    """Fake API: raises the queued errors first, then answers like ScriptedLLM."""

    def __init__(self, resp, errors=()):
        super().__init__(resp)
        self.errors, self.attempts = list(errors), 0

    def create(self, *a, **k):
        self.attempts += 1
        if self.errors:
            raise self.errors.pop(0)
        return super().create(*a, **k)


def live(tmp_path, api, ledger=None, approval=APPROVAL):
    return CachedLLM(mode="live", model="claude-sonnet-4-5-20250929", temperature=0, cache_dir=str(tmp_path / "cache"),
                     inner=api, approval=approval, ledger=ledger)


def preds(runs_dir, run_id):
    return [json.loads(x) for x in open(os.path.join(runs_dir, run_id, "predictions.jsonl"))]


# ----------------------------------------------------------- runner wiring

def test_config_loads_baseline_and_replay(cfg):
    a = cfg["approaches"]
    assert list(a) == ["A2_rag_numeric", "A3v2_R", "A3v2_RG"]
    assert a["A3v2_RG"]["replay_of"] == "A3v2_R" and a["A3v2_RG"]["guard"]["enabled"] and not a["A3v2_R"]["guard"]["enabled"]
    assert {json.dumps(dict(x["llm"]), sort_keys=True) for x in a.values()} == {
        json.dumps({"model": "claude-sonnet-4-5-20250929", "temperature": 0, "max_output_tokens": 1500}, sort_keys=True)}
    with pytest.raises(ValueError, match="may differ only in the guard"):
        raw = json.load(open(CFG_PATH))
        raw["approaches"][2]["overrides"]["contradiction"]["max_hypotheses"] = 2
        load_v2_config(raw)


def test_plan_counts_each_paid_request_once(cfg, claims):
    p = plan_run(cfg, claims[0], ledger_remaining_usd=15.0)
    by = {r["approach"]: r for r in p["approaches"]}
    assert by["A2_rag_numeric"]["paid_calls_new"] == 3 and by["A3v2_R"]["paid_calls_new"] == 9 and by["A3v2_RG"]["paid_calls_new"] == 0
    assert p["max_llm_calls"] == 12 and p["max_cost_usd"] <= 15.0


def test_full_run_rg_is_cache_only_and_costs_are_ledgered(cfg, claims, tmp_path):
    api = ScriptedLLM(responses())
    ledger = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "ledger"))
    runs = str(tmp_path / "runs")
    rid = run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api, ledger), ledger=ledger,
                         runs_dir=runs, progress=lambda *_: None)
    rows = preds(runs, rid)
    assert len(rows) == 9 and all(r["stop_reason"] == "COMPLETED" for r in rows)
    assert {a: sorted(r["claim_id"] for r in rows if r["approach"] == a) for a in cfg["approaches"]} == {a: sorted(IDS) for a in cfg["approaches"]}
    # 3 claims x (1 shared initial + hypotheses + review + reconcile) reach the API; RG none
    assert len(api.requests) == 12
    st = json.load(open(os.path.join(runs, rid, "status.json")))
    assert st["state"] == "complete" and st["llm_stats"]["live_calls"] == 12
    assert st["replay_llm_stats"]["live_calls"] == 0 and st["replay_llm_stats"]["cache_hits"] == 12
    led = ledger.status()
    assert led["paid_calls"] == 12 and led["open_reservations"] == [] and led["settled_usd"] == pytest.approx(12 * Pricing().cost(1000, 200))
    # R and RG start from A2's label; RG differs only by the guard
    by = {(r["approach"], r["claim_id"]): r for r in rows}
    for c in IDS:
        assert by[("A3v2_R", c)]["initial_label"] == by[("A3v2_RG", c)]["initial_label"] == by[("A2_rag_numeric", c)]["predicted_label"]
    m = json.load(open(os.path.join(runs, rid, "manifest.json")))
    assert m["replays"] == {"A3v2_RG": "A3v2_R"} and m["cost_ledger"]["cap_usd"] == 15.0
    assert m["dataset"]["path"] == "datasets/development_cases_dev-v0.2.jsonl" and len(m["dataset"]["sha256"]) == 64
    assert set(m["approach_config_hashes"]) == set(cfg["approaches"]) and m["llm"]["model"] == "claude-sonnet-4-5-20250929"
    assert all(os.path.isdir(os.path.join(runs, rid, "traces", a)) for a in cfg["approaches"])


def test_replay_arm_never_pays_even_without_cache(cfg, claims, tmp_path):
    api = ScriptedLLM(responses())
    runs = str(tmp_path / "runs")
    rid = run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api), approaches=["A3v2_RG"],
                         runs_dir=runs, progress=lambda *_: None)
    st = json.load(open(os.path.join(runs, rid, "status.json")))
    assert api.requests == [] and st["state"] == "incomplete" and len(st["cache_misses"]) == 3


def test_interrupt_and_resume_do_not_pay_twice_or_reset_the_ledger(cfg, claims, tmp_path):
    ledger = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "ledger"))
    runs = str(tmp_path / "runs")
    api1 = ScriptedLLM(responses())
    small = PaidRunApproval(max_cost_usd=Pricing().cost(30000, 1500) * 5, max_calls=5, phrase="t")
    with pytest.raises(BudgetExceeded):
        run_experiment(cfg, *claims, llm_mode="live", approval=small, llm=live(tmp_path, api1, ledger, small), ledger=ledger,
                       runs_dir=runs, progress=lambda *_: None)
    rid = sorted(os.listdir(runs))[0]
    assert json.load(open(os.path.join(runs, rid, "status.json")))["state"] == "incomplete"
    first = ledger.status()
    assert first["paid_calls"] == len(api1.requests) == 5 and first["open_reservations"] == []
    api2 = ScriptedLLM(responses())  # a new process: fresh guard, same cache and ledger
    run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api2, ledger), ledger=ledger,
                   resume_run_id=rid, runs_dir=runs, progress=lambda *_: None)
    keys = lambda api: [request_key("claude-sonnet-4-5-20250929", 0, r["system"], r["messages"],
                                    [{"name": t} for t in r["tools"]], r["max_tokens"], r["tool_choice"]) for r in api.requests]
    assert len(api1.requests) + len(api2.requests) == 12 and not set(keys(api1)) & set(keys(api2))
    assert ledger.status()["paid_calls"] == 12  # accumulated, not reset
    assert json.load(open(os.path.join(runs, rid, "status.json")))["state"] == "complete"
    with pytest.raises(ValueError, match="cannot be changed"):
        CostLedger("t", 30.0, ledger_dir=str(tmp_path / "ledger"))


def test_ledger_stops_the_run_before_the_aggregate_cap(cfg, claims, tmp_path):
    ledger = CostLedger("t", 0.05, ledger_dir=str(tmp_path / "ledger"))
    api = ScriptedLLM(responses())
    with pytest.raises(BudgetExceeded, match="ledger t"):
        run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api, ledger), ledger=ledger,
                       runs_dir=str(tmp_path / "runs"), progress=lambda *_: None)
    s = ledger.status()
    assert s["committed_usd"] <= 0.05 and s["paid_calls"] == len(api.requests)


def test_transient_api_errors_are_retried_and_reserved_conservatively(cfg, claims, tmp_path):
    def err(code):
        r = requests.Response()
        r.status_code = code
        return requests.HTTPError(response=r)
    api = FlakyAPI(responses(), errors=[err(529), err(529)])
    ledger = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "ledger"))
    claim = select_claims(cfg, claim_ids=["DEV-PG-05"])
    rid = run_experiment(cfg, *claim, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api, ledger), ledger=ledger,
                         approaches=["A2_rag_numeric"], runs_dir=str(tmp_path / "runs"), progress=lambda *_: None)
    assert api.attempts == 3 and preds(str(tmp_path / "runs"), rid)[0]["stop_reason"] == "COMPLETED"
    s = ledger.status()
    assert s["failed_calls"] == 2 and s["paid_calls"] == 1 and s["failed_reserved_usd"] > 0  # failures stay counted


def test_fatal_billing_error_stops_without_recording_predictions(cfg, claims, tmp_path):
    r = requests.Response()
    r.status_code, r._content = 400, b'{"error": {"message": "Your credit balance is too low"}}'
    api = FlakyAPI(responses(), errors=[requests.HTTPError(response=r)])
    runs = str(tmp_path / "runs")
    with pytest.raises(requests.HTTPError):
        run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api), runs_dir=runs, progress=lambda *_: None)
    rid = os.listdir(runs)[0]
    assert not os.path.exists(os.path.join(runs, rid, "predictions.jsonl")) or preds(runs, rid) == []
    assert json.load(open(os.path.join(runs, rid, "status.json")))["state"] == "incomplete"


def _reserve(args):
    d, n = args
    led, got = CostLedger("shared", ledger_dir=d), 0
    for _ in range(n):
        try:
            led.reserve(1.0, run_id=str(os.getpid()))
            got += 1
        except LedgerExceeded:
            pass
    return got


def test_ledger_is_safe_across_processes_and_counts_calls_in_flight(tmp_path):
    d = str(tmp_path / "ledger")
    CostLedger("shared", 10.0, ledger_dir=d)
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        got = pool.map(_reserve, [(d, 6)] * 4)
    led = CostLedger("shared", ledger_dir=d)
    s = led.status()
    assert sum(got) == 10 and s["open_reserved_usd"] == pytest.approx(10.0) and s["remaining_usd"] == pytest.approx(0)
    # reservations in flight block new calls; a failed call stays counted; a reply that reached the cache is settled
    rid = s["open_reservations"][0]
    led.fail(rid, "timeout")
    assert led.status()["committed_usd"] == pytest.approx(10.0)
    cache = tmp_path / "cache"
    rid2 = led.status()["open_reservations"][0]
    key = "ab" + "0" * 62
    with open(led.path) as f:
        rows = [json.loads(x) for x in f]
    rows = [{**r, "request_key": key} if r.get("id") == rid2 else r for r in rows]
    with open(led.path, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    (cache / "ab").mkdir(parents=True)
    (cache / "ab" / f"{key}.json").write_text(json.dumps({"response": {"usage": {"input_tokens": 1000, "output_tokens": 200}}}))
    assert led.reconcile(str(cache), Pricing()) == [rid2]
    assert led.status()["committed_usd"] == pytest.approx(9.0 + Pricing().cost(1000, 200))


def test_changed_prompt_or_config_is_a_cache_miss_and_resume_is_refused(cfg, claims, tmp_path):
    k = lambda system: request_key("m", 0, system, [{"role": "user", "content": "x"}], [], 100, None)
    assert k("review prompt v1") != k("review prompt v2")
    runs = str(tmp_path / "runs")
    offline = lambda: CachedLLM(mode="offline", model="claude-sonnet-4-5-20250929", temperature=0, cache_dir=str(tmp_path / "empty"))
    rid = run_experiment(cfg, *claims, llm_mode="offline", llm=offline(), approaches=["A2_rag_numeric"], runs_dir=runs,
                         progress=lambda *_: None)
    assert json.load(open(os.path.join(runs, rid, "status.json")))["state"] == "incomplete"  # nothing cached
    raw = json.load(open(CFG_PATH))
    raw["common"]["retrieval"]["top_k"] = 5
    with pytest.raises(ValueError, match="config changed"):
        run_experiment(load_v2_config(raw), *claims, llm_mode="offline", llm=offline(), approaches=["A2_rag_numeric"],
                       resume_run_id=rid, runs_dir=runs, progress=lambda *_: None)


# ------------------------------------------------------- evidence scenarios

def arm(cfg, claim, resp, name):
    llm = CachedLLM(mode="mock", inner=ScriptedLLM(resp), model="claude-sonnet-4-5-20250929")
    pred, trace = run_v2(claim.to_input(), cfg["approaches"][name], llm, "t")
    return pred, llm


def both(cfg, cid, **kw):
    claim = select_claims(cfg, claim_ids=[cid])[0][0]
    return {n: arm(cfg, claim, responses(**kw), n)[0] for n in ("A3v2_R", "A3v2_RG")}


def finding(relation, quote_from=None, quote="", etype="OBSERVED_RESULT", pick=lambda e: True):
    def f(p):
        ev = next(e for e in p["evidence"] if e["kind"] == "filing_passage" and pick(e))
        q = ev["text"][20:90] if quote_from is None else quote
        return {"findings": [{"assertion_id": "A0", "evidence_ids": [ev["evidence_id"]], "relation": relation, "evidence_type": etype,
                              "addresses": "LEVEL", "key_quote": q, "justification": "s"}]}
    return f


def cite_reviewed(label):
    def f(p):
        ev = p["evidence_review"][0] if p.get("evidence_review") else None
        eid = ev["evidence_ids"][0] if ev else p["counter_evidence"][0]["evidence_id"]
        text = next((e["text"] for e in p["counter_evidence"] if e["evidence_id"] == eid), None)
        item = [{"evidence_id": eid, "quote": text[20:90] if text else ""}]
        side = "contradicting_evidence" if label == "CONTRADICTED" else "supporting_evidence"
        return {"assessments": [{"item_id": "H1", "assessment": "CHALLENGE_SUPPORTED", "evidence": item}], "label": label,
                "verdict_changed": True, "change_reason": "s", "supporting_evidence": [], "contradicting_evidence": [], side: item,
                "reasoning_summary": "s"}
    return f


def test_irrelevant_evidence_cannot_carry_a_change():
    cfg = load_v2_config(CFG_PATH)
    out = both(cfg, "DEV-PG-05", review=finding("IRRELEVANT"))
    assert out["A3v2_R"]["predicted_label"] == "CONTRADICTED"          # R follows the reconciliation
    g = out["A3v2_RG"]["contradiction"]["a3v2"]["reconciliation_guard"]
    assert out["A3v2_RG"]["predicted_label"] == "SUPPORTED" and g["outcome"] == "REJECT"


def test_false_contradiction_with_invented_quote_is_downgraded():
    cfg = load_v2_config(CFG_PATH)
    out = both(cfg, "DEV-ADBE-04", review=finding("CONTRADICTS", quote_from="x", quote="cash from operations declined sharply in 2025"))
    g = out["A3v2_RG"]["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["reason_code"] == "INVALID_DECIDING_EVIDENCE:KEY_QUOTE_NOT_IN_EVIDENCE" and out["A3v2_RG"]["predicted_label"] == "SUPPORTED"


def test_management_intention_is_not_a_contradiction():
    cfg = load_v2_config(CFG_PATH)
    out = both(cfg, "DEV-ADBE-04", review=finding("CONTRADICTS", etype="MANAGEMENT_INTENT", pick=lambda e: e["period_status"] == "MATCH"))
    assert out["A3v2_RG"]["contradiction"]["a3v2"]["reconciliation_guard"]["reason_code"].startswith("INVALID_DECIDING_EVIDENCE:NON_RESULT")


def test_genuine_same_period_contradiction_is_accepted():
    cfg = load_v2_config(CFG_PATH)
    pick = lambda e: int(e["evidence_id"][1:]) > 6 and e["period_status"] == "MATCH"
    # a claim with a stated period end; see the WARNING test below for quarter claims without one
    out = both(cfg, "DEV-ADBE-11", review=finding("CONTRADICTS", pick=pick), reconcile=cite_reviewed("CONTRADICTED"))
    g = out["A3v2_RG"]["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["outcome"] == "ACCEPT" and out["A3v2_RG"]["predicted_label"] == "CONTRADICTED"


def test_conflicting_valid_evidence_blocks_a_move_to_supported():
    cfg = load_v2_config(CFG_PATH)

    def review(p):
        evs = [e for e in p["evidence"] if e["kind"] == "filing_passage"][:2]
        return {"findings": [{"assertion_id": "A0", "evidence_ids": [e["evidence_id"]], "relation": rel, "evidence_type": "OBSERVED_RESULT",
                              "addresses": "LEVEL", "key_quote": e["text"][20:90], "justification": "s"}
                             for e, rel in zip(evs, ("CONTRADICTS", "ENTAILS"))]}
    claim = select_claims(cfg, claim_ids=["DEV-INTC-05"])[0][0]
    resp = {**responses(review=review, reconcile=cite_reviewed("SUPPORTED")), "submit_verdict": verdict("CONTRADICTED", ctype="interpretive")}
    pred, _ = arm(cfg, claim, resp, "A3v2_RG")
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["reason_code"] in ("CONFLICTING_DECIDING_EVIDENCE", "NO_CHANGE") and pred["predicted_label"] == "CONTRADICTED"


def test_empty_retrieval_cannot_produce_a_decisive_change(monkeypatch):
    cfg = load_v2_config(CFG_PATH)
    monkeypatch.setattr(Retriever, "search", lambda self, *a, **k: [])
    claim = select_claims(cfg, claim_ids=["DEV-PG-05"])[0][0]
    resp = {**responses(review=lambda p: {"findings": []}),
            "submit_verdict": lambda p: {"label": "INSUFFICIENT_EVIDENCE", "claim_type": "interpretive", "numeric_assertions": [],
                                         "supporting_evidence": [], "contradicting_evidence": [], "reasoning_summary": "no evidence"}}
    pred, llm = arm(cfg, claim, resp, "A3v2_RG")
    review = next((r for r in llm.inner.requests if r["tools"] == ["submit_evidence_review"]), None)
    if review:  # only XBRL facts from the counter numeric check can reach the reviewer
        assert '"kind": "filing_passage"' not in json.dumps(review["messages"])
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    # the v1 guards already undo an uncited change (NO_CHANGE reaches RG); otherwise RG rejects it
    assert g["outcome"] in ("REJECT", "NO_CHANGE") and pred["predicted_label"] == "INSUFFICIENT_EVIDENCE"


def test_reviewer_failure_falls_back_to_a2_label():
    cfg = load_v2_config(CFG_PATH)
    claim = select_claims(cfg, claim_ids=["DEV-PG-05"])[0][0]

    class NoTool(ScriptedLLM):
        def create(self, system, messages, tools, max_tokens, tool_choice=None):
            out = super().create(system, messages, tools, max_tokens, tool_choice)
            if tools[-1]["name"] == "submit_evidence_review":
                out["content"] = [{"type": "text", "text": "no tool call"}]
            return out
    llm = CachedLLM(mode="mock", inner=NoTool(responses()), model="claude-sonnet-4-5-20250929")
    pred, _ = run_v2(claim.to_input(), cfg["approaches"]["A3v2_RG"], llm, "t")
    assert pred["stop_reason"] == "NO_FINAL_VERDICT" and pred["predicted_label"] == pred["initial_label"] == "SUPPORTED"


def test_missing_xbrl_facts_give_unavailable_not_a_number():
    assert free_cash_flow("ADBE", "2026-10-05", "quarter", "2026-11-27")["status"] == "UNAVAILABLE"


def test_period_check_ignores_duration_known_limitation():
    """A nine-month figure ending on the quarter's end date passes as MATCH:
    period checks compare end dates only (disclosed WARNING)."""
    period = {"period_end": "2026-08-28", "basis": "quarter", "comparison_end": "2025-08-28", "source": "stated_date"}
    assert period_status("2026-08-28", period) == "MATCH"
    assert period_status("2026-05-29", period) == "OTHER_PERIOD"


def test_manifest_records_v2_code_and_prompt_hashes(cfg, claims, tmp_path):
    runs = str(tmp_path / "runs")
    rid = run_experiment(cfg, *claims, llm_mode="mock", llm=CachedLLM(mode="mock", inner=ScriptedLLM(responses())),
                         approaches=["A3v2_R"], runs_dir=runs, progress=lambda *_: None)
    m = json.load(open(os.path.join(runs, rid, "manifest.json")))
    assert "a3v2/guard.py" in m["code"]["files_sha256"] and "a3v2/reviewer.py" in m["code"]["files_sha256"]
    assert len(m["versions"]["a3v2_review_system_prompt_hash"]) >= 12 and m["versions"]["a3v2_guard"].startswith("a3v2-guard")


def test_client_that_cannot_be_built_leaves_no_reservation(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ledger = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "ledger"))
    llm = CachedLLM(mode="live", model="claude-sonnet-4-5-20250929", temperature=0, cache_dir=str(tmp_path / "c"),
                    approval=APPROVAL, ledger=ledger)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        llm.create("s", [{"role": "user", "content": "x"}], [{"name": "t", "input_schema": {}}], 100)
    s = ledger.status()
    assert s["open_reservations"] == [] and s["committed_usd"] == 0
    rid = ledger.reserve(1.0)
    ledger.release(rid, "never sent")
    assert ledger.status()["committed_usd"] == 0
