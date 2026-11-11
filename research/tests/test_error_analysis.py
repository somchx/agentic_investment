"""Error analysis over a finished run: paired outcomes, second-look
transitions, error types, citation and counter-evidence audits, latency,
and the freeze diff. Synthetic predictions only -- no model, no run dir."""
import json

from openpyxl import Workbook

from engine import error_analysis as ea
from engine.freeze import diff_freeze

GOLD = {"C1": {"label": "SUPPORTED"}, "C2": {"label": "INSUFFICIENT_EVIDENCE"},
        "C3": {"label": "CONTRADICTED"}, "C4": {"label": "SUPPORTED"}}


def pred(approach, cid, label, initial=None, kind="financial_verification", **kw):
    return {"approach": approach, "claim_id": cid, "predicted_label": label, "initial_label": initial or label,
            "approach_kind": kind, "claim_category": "ambiguous", "verdict_changed": (initial or label) != label, **kw}


def a3(cid, initial, final, **kw):
    return pred("A3", cid, final, initial, kind="contradiction_aware", **kw)


def test_paired_outcomes_quadrants_and_alternatives():
    preds = [pred("A2", "C1", "SUPPORTED"), a3("C1", "SUPPORTED", "SUPPORTED"),
             pred("A2", "C2", "INSUFFICIENT_EVIDENCE"), a3("C2", "INSUFFICIENT_EVIDENCE", "SUPPORTED"),
             pred("A2", "C3", "SUPPORTED"), a3("C3", "SUPPORTED", "CONTRADICTED"),
             pred("A2", "C4", "CONTRADICTED"), a3("C4", "CONTRADICTED", "CONTRADICTED"),
             pred("A2", "C9", "SUPPORTED")]  # unlabelled and unpaired: dropped
    rows = {r["claim_id"]: r["quadrant"] for r in ea.paired_outcomes(preds, GOLD, "A2", "A3")}
    assert rows == {"C1": "both_correct", "C2": "only_a", "C3": "only_b", "C4": "both_wrong"}
    lenient = {("C2", "A3"): "ACCEPTABLE"}
    assert {r["claim_id"]: r["quadrant"] for r in ea.paired_outcomes(preds, GOLD, "A2", "A3", lenient)}["C2"] == "both_correct"


def test_second_look_rows_record_direction_and_investigation():
    info = {"assessments": [{"assessment": "CHALLENGE_SUPPORTED"}, {"assessment": "NO_RELEVANT_EVIDENCE"}, "junk"],
            "hypotheses": [{}, {}], "guard_reverted": None, "model_final_label": "SUPPORTED"}
    rows = ea.second_look_rows([a3("C2", "INSUFFICIENT_EVIDENCE", "SUPPORTED", contradiction=info),
                                a3("C1", "SUPPORTED", "SUPPORTED", contradiction={"hypotheses": []}),
                                pred("A2", "C1", "SUPPORTED")], GOLD)
    by = {r["claim_id"]: r for r in rows}
    assert set(by) == {"C1", "C2"}
    assert by["C2"]["shift"] == "insufficient_to_decisive" and by["C2"]["path"] == "I→S"
    assert by["C2"]["transition"] == "correct_to_incorrect"
    assert by["C2"]["challenges_supported"] == 1 and by["C2"]["no_relevant_evidence"] == 1 and by["C2"]["completed"]
    assert by["C1"]["completed"] is False  # reconciliation never produced assessments


def test_label_shift_and_error_type():
    assert ea.label_shift("SUPPORTED", "CONTRADICTED") == "polarity_flip"
    assert ea.label_shift("CONTRADICTED", "INSUFFICIENT_EVIDENCE") == "decisive_to_insufficient"
    assert ea.label_shift("SUPPORTED", "SUPPORTED") == "unchanged"
    assert ea.error_type("SUPPORTED", "INSUFFICIENT_EVIDENCE") == "overconfident_supported"
    assert ea.error_type("CONTRADICTED", "INSUFFICIENT_EVIDENCE") == "overconfident_contradicted"
    assert ea.error_type("INSUFFICIENT_EVIDENCE", "SUPPORTED") == "over_abstention"
    assert ea.error_type("CONTRADICTED", "SUPPORTED") == "polarity_error"
    assert ea.error_type(None, "SUPPORTED") == "no_prediction"
    assert ea.error_type("SUPPORTED", "SUPPORTED") == "correct"


