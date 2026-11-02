"""The four approaches on real cached SEC data with a scripted LLM (no paid
calls): stage activation / deactivation, self-reflection behaviour, guards,
evidence provenance and citation validity."""
import pytest

from engine.config import load_config
from engine.llm import CachedLLM, ScriptedLLM
from experiments import RUNNERS

AMZN_DEBT = {"metric": "LongTermDebt", "measure": "level", "period_basis": "instant", "period_end": None,
             "comparison": "decrease", "threshold": None, "stated_value": None}  # AMZN debt rose -> FALSE


def quote_of(ev):
    return ev["text"][20:90]


def verdict(label="SUPPORTED", ctype="numeric", assertions=(), cite="support"):
    def f(p):
        ev = p["evidence"][0]
        item = {"evidence_id": ev["evidence_id"], "quote": quote_of(ev)}
        return {"label": label, "claim_type": ctype, "numeric_assertions": list(assertions),
                "supporting_evidence": [item] if cite == "support" else [],
                "contradicting_evidence": [item] if cite == "contradict" else [], "reasoning_summary": "scripted"}
    return f


PLAN = {"hypotheses": [{"hypothesis_id": "H1", "challenge": "Did costs rise?", "search_query": "operating expenses increased",
                        "numeric_check": {"metric": "OperatingIncome", "measure": "level", "period_basis": "quarter",
                                          "period_end": None, "comparison": "increase", "threshold": None, "stated_value": None}},
                       {"hypothesis_id": "H2", "challenge": "Currency effects?", "search_query": "foreign exchange rates impact"}]}
CRITIQUE = {"weaknesses": [{"weakness_id": "W1", "critique": "cause not stated"}, {"weakness_id": "W2", "critique": "period"}]}


def final_from_counter(label="CONTRADICTED", invent=False, bad_quote=False):
    def f(p):
        ev = (p.get("counter_evidence") or [{"evidence_id": "E1", "text": "x" * 100}])[0]
        item = {"evidence_id": "E999" if invent else ev["evidence_id"], "quote": "made up words not present" if bad_quote else quote_of(ev)}
        return {"assessments": [{"item_id": "H1", "assessment": "CHALLENGE_SUPPORTED", "evidence": [item]}],
                "label": label, "verdict_changed": True, "change_reason": "counter evidence",
                "supporting_evidence": [], "contradicting_evidence": [item] if label == "CONTRADICTED" else [],
                "reasoning_summary": "scripted"}
    return f


def keep(label):
    return {"assessments": [], "label": label, "verdict_changed": False, "supporting_evidence": [], "contradicting_evidence": [],
            "reasoning_summary": "kept"}


def run(cfg, name, claim, responses, **overrides):
    scripted = ScriptedLLM(responses)
    llm = CachedLLM(mode="mock", inner=scripted, model=cfg["common"]["llm"]["model"])
    pred, trace = RUNNERS[cfg["approaches"][name]["kind"]](claim.to_input(), cfg["approaches"][name], llm, "test")
    return pred, trace, scripted


def test_a1_takes_llm_label_without_numeric_stage(main_cfg, dev_claims):
    pred, trace, llm = run(main_cfg, "A1_conventional_rag", dev_claims["DEV-AMZN-03"], {"submit_verdict": verdict(assertions=[AMZN_DEBT])})
    assert pred["predicted_label"] == "SUPPORTED" and pred["numeric_checks"] == 0
    assert len(llm.requests) == 1 and not any(t["tool"] == "verify_numbers" for t in trace["tool_calls"])


def test_a2_numeric_stage_overrides_and_shares_initial_request(main_cfg, dev_claims):
    c = dev_claims["DEV-AMZN-03"]
    _, _, l1 = run(main_cfg, "A1_conventional_rag", c, {"submit_verdict": verdict(assertions=[AMZN_DEBT])})
    pred, trace, l2 = run(main_cfg, "A2_rag_numeric", c, {"submit_verdict": verdict(assertions=[AMZN_DEBT])})
    assert l1.requests[0] == l2.requests[0]  # byte-identical initial call
    assert pred["llm_label"] == "SUPPORTED" and pred["predicted_label"] == "CONTRADICTED"
    assert pred["numeric_rule"] == "NUMERIC_FALSE" and pred["numeric_statuses"] == ["FALSE"]
    assert any(e["kind"] == "derived_metric" for e in pred["contradicting_evidence"])


def test_a2_skips_numeric_for_qualitative_claims(main_cfg, dev_claims):
    pred, _, _ = run(main_cfg, "A2_rag_numeric", dev_claims["DEV-AAPL-04"], {"submit_verdict": verdict("INSUFFICIENT_EVIDENCE", "interpretive", cite=None)})
    assert pred["numeric_rule"] == "NOT_APPLICABLE" and pred["numeric_checks"] == 0


