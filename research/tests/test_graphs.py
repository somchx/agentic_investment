"""LangGraph orchestration: graph shapes, state transitions, failure routing,
retries, contradiction logging and point-in-time behaviour on the
future-period claims. Scripted LLM only (no paid calls)."""
import pytest
import requests
from langgraph.types import RetryPolicy

from engine.config import load_config
from engine.datasets import load_split
from engine.llm import CachedLLM, PaidCallNotApproved, ScriptedLLM
from graphs import build_graph, run_graph
from graphs.build import is_transient

from test_approaches import CRITIQUE, PLAN, final_from_counter, keep, verdict

FAST_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.001, backoff_factor=1.0, jitter=False, retry_on=is_transient)
FUTURE_CLAIMS = ("GOLD-AAPL-04", "GOLD-AMZN-05", "GOLD-MSFT-05", "GOLD-NVDA-05", "GOLD-WMT-05")


def go(cfg, name, claim, responses, graph=None):
    scripted = ScriptedLLM(responses)
    llm = CachedLLM(mode="mock", inner=scripted, model=cfg["common"]["llm"]["model"])
    a = cfg["approaches"][name]
    pred, trace = run_graph(a["kind"], claim.to_input(), a, llm, "test", graph=graph)
    return pred, trace, scripted


def nodes_of(kind, enabled=True):
    return set(build_graph(kind, enabled).get_graph().nodes) - {"__start__", "__end__"}


def test_graph_shapes():
    base = {"retrieve_evidence", "initial_verdict", "finalize"}
    assert nodes_of("conventional_rag") == base
    assert nodes_of("financial_verification") == base | {"numeric_verification"}
    assert nodes_of("contradiction_aware") == base | {"numeric_verification", "generate_hypotheses", "counter_investigation",
                                                      "reconcile", "apply_guards"}
    assert nodes_of("self_reflection") == base | {"numeric_verification", "self_critique", "revise", "apply_guards"}
    assert nodes_of("contradiction_aware", enabled=False) == nodes_of("financial_verification")
    with pytest.raises(ValueError):
        build_graph("not_an_approach")


@pytest.mark.parametrize("name,expected", [
    ("A1_conventional_rag", ["retrieve_evidence", "initial_verdict", "finalize"]),
    ("A2_rag_numeric", ["retrieve_evidence", "initial_verdict", "numeric_verification", "finalize"]),
    ("A3_contradiction_aware", ["retrieve_evidence", "initial_verdict", "numeric_verification", "generate_hypotheses",
                                "counter_investigation", "reconcile", "apply_guards", "finalize"]),
    ("SR_self_reflection", ["retrieve_evidence", "initial_verdict", "numeric_verification", "self_critique", "revise",
                            "apply_guards", "finalize"]),
])
def test_state_transitions_follow_the_graph(main_cfg, dev_claims, name, expected):
    pred, trace, _ = go(main_cfg, name, dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict(), "submit_contradiction_plan": PLAN, "submit_reconciliation": keep("SUPPORTED"),
        "submit_self_critique": CRITIQUE, "submit_revision": keep("SUPPORTED")})
    g = trace["graph"]
    assert g["framework"] == "langgraph" and g["nodes_visited"] == expected
    assert all(s["status"] == "ok" for s in g["execution_trace"])
    calls = [s["llm_calls_so_far"] for s in g["execution_trace"]]
    assert calls == sorted(calls) and calls[-1] == pred["llm_calls"]
    assert pred["predicted_label"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")


@pytest.mark.parametrize("bad", [{"label": "MAYBE"}, None])
def test_invalid_initial_output_routes_to_finalize(main_cfg, dev_claims, bad):
    if bad is None:  # the model answers in text without calling the tool
        class NoTool(ScriptedLLM):
            def create(self, *a, **k):
                return {"content": [{"type": "text", "text": "{not json"}], "usage": {"input_tokens": 10, "output_tokens": 5},
                        "stop_reason": "end_turn"}
        llm = CachedLLM(mode="mock", inner=NoTool({}), model=main_cfg["common"]["llm"]["model"])
        a = main_cfg["approaches"]["A3_contradiction_aware"]
        pred, trace = run_graph(a["kind"], dev_claims["DEV-AMZN-06"].to_input(), a, llm, "test")
    else:
        pred, trace, _ = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {"submit_verdict": bad})
    assert pred["predicted_label"] == "INSUFFICIENT_EVIDENCE" and pred["initial_label"] is None
    assert pred["stop_reason"] == "NO_VERDICT" and pred["error"]
    assert trace["graph"]["nodes_visited"] == ["retrieve_evidence", "initial_verdict", "finalize"]
    assert trace["graph"]["failed_stage"] == "initial_verdict"