def test_value_in_quote_scales_and_percentages():
    assert ea.value_in_quote(125102000000.0, "Total long-term debt $ 46,547 $ 125,102")      # millions
    assert not ea.value_in_quote(21607000000.0, "Total long-term debt $ 46,547 $ 125,102")
    assert ea.value_in_quote(0.1565, "Total net sales increased 16 %", rel_tol=0.03)       # ratio as percent
    assert ea.value_in_quote(-1234.0, "Other income (1,234)")
    assert not ea.value_in_quote(None, "anything 5")


def _trace(evidence, claim="Revenue for the quarter ended June 30, 2026 rose.", tool_calls=(), llm_calls=(), nodes=()):
    return {"evidence": evidence, "claim": {"claim": claim, "as_of_date": "2026-08-15"}, "tool_calls": list(tool_calls),
            "llm_calls": list(llm_calls), "graph": {"execution_trace": list(nodes)}}


def test_citation_audit_checks_what_the_pipeline_does_not():
    ev = [{"evidence_id": "E1", "kind": "filing_passage", "filed": "2026-07-30", "period_end": "2026-06-30"},
          {"evidence_id": "E2", "kind": "xbrl_fact", "filed": "2026-07-30", "period_end": "2025-06-30", "values": [21607000000.0]},
          {"evidence_id": "E3", "kind": "derived_metric", "filed": "2026-07-30", "period_end": "2026-06-30", "values": [0.2]},
          {"evidence_id": "E4", "kind": "filing_passage", "filed": "2026-09-01", "period_end": "2026-06-30"}]
    p = pred("A3", "C1", "SUPPORTED", as_of_date="2026-08-15", citations=[
        {"evidence_id": "E1", "quote": "Revenue rose", "valid": True},
        {"evidence_id": "E2", "quote": "Total debt $ 46,547 $ 125,102", "valid": True},   # misattributed quote
        {"evidence_id": "E3", "quote": "", "valid": True},                                 # verifier-attached figure
        {"evidence_id": "E4", "quote": "late", "valid": False, "issues": ["FUTURE_EVIDENCE"]}])
    rows = {r["evidence_id"]: r for r in ea.citation_audit(p, _trace(ev))}
    assert rows["E1"]["quote_checked_by_pipeline"] and rows["E1"]["xbrl_value_in_quote"] is None
    assert rows["E1"]["period_matches_claim"] is True and rows["E2"]["period_matches_claim"] is False
    assert rows["E2"]["pipeline_valid"] and rows["E2"]["xbrl_value_in_quote"] is False
    assert rows["E3"]["xbrl_value_in_quote"] is None
    assert rows["E4"]["after_cutoff"] and not rows["E1"]["after_cutoff"]
    s = ea.citation_summary(list(rows.values()))[0]
    assert s["xbrl_quote_value_mismatch"] == 1 and s["xbrl_quotes_checked"] == 1 and s["after_cutoff"] == 1
    assert s["quote_not_checked"] == 2 and s["pipeline_valid_rate"] == 0.75


def test_counter_evidence_audit():
    ev = [{"evidence_id": f"E{i}", "accession_number": acc} for i, acc in ((1, "A"), (2, "A"), (3, "B"))]
    tc = [{"tool": "retrieve_passages", "purpose": "initial", "results": ["E1"]},
          {"tool": "retrieve_passages", "purpose": "counter:H1", "results": ["E2", "E3"]}]
    info = {"hypotheses": [{}, {}], "queries": [{}],
            "assessments": [{"assessment": "CHALLENGE_SUPPORTED", "evidence": [{"evidence_id": "E3", "valid": True}]},
                            {"assessment": "CHALLENGE_SUPPORTED", "evidence": [{"evidence_id": "E2", "valid": False}]}]}
    p = a3("C1", "SUPPORTED", "CONTRADICTED", contradiction=info, citations=[{"evidence_id": "E3"}])
    r = ea.counter_evidence_audit(p, _trace(ev, tool_calls=tc))
    assert r["counter_passages"] == 2 and r["new_filings"] == 1
    assert r["challenges_supported"] == 2 and r["supported_with_valid_citation"] == 1
    assert r["final_cites_counter_evidence"] and not r["changed_without_supported_challenge"]
    q = ea.counter_evidence_audit(a3("C2", "INSUFFICIENT_EVIDENCE", "SUPPORTED", contradiction={"assessments": []}), _trace([]))
    assert q["changed_without_supported_challenge"]


