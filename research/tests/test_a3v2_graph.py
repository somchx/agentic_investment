"""A3 v2 graph end to end on a development claim with a scripted LLM (no
paid calls): node order, reviewer isolation, auditable trace, guard effect,
config rules, and v1 graphs untouched."""
import json

import pytest

from a3v2 import A3V2_VERSION, KIND
from a3v2.config import load_v2_config
from a3v2.graph import build_v2_graph, run as run_v2
from a3v2.prompts import REVIEW_SYSTEM_PROMPT
from engine.llm import CachedLLM, ScriptedLLM
from graphs import build_graph

from test_approaches import PLAN, quote_of, verdict


@pytest.fixture(scope="module")
def v2_cfg():
    return load_v2_config("configs/a3v2_development.json")


def review_with(relation):
    def f(p):
        ev = next(e for e in p["evidence"] if e["kind"] == "filing_passage")
        return {"findings": [{"assertion_id": "A0", "evidence_ids": [ev["evidence_id"]], "relation": relation, "evidence_type": "OBSERVED_RESULT",
                              "addresses": "LEVEL", "key_quote": ev["text"][20:90], "justification": "scripted"}]}
    return f


def change_to_contradicted(p):
    ev = p["counter_evidence"][0] if p.get("counter_evidence") else None
    item = [{"evidence_id": ev["evidence_id"], "quote": quote_of(ev)}] if ev else []
    return {"assessments": [{"item_id": "H1", "assessment": "CHALLENGE_SUPPORTED", "evidence": item}], "label": "CONTRADICTED",
            "verdict_changed": True, "change_reason": "scripted", "supporting_evidence": [], "contradicting_evidence": item,
            "reasoning_summary": "scripted"}


def go(cfg, claim, responses, name="A3v2_RG"):
    scripted = ScriptedLLM(responses)
    llm = CachedLLM(mode="mock", inner=scripted, model=cfg["approaches"][name]["llm"]["model"])
    pred, trace = run_v2(claim.to_input(), cfg["approaches"][name], llm, "test")
    return pred, trace, scripted


def test_node_order_isolation_and_trace(v2_cfg, dev_claims):
    pred, trace, llm = go(v2_cfg, dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict(ctype="interpretive"), "submit_contradiction_plan": PLAN,
        "submit_evidence_review": review_with("RELATED_NOT_DECIDING"), "submit_reconciliation": change_to_contradicted})
    assert trace["graph"]["nodes_visited"] == ["retrieve_evidence", "initial_verdict", "numeric_verification", "analyze_claim",
                                               "generate_hypotheses", "counter_investigation", "evidence_review", "reconcile_v2",
                                               "apply_guards", "reconciliation_guard", "finalize"]
    assert pred["approach_kind"] == KIND and trace["a3v2_version"] == A3V2_VERSION and pred["llm_calls"] == 4
    # the reviewer call: fresh conversation, own system prompt, no A2 verdict / reasoning / hypotheses
    rev = next(r for r in llm.requests if r["tools"] == ["submit_evidence_review"])
    assert rev["system"] == REVIEW_SYSTEM_PROMPT and len(rev["messages"]) == 1
    packet = json.loads(rev["messages"][0]["content"][-1]["text"].split("PACKET:\n", 1)[1])
    assert set(packet) == {"claim", "claim_period", "assertions", "evidence"}
    assert "scripted" not in json.dumps(packet) and "Did costs rise?" not in json.dumps(packet)
    # the reconciliation call sees the review table
    rec = next(r for r in llm.requests if r["tools"] == ["submit_reconciliation"])
    assert '"evidence_review"' in rec["messages"][-1]["content"][-1]["text"]
    # only context evidence -> the change is rejected and A2's label kept, with an auditable record
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["outcome"] == "REJECT" and g["reason_code"] == "CONTEXT_ONLY"
    assert pred["predicted_label"] == pred["initial_label"] == "SUPPORTED"
    assert {s["stage"] for s in trace["stages"]} >= {"analyze_claim", "evidence_review", "reconciliation_guard"}


@pytest.mark.parametrize("period,outcome,label", [("MATCH", "ACCEPT", "CONTRADICTED"),
                                                   ("OTHER_PERIOD", "REJECT", "SUPPORTED")])
def test_guard_on_a_reviewed_counter_passage(v2_cfg, dev_claims, period, outcome, label):
    """The reviewer marks one counter passage CONTRADICTS and reconciliation cites it: accepted when the passage
    is from the claim's quarter, rejected (PERIOD_MISMATCH) when it is from another quarter."""
    picked = {}

    def review(p):
        ev = next(e for e in p["evidence"] if e["kind"] == "filing_passage" and int(e["evidence_id"][1:]) > 6 and e["period_status"] == period)
        picked.update(evidence_id=ev["evidence_id"], quote=ev["text"][20:90])
        return {"findings": [{"assertion_id": "A0", "evidence_ids": [ev["evidence_id"]], "relation": "CONTRADICTS",
                              "evidence_type": "OBSERVED_RESULT", "addresses": "LEVEL", "key_quote": picked["quote"], "justification": "s"}]}

    def reconcile(p):
        item = [dict(picked)]
        return {"assessments": [{"item_id": "H1", "assessment": "CHALLENGE_SUPPORTED", "evidence": item}], "label": "CONTRADICTED",
                "verdict_changed": True, "change_reason": "s", "supporting_evidence": [], "contradicting_evidence": item, "reasoning_summary": "s"}
    pred, _, _ = go(v2_cfg, dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict(ctype="interpretive"), "submit_contradiction_plan": PLAN, "submit_evidence_review": review,
        "submit_reconciliation": reconcile})
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["outcome"] == outcome and pred["predicted_label"] == label
    if outcome == "REJECT":
        assert g["reason_code"] == "INVALID_DECIDING_EVIDENCE:PERIOD_MISMATCH"


def test_reviewer_only_arm_keeps_v1_guards(v2_cfg, dev_claims):
    pred, trace, _ = go(v2_cfg, dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict(ctype="interpretive"), "submit_contradiction_plan": PLAN,
        "submit_evidence_review": review_with("RELATED_NOT_DECIDING"), "submit_reconciliation": change_to_contradicted}, name="A3v2_R")
    assert "reconciliation_guard" not in trace["graph"]["nodes_visited"] and "evidence_review" in trace["graph"]["nodes_visited"]


def test_config_rules():
    with pytest.raises(ValueError, match="development"):
        load_v2_config({"experiment_id": "x", "dataset": {"split": "gold"}, "approaches": []})
    with pytest.raises(ValueError, match="needs the evidence review"):
        load_v2_config({"experiment_id": "x", "dataset": {"split": "development"},
                        "approaches": [{"name": "bad", "overrides": {"review": {"enabled": False}, "guard": {"enabled": True}}}]})
    with pytest.raises(ValueError):
        build_v2_graph(review_enabled=False, guard_enabled=True)


def test_v1_graphs_and_runners_unchanged():
    from experiments import RUNNERS
    assert KIND not in RUNNERS
    assert set(build_graph("contradiction_aware").get_graph().nodes) - {"__start__", "__end__"} == {
        "retrieve_evidence", "initial_verdict", "numeric_verification", "generate_hypotheses", "counter_investigation", "reconcile",
        "apply_guards", "finalize"}