def test_failure_in_second_look_keeps_initial_verdict(main_cfg, dev_claims):
    pred, trace, _ = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"],
                        {"submit_verdict": verdict(), "submit_contradiction_plan": PLAN, "submit_reconciliation": {"label": "BOGUS"}})
    # an invalid final label is caught by the guard: initial verdict kept, recorded
    assert pred["predicted_label"] == pred["initial_label"] == "SUPPORTED"
    assert pred["contradiction"]["guard_reverted"] == "INVALID_LABEL"


def test_transient_api_error_is_retried_with_the_same_request(main_cfg, dev_claims):
    attempts = []

    def flaky(p):
        attempts.append(1)
        if len(attempts) == 1:
            raise requests.Timeout("read timed out")
        return verdict()(p)
    graph = build_graph("financial_verification", True, FAST_RETRY)
    pred, trace, llm = go(main_cfg, "A2_rag_numeric", dev_claims["DEV-AMZN-06"], {"submit_verdict": flaky}, graph=graph)
    assert len(attempts) == 2 and pred["stop_reason"] == "COMPLETED"
    assert llm.requests[0] == llm.requests[1]  # the retry sent the identical request
    assert pred["llm_calls"] == 1  # the failed attempt is not counted as a model call


def test_persistent_transient_error_gives_up_after_max_attempts(main_cfg, dev_claims):
    calls = []

    def down(p):
        calls.append(1)
        raise requests.ConnectionError("connection refused")
    graph = build_graph("conventional_rag", True, FAST_RETRY)
    with pytest.raises(requests.ConnectionError):
        go(main_cfg, "A1_conventional_rag", dev_claims["DEV-AMZN-06"], {"submit_verdict": down}, graph=graph)
    assert len(calls) == 3


def test_paid_call_refusal_is_never_retried(main_cfg, dev_claims):
    calls = []

    def refuse(p):
        calls.append(1)
        raise PaidCallNotApproved("no approval")
    graph = build_graph("conventional_rag", True, FAST_RETRY)
    with pytest.raises(PaidCallNotApproved):
        go(main_cfg, "A1_conventional_rag", dev_claims["DEV-AMZN-06"], {"submit_verdict": refuse}, graph=graph)
    assert len(calls) == 1


def test_transient_classification():
    resp = requests.Response()
    resp.status_code = 529
    assert is_transient(requests.HTTPError(response=resp))
    resp.status_code = 400
    assert not is_transient(requests.HTTPError(response=resp))
    assert is_transient(requests.Timeout()) and not is_transient(ValueError())


def test_no_counterevidence_found_is_logged_not_invented(main_cfg, dev_claims):
    plan = {"hypotheses": [{"hypothesis_id": "H1", "challenge": "nothing", "search_query": "zzzqqq xyzzy plugh"}]}
    pred, trace, llm = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"],
                          {"submit_verdict": verdict(), "submit_contradiction_plan": plan, "submit_reconciliation": keep("SUPPORTED")})
    rec = pred["second_look_record"]
    assert rec["counterevidence_found"] == 0 and rec["no_counterevidence_found"] is True
    assert rec["counterevidence_queries"] == ["zzzqqq xyzzy plugh"] and not pred["verdict_changed"]
    reconcile_packet = llm.requests[-1]["messages"][-1]["content"][-1]["text"]
    assert '"counter_evidence": []' in reconcile_packet


def test_contradictory_evidence_changes_verdict_and_is_recorded(main_cfg, dev_claims):
    pred, trace, _ = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": final_from_counter("CONTRADICTED")})
    rec = pred["second_look_record"]
    assert pred["predicted_label"] == "CONTRADICTED" and pred["verdict_changed"]
    assert rec["initial_verdict"] == "SUPPORTED" and rec["final_verdict"] == "CONTRADICTED"
    assert rec["counterevidence_found"] > 0 and rec["change_reason"] == "counter evidence"
    assert rec["challenges_supported"] == 1 and rec["contradiction_hypotheses"] == ["Did costs rise?", "Currency effects?"]


def test_token_cost_and_latency_logging(main_cfg, dev_claims):
    pred, trace, _ = go(main_cfg, "SR_self_reflection", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict(), "submit_self_critique": CRITIQUE, "submit_revision": keep("SUPPORTED")})
    assert pred["llm_calls"] == 3 and pred["token_usage"] == {"input": 3000, "output": 600}  # ScriptedLLM usage 1000/200 per call
    expected = round(3000 / 1e6 * 3.0 + 600 / 1e6 * 15.0, 6)
    assert pred["estimated_cost_usd"] == pytest.approx(expected)
    assert sum(c["input_tokens"] for c in trace["llm_calls"]) == 3000 and pred["latency_ms"] >= 0