def test_contradiction_stage_activation(main_cfg, dev_claims):
    pred, trace, llm = run(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": final_from_counter("CONTRADICTED")})
    assert [r["tools"] for r in llm.requests] == [["submit_verdict"], ["submit_contradiction_plan"], ["submit_reconciliation"]]
    inv = pred["contradiction"]
    assert inv["enabled"] and [h["hypothesis_id"] for h in inv["hypotheses"]] == ["H1", "H2"]
    assert [q["hypothesis_id"] for q in inv["queries"]] == ["H1", "H2"] and inv["counter_evidence_ids"]
    assert inv["counter_numeric"][0]["status"] in ("TRUE", "FALSE")
    initial_ids = set(trace["stages"][0]["retrieved"])
    assert not initial_ids & set(inv["counter_evidence_ids"])  # contradiction search returns NEW passages
    assert pred["initial_label"] == "SUPPORTED" and pred["predicted_label"] == "CONTRADICTED" and pred["verdict_changed"]
    assert inv["challenges_supported"] == 1 and inv["guard_reverted"] is None
    stage_names = [s["stage"] for s in trace["stages"]]
    assert stage_names == ["initial", "numeric_verification", "contradiction_investigation", "reconciliation"]


def test_contradiction_stage_deactivation_equals_a2(dev_claims):
    cfg = load_config("configs/ablation_contradiction.json")
    c = dev_claims["DEV-AMZN-03"]
    resp = {"submit_verdict": verdict(assertions=[AMZN_DEBT])}
    a2, _, l2 = run(cfg, "A2_rag_numeric", c, resp)
    off, trace, l3 = run(cfg, "A3_stage_off", c, resp)
    assert l2.requests == l3.requests and len(l3.requests) == 1
    assert off["predicted_label"] == a2["predicted_label"] and off["contradiction"] == {"enabled": False}
    assert {k: a2[k] for k in ("supporting_evidence", "contradicting_evidence")} == {k: off[k] for k in ("supporting_evidence", "contradicting_evidence")}


def test_no_counter_retrieval_ablation(dev_claims):
    cfg = load_config("configs/ablation_contradiction.json")
    pred, _, _ = run(cfg, "A3_no_counter_retrieval", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": keep("SUPPORTED")})
    assert pred["contradiction"]["queries"] == [] and pred["retrieval_queries"] == 1
    assert pred["contradiction"]["counter_numeric"]  # numeric checks still on


def test_invented_counterevidence_is_rejected(main_cfg, dev_claims):
    pred, _, _ = run(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": final_from_counter("CONTRADICTED", invent=True)})
    inv = pred["contradiction"]
    assert inv["invalid_challenges"] == 1 and inv["assessments"][0]["assessment"] == "NO_RELEVANT_EVIDENCE"
    assert inv["guard_reverted"] == "CHANGE_TO_CONTRADICTED_WITHOUT_VALID_EVIDENCE"
    assert pred["predicted_label"] == "SUPPORTED" and not pred["verdict_changed"]


def test_misquoted_counterevidence_is_rejected(main_cfg, dev_claims):
    pred, _, _ = run(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-06"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": final_from_counter("CONTRADICTED", bad_quote=True)})
    assert pred["predicted_label"] == "SUPPORTED"
    assert any("QUOTE_NOT_IN_PASSAGE" in a["evidence"][0]["issues"] for a in pred["contradiction"]["assessments"])


def test_numeric_rule_reapplied_after_reconciliation(main_cfg, dev_claims):
    pred, _, _ = run(main_cfg, "A3_contradiction_aware", dev_claims["DEV-AMZN-03"], {
        "submit_verdict": verdict(assertions=[AMZN_DEBT]), "submit_contradiction_plan": PLAN,
        "submit_reconciliation": keep("SUPPORTED") | {"supporting_evidence": []}})
    assert pred["initial_label"] == "CONTRADICTED" and pred["predicted_label"] == "CONTRADICTED"


def test_self_reflection_uses_no_new_retrieval(main_cfg, dev_claims):
    pred, trace, llm = run(main_cfg, "SR_self_reflection", dev_claims["DEV-AAPL-05"], {
        "submit_verdict": verdict("SUPPORTED", "interpretive"), "submit_self_critique": CRITIQUE,
        "submit_revision": keep("INSUFFICIENT_EVIDENCE") | {"verdict_changed": True}})
    assert [r["tools"] for r in llm.requests] == [["submit_verdict"], ["submit_self_critique"], ["submit_revision"]]
    assert pred["retrieval_queries"] == 1 and len(trace["tool_calls"]) == 1
    assert "counter_evidence" not in str(llm.requests[2]["messages"][-1])
    assert pred["predicted_label"] == "INSUFFICIENT_EVIDENCE" and pred["reflection"]["guard_reverted"] is None
    assert [w["weakness_id"] for w in pred["reflection"]["weaknesses"]] == ["W1", "W2"]


def test_self_reflection_change_without_evidence_is_reverted(main_cfg, dev_claims):
    pred, _, _ = run(main_cfg, "SR_self_reflection", dev_claims["DEV-AAPL-05"], {
        "submit_verdict": verdict("INSUFFICIENT_EVIDENCE", "interpretive", cite=None), "submit_self_critique": CRITIQUE,
        "submit_revision": keep("CONTRADICTED") | {"verdict_changed": True}})
    assert pred["predicted_label"] == "INSUFFICIENT_EVIDENCE"
    assert pred["reflection"]["guard_reverted"] == "CHANGE_TO_CONTRADICTED_WITHOUT_VALID_EVIDENCE"


def test_second_look_budgets_match(main_cfg, dev_claims):
    c = dev_claims["DEV-AAPL-05"]
    _, _, a3 = run(main_cfg, "A3_contradiction_aware", c, {"submit_verdict": verdict("SUPPORTED", "interpretive"),
                                                          "submit_contradiction_plan": PLAN, "submit_reconciliation": keep("SUPPORTED")})
    _, _, sr = run(main_cfg, "SR_self_reflection", c, {"submit_verdict": verdict("SUPPORTED", "interpretive"),
                                                      "submit_self_critique": CRITIQUE, "submit_revision": keep("SUPPORTED")})
    assert len(a3.requests) == len(sr.requests) == 3
    assert [r["max_tokens"] for r in a3.requests] == [r["max_tokens"] for r in sr.requests]
    assert {r["system"] for r in a3.requests + sr.requests} == {a3.requests[0]["system"]}
    assert a3.requests[0] == sr.requests[0]


def test_per_claim_llm_budget_stops_after_initial(dev_claims):
    raw = {"experiment_id": "t", "common": {"budget": {"max_llm_calls_per_claim": 1, "max_retrieval_queries_per_claim": 4}},
           "approaches": [{"name": "A3", "kind": "contradiction_aware"}]}
    cfg = load_config(raw)
    pred, _, llm = run(cfg, "A3", dev_claims["DEV-AMZN-06"], {"submit_verdict": verdict("SUPPORTED", "interpretive")})
    assert len(llm.requests) == 1 and pred["stop_reason"] == "BUDGET_EXHAUSTED_AFTER_INITIAL"
    assert pred["predicted_label"] == "SUPPORTED"


def test_evidence_provenance_and_citation_validity(main_cfg, dev_claims):
    c = dev_claims["DEV-AMZN-04"]
    pred, trace, _ = run(main_cfg, "A2_rag_numeric", c, {"submit_verdict": verdict("SUPPORTED", "interpretive")})
    assert pred["supporting_evidence"] and not pred["unsupported_conclusion"]
    for cite in pred["citations"]:
        assert cite["valid"] and cite["accession_number"] and cite["source_url"].startswith("https://www.sec.gov/")
        assert cite["filed"] <= c.as_of_date
    assert all(e["filed"] is None or e["filed"] <= c.as_of_date for e in trace["evidence"])


def test_unknown_or_misquoted_citation_counts_as_unsupported(main_cfg, dev_claims):
    def bad(p):
        return {"label": "SUPPORTED", "claim_type": "interpretive", "numeric_assertions": [], "contradicting_evidence": [],
                "supporting_evidence": [{"evidence_id": "E77", "quote": "anything at all here"},
                                        {"evidence_id": p["evidence"][0]["evidence_id"], "quote": "this sentence is not in the filing"}],
                "reasoning_summary": "r"}
    pred, _, _ = run(main_cfg, "A1_conventional_rag", dev_claims["DEV-AMZN-04"], {"submit_verdict": bad})
    assert pred["unsupported_conclusion"] and len(pred["invalid_citations"]) == 2
    assert {i for c in pred["invalid_citations"] for i in c["issues"]} == {"UNKNOWN_EVIDENCE_ID", "QUOTE_NOT_IN_PASSAGE"}


def test_missing_structured_output_is_recorded_not_guessed(main_cfg, dev_claims):
    class Silent:
        version = "silent"

        def create(self, *a, **k):
            return {"content": [{"type": "text", "text": "I think it's fine"}], "usage": {"input_tokens": 10, "output_tokens": 5},
                    "stop_reason": "end_turn"}
    llm = CachedLLM(mode="mock", inner=Silent())
    pred, _ = RUNNERS["financial_verification"](dev_claims["DEV-AAPL-01"].to_input(), main_cfg["approaches"]["A2_rag_numeric"], llm)
    assert pred["stop_reason"] == "NO_VERDICT" and pred["initial_label"] is None and pred["error"]


@pytest.mark.parametrize("name", ["A1_conventional_rag", "A2_rag_numeric", "A3_contradiction_aware", "SR_self_reflection"])
def test_output_has_required_structure(main_cfg, dev_claims, name):
    llm = CachedLLM(mode="mock")
    pred, trace = RUNNERS[main_cfg["approaches"][name]["kind"]](dev_claims["DEV-MSFT-04"].to_input(), main_cfg["approaches"][name], llm, "t")
    for key in ("claim_id", "predicted_label", "supporting_evidence", "contradicting_evidence", "reasoning_summary", "citations",
                "investigation_trace_id", "token_usage", "latency_ms", "estimated_cost_usd"):
        assert key in pred
    assert set(pred["token_usage"]) == {"input", "output"}
    for key in ("trace_id", "approach", "claim", "initial_label", "final_label", "tool_calls", "evidence", "citations",
                "token_usage", "latency_ms", "estimated_cost_usd", "stop_reason", "prompt_version", "engine_version", "config"):
        assert key in trace