def test_latency_uses_live_measurements_only(tmp_path):
    d = tmp_path / "live" / "traces" / "A1"
    d.mkdir(parents=True)
    (d / "C1.json").write_text(json.dumps({"llm_calls": [{"request_key": "k1", "source": "live", "latency_ms": 4000},
                                                         {"request_key": "k2", "source": "cache", "latency_ms": 0}]}))
    live = ea.live_latency_index([str(tmp_path / "live")])
    assert live == {"k1": 4000}
    p = pred("A1", "C1", "SUPPORTED", llm_calls=2, token_usage={"input": 10, "output": 2}, estimated_cost_usd=0.1)
    t = _trace([], llm_calls=[{"request_key": "k1"}, {"request_key": "k1"}], nodes=[{"duration_ms": 500}])
    r = ea.efficiency_rows([p], {("A1", "C1"): t}, live)[0]
    assert r["latency_s"] == 8.5 and r["latency_complete"]
    t2 = _trace([], llm_calls=[{"request_key": "k1"}, {"request_key": "unmeasured"}])
    assert not ea.efficiency_rows([p], {("A1", "C1"): t2}, live)[0]["latency_complete"]


def test_scoring_summary_strict_and_alternative():
    preds = [pred("A2", "C1", "SUPPORTED"), a3("C1", "SUPPORTED", "SUPPORTED"),
             pred("A2", "C2", "INSUFFICIENT_EVIDENCE"), a3("C2", "INSUFFICIENT_EVIDENCE", "SUPPORTED")]
    gold = {k: GOLD[k] for k in ("C1", "C2")}
    s = ea.scoring_summary(preds, gold, {"strict": None, "lenient": {("C2", "A3"): "ACCEPTABLE"}}, [("A2", "A3")], n_boot=200)
    assert s["accuracy"]["strict"] == {"A2": 1.0, "A3": 0.5}
    assert s["accuracy"]["lenient"] == {"A2": 1.0, "A3": 1.0}
    c = s["comparisons"]["A2 -> A3 (strict)"]
    assert c["only_a_correct"] == 1 and c["only_b_correct"] == 0 and c["diff"] == -0.5


def test_adjudication_matches_workbook(tmp_path):
    jl = tmp_path / "v.jsonl"
    jl.write_text("\n".join(json.dumps({"case_id": c, "decision": d}) for c, d in (("X-A", "ACCEPTABLE"), ("Y-A", "NOT_ACCEPTABLE"))))
    wb = Workbook()
    ws = wb.active
    ws.title = "Cases"
    ws.append(["Case ID", "Decision [EDIT]"])
    ws.append(["X-A", "acceptable"])
    ws.append(["Y-A", "NOT_ACCEPTABLE"])
    wb.save(tmp_path / "ok.xlsx")
    assert ea.adjudication_matches_workbook(str(jl), str(tmp_path / "ok.xlsx"))["consistent"]
    ws["B3"] = "ACCEPTABLE"
    wb.save(tmp_path / "bad.xlsx")
    r = ea.adjudication_matches_workbook(str(jl), str(tmp_path / "bad.xlsx"))
    assert not r["consistent"] and r["mismatched"] == ["Y-A"]


def test_diff_freeze_ignores_volatile_and_reports_added():
    old = {"frozen_at": "t0", "git": {"dirty": True}, "files": {"a": "1"}, "scores": {"strict": {"A2": 0.68}}}
    new = {"frozen_at": "t1", "git": {"dirty": False}, "files": {"a": "1", "b": "2"}, "scores": {"strict": {"A2": 0.68}}}
    assert diff_freeze(old, new) == {"changed": [], "removed": [], "added": ["files/b"]}
    new["scores"]["strict"]["A2"] = 0.7
    del new["files"]["a"]
    d = diff_freeze(old, new)
    assert d["changed"] == ["scores/strict/A2"] and d["removed"] == ["files/a"]