@pytest.mark.parametrize("claim_id", FUTURE_CLAIMS)
def test_future_period_claims_see_no_future_data(main_cfg, claim_id):
    claim = {c.claim_id: c for c in load_split("gold")}[claim_id]
    pred, trace, _ = go(main_cfg, "A3_contradiction_aware", claim, {
        "submit_verdict": verdict("INSUFFICIENT_EVIDENCE", "numeric", cite=None), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": keep("INSUFFICIENT_EVIDENCE")})
    cutoff = claim.as_of_date
    assert all(f["filed"] <= cutoff for f in trace["corpus"]["filings"])
    assert all(u["filed"] is None or u["filed"] <= cutoff for u in trace["evidence"])
    for n in (c for s in trace["tool_calls"] if s["tool"] == "verify_numbers" for c in s["checks"]):
        assert all(f["filed"] <= cutoff for f in (n["computed"] or {}).get("facts", []))
    assert pred["predicted_label"] == "INSUFFICIENT_EVIDENCE"


def test_unavailable_period_is_unverifiable_not_guessed(main_cfg):
    claim = {c.claim_id: c for c in load_split("gold")}["GOLD-AMZN-05"]  # quarter ending 2026-12-31, cutoff 2026-11-01
    future_q = {"metric": "Revenue", "measure": "level", "period_basis": "quarter", "period_end": "2026-12-31",
                "comparison": "increase", "threshold": None, "stated_value": None}
    pred, trace, _ = go(main_cfg, "A2_rag_numeric", claim, {"submit_verdict": verdict("SUPPORTED", "numeric", [future_q], cite=None)})
    check = trace["stages"][1]["checks"][0]
    assert check["status"] == "UNVERIFIABLE" and check["issues"][0].startswith("PERIOD_NOT_AVAILABLE")
    assert pred["numeric_rule"] == "NUMERIC_PARTIALLY_UNVERIFIABLE"
    assert pred["unsupported_conclusion"]  # SUPPORTED with no valid citation is flagged


def test_ablation_config_still_loads():
    cfg = load_config("configs/ablation_contradiction.json")
    assert not cfg["approaches"]["A3_stage_off"]["contradiction"]["enabled"]


def test_json_encoded_array_fields_are_decoded_and_recorded(main_cfg, dev_claims):
    # seen live: the model returned `assessments` as a JSON string instead of an array
    import json as _json

    def stringly(p):
        out = final_from_counter("CONTRADICTED")(p)
        return {**out, "assessments": _json.dumps(out["assessments"])}
    pred, trace, llm = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN, "submit_reconciliation": stringly})
    assert pred["stop_reason"] == "COMPLETED" and pred["predicted_label"] == "CONTRADICTED"
    assert pred["contradiction"]["challenges_supported"] == 1
    assert trace["llm_calls"][-1]["coerced_fields"] == ["assessments"]
    assert isinstance(trace["llm_calls"][-1]["output"]["assessments"], str)  # raw output kept as returned


def test_malformed_assessments_are_rejected_not_crashing(main_cfg, dev_claims):
    def garbage(p):
        return {**final_from_counter("CONTRADICTED")(p), "assessments": ["not an object", 7]}
    pred, _, _ = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN, "submit_reconciliation": garbage})
    assert pred["stop_reason"] == "COMPLETED"
    assert [a["flag"] for a in pred["contradiction"]["assessments"]] == ["MALFORMED_ASSESSMENT"] * 2
    assert pred["contradiction"]["challenges_supported"] == 0


def test_non_object_evidence_items_do_not_break_finalize(main_cfg, dev_claims):
    # seen live (GOLD-AMZN-10): an initial verdict listed evidence as bare strings
    def loose(p):
        return {**verdict("SUPPORTED", "interpretive")(p), "supporting_evidence": ["E1", "E2"]}
    pred, _, _ = go(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": loose, "submit_contradiction_plan": PLAN, "submit_reconciliation": keep("SUPPORTED")})
    assert pred["stop_reason"] == "COMPLETED" and pred["second_look_record"]["initial_evidence"] == []
    assert pred["unsupported_conclusion"]  # bare ids are not valid citations


def test_truncated_json_evidence_is_one_invalid_item(main_cfg, dev_claims):
    # seen live (GOLD-KO-08): contradicting_evidence was a JSON string cut off before its closing bracket
    def truncated(p):
        out = verdict("CONTRADICTED", "interpretive", cite="contradict")(p)
        import json as _json
        return {**out, "contradicting_evidence": _json.dumps(out["contradicting_evidence"])[:-1]}
    for name in ("A1_conventional_rag", "A2_rag_numeric"):
        pred, _, _ = go(main_cfg, name, dev_claims["DEV-AMZN-06"], {"submit_verdict": truncated})
        assert len(pred["invalid_citations"]) == 1 and pred["invalid_citations"][0]["issues"] == ["MALFORMED_ITEM"]
        assert pred["unsupported_conclusion"] and pred["stop_reason"] == "COMPLETED"
