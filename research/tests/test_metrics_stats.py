"""Metric calculations and statistical analysis against hand-computed values."""
import math

import pytest

from engine.metrics import (citation_matches_ref, classification_metrics, efficiency, evaluate, evidence_scores, integrity_metrics,
                            second_look_metrics, transition, unsupported_rate)
from engine.stats import bootstrap_ci, bootstrap_diff, compare, mcnemar

S, C, I = "SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"


def test_classification_metrics_hand_computed():
    y = [S, S, S, C, C, I]
    p = [S, S, C, C, I, None]
    m = classification_metrics(y, p)
    assert m["accuracy"] == pytest.approx(3 / 6)
    # S: tp2 fp0 fn1 -> P1 R2/3 F0.8 ; C: tp1 fp1 fn1 -> P.5 R.5 F.5 ; I: tp0 fp1 fn1 -> F0
    assert m["per_class"][S]["f1"] == pytest.approx(0.8)
    assert m["per_class"][C]["f1"] == pytest.approx(0.5)
    assert m["per_class"][I]["f1"] == 0.0
    assert m["macro_f1"] == pytest.approx((0.8 + 0.5 + 0.0) / 3)
    assert m["confusion_matrix"][I]["NO_PREDICTION"] == 1 and m["no_prediction"] == 1
    assert sum(sum(r.values()) for r in m["confusion_matrix"].values()) == 6


def test_macro_f1_ignores_absent_classes():
    m = classification_metrics([S, S, C], [S, S, C])
    assert m["macro_f1"] == 1.0 and m["macro_f1_labels"] == [S, C]


def test_evidence_matching_and_scores():
    unit = {"evidence_id": "E1", "excerpt": "AWS segment operating income increased primarily due to increased sales"}
    cite = {"evidence_id": "E1", "kind": "filing_passage", "accession_number": "A1", "valid": True}
    assert citation_matches_ref(cite, unit, {"accession_number": "A1", "quote": "operating income increased primarily due to increased sales"})
    assert not citation_matches_ref(cite, unit, {"accession_number": "A2", "quote": "operating income"})
    assert not citation_matches_ref(cite, unit, {"accession_number": "A1", "quote": "currency headwinds reduced margins"})
    x = {"evidence_id": "E2", "kind": "xbrl_fact", "accession_number": "A1", "period_end": "2026-06-30", "valid": True}
    assert citation_matches_ref(x, None, {"accession_number": "A1", "kind": "xbrl_fact", "period_end": "2026-06-30"})
    pred = {"supporting_evidence": [cite], "contradicting_evidence": [x]}
    gold = {"supporting_evidence": [{"accession_number": "A1", "quote": "operating income increased"}],
            "contradictory_evidence": [{"accession_number": "A9", "quote": "x"}]}
    s = evidence_scores(pred, {"evidence": [unit]}, gold)
    assert s["evidence_precision"] == 0.5 and s["evidence_recall"] == 0.5
    assert evidence_scores(pred, None, {"supporting_evidence": []})["evidence_recall"] is None


def test_unsupported_and_efficiency_never_invent_values():
    preds = [{"predicted_label": S, "unsupported_conclusion": True, "latency_ms": 100, "token_usage": {"input": 10, "output": 2}, "estimated_cost_usd": 0.1},
             {"predicted_label": I, "unsupported_conclusion": False, "latency_ms": None, "token_usage": None, "estimated_cost_usd": None},
             {"predicted_label": C, "unsupported_conclusion": False, "latency_ms": 300}]
    u = unsupported_rate(preds)
    assert u["decisive"] == 2 and u["unsupported_conclusion_rate"] == 0.5
    e = efficiency(preds)
    assert e["avg_latency_ms"] == 200 and e["n_latency"] == 2 and e["n_cost"] == 1 and e["avg_cost_usd"] == 0.1


def test_evaluate_groups_and_uses_only_labelled_for_accuracy():
    gold = {"c1": {"label": S}, "c2": {"label": C}}
    preds = [{"claim_id": "c1", "approach": "A", "predicted_label": S, "claim_category": "numerical"},
             {"claim_id": "c2", "approach": "A", "predicted_label": S, "claim_category": "interpretive"},
             {"claim_id": "c3", "approach": "A", "predicted_label": C, "claim_category": "interpretive"}]
    rows = {r["approach"]: r for r in evaluate(preds, gold)}
    assert rows["A"]["n_predictions"] == 3 and rows["A"]["n_labelled"] == 2 and rows["A"]["accuracy"] == 0.5
    by_cat = {r["claim_category"]: r for r in evaluate(preds, gold, group_by=("approach", "claim_category"))}
    assert by_cat["numerical"]["accuracy"] == 1.0 and by_cat["interpretive"]["accuracy"] == 0.0
    assert evaluate(preds, {})[0]["accuracy"] is None


def test_mcnemar_exact_values():
    # 10 discordant pairs, 8 favour B: two-sided exact p = 2 * P(X<=2 | n=10, .5) = 2*56/1024
    y = [S] * 14
    a = [S] * 2 + [C] * 8 + [S] * 2 + [C] * 2
    b = [C] * 2 + [S] * 8 + [S] * 2 + [C] * 2
    m = mcnemar(y, a, b)
    assert (m["a_right_b_wrong"], m["b_right_a_wrong"], m["both_right"], m["both_wrong"]) == (2, 8, 2, 2)
    assert m["p_value_exact"] == pytest.approx(2 * 56 / 1024)
    assert m["chi2_cc"] == pytest.approx((6 - 1) ** 2 / 10)
    assert m["p_value_chi2_cc"] == pytest.approx(math.erfc(math.sqrt(2.5 / 2)))
    assert m["accuracy_diff_b_minus_a"] == pytest.approx((10 - 4) / 14)
    assert mcnemar([S], [S], [S])["p_value_exact"] == 1.0


def test_bootstrap_is_seeded_and_brackets_point_estimate():
    y = [S, C, I] * 20
    a = [S, S, S] * 20
    b = [S, C, S] * 20
    r1, r2 = bootstrap_diff(y, a, b, n_boot=500, seed=1), bootstrap_diff(y, a, b, n_boot=500, seed=1)
    assert r1 == r2
    acc = r1["accuracy"]
    assert acc["diff_b_minus_a"] == pytest.approx(1 / 3)
    assert acc["ci_low"] <= acc["diff_b_minus_a"] <= acc["ci_high"] and acc["ci_low"] > 0
    same = bootstrap_diff(y, a, a, n_boot=200, seed=1)["accuracy"]
    assert same["diff_b_minus_a"] == 0 and same["ci_low"] == same["ci_high"] == 0


def test_compare_pairs_on_claim_ids():
    gold = {"c1": {"label": S}, "c2": {"label": C}, "c3": {"label": I}}
    pa = [{"claim_id": "c1", "predicted_label": S}, {"claim_id": "c2", "predicted_label": S}, {"claim_id": "c4", "predicted_label": S}]
    pb = [{"claim_id": "c1", "predicted_label": S}, {"claim_id": "c2", "predicted_label": C}, {"claim_id": "c3", "predicted_label": I}]
    r = compare(pa, pb, gold, n_boot=100)
    assert r["n"] == 2 and r["pairing"]["dropped_unpaired"] == 1 and r["pairing"]["dropped_no_gold"] == 1
    assert r["mcnemar"]["b_right_a_wrong"] == 1


def _p(cid, initial, final, approach="A3", kind="contradiction_aware", rec=None):
    return {"claim_id": cid, "approach": approach, "approach_kind": kind, "initial_label": initial, "predicted_label": final,
            "verdict_changed": initial != final, "second_look_record": rec}


def test_transitions_hand_computed():
    assert transition(S, C, C) == "incorrect_to_correct" and transition(C, S, C) == "correct_to_incorrect"
    assert transition(S, S, S) == "correct_to_correct" and transition(I, C, S) == "incorrect_to_incorrect"
    gold = {k: {"label": v} for k, v in {"1": C, "2": S, "3": S, "4": I, "5": S}.items()}
    rec = lambda n: {"counterevidence_found": n, "no_counterevidence_found": n == 0, "completed": True}  # noqa: E731
    preds = [_p("1", S, C, rec=rec(2)), _p("2", S, C, rec=rec(1)), _p("3", S, S, rec=rec(0)), _p("4", S, S, rec=rec(0)),
             _p("5", None, I, rec=None)]  # 5: no initial verdict -> excluded from transitions
    r = second_look_metrics(preds, gold)[0]
    assert r["n_labelled"] == 4
    assert (r["incorrect_to_correct"], r["correct_to_incorrect"], r["correct_to_correct"], r["incorrect_to_incorrect"]) == (1, 1, 1, 1)
    assert r["initial_accuracy"] == pytest.approx(2 / 4) and r["final_accuracy"] == pytest.approx(2 / 4)
    assert r["verdict_change_rate"] == pytest.approx(2 / 4) and r["change_precision"] == pytest.approx(1 / 2)
    assert r["net_gain"] == 0 and r["counterevidence_retrieval_success"] == pytest.approx(2 / 4)
    assert r["no_counterevidence_found"] == 2


def test_second_look_metrics_for_single_pass_approaches():
    gold = {"1": {"label": S}}
    r = second_look_metrics([_p("1", S, S, "A2", "financial_verification")], gold)[0]
    assert r["verdict_change_rate"] == 0 and r["counterevidence_retrieval_success"] is None and r["change_precision"] is None


def test_integrity_metrics_detect_leakage_period_issues_and_reference_hits():
    trace_ok = {"claim": {"as_of_date": "2026-05-01"}, "corpus": {"filings": [{"filed": "2026-04-30"}]},
                "evidence": [{"filed": "2026-04-30"}],
                "tool_calls": [{"tool": "verify_numbers", "checks": [{"issues": ["PERIOD_NOT_AVAILABLE:2026-06-30"], "computed": None}]}]}
    trace_leak = {"claim": {"as_of_date": "2026-05-01"}, "corpus": {"filings": [{"filed": "2026-04-30"}]},
                  "evidence": [{"filed": "2026-05-02"}], "tool_calls": []}
    preds = [{"claim_id": "1", "approach": "A", "citations": [{"valid": True, "accession_number": "X"}, {"valid": False}]},
             {"claim_id": "2", "approach": "A", "citations": [{"valid": True, "accession_number": "Y"}]}]
    traces = {("A", "1"): trace_ok, ("A", "2"): trace_leak}
    gold = {"1": {"reference_accessions": ["X"]}, "2": {"reference_accessions": ["Z"]}}
    r = integrity_metrics(preds, traces, gold)[0]
    assert r["citation_validity"] == pytest.approx(2 / 3) and r["future_data_leakage_rate"] == pytest.approx(1 / 2)
    assert r["runs_with_numeric_checks"] == 1 and r["incorrect_fiscal_period_rate"] == 1.0
    assert r["reference_filing_scored"] == 2 and r["reference_filing_hit_rate"] == pytest.approx(1 / 2)
    assert integrity_metrics(preds, None)[0]["future_data_leakage_rate"] is None  # not measured -> not reported


def test_bootstrap_ci_brackets_the_point_estimate():
    y = [S, C, I] * 20
    p = [S, C, S] * 20
    r = bootstrap_ci(y, p, n_boot=500)
    assert r["accuracy"]["point"] == pytest.approx(2 / 3)
    assert r["accuracy"]["ci_low"] <= 2 / 3 <= r["accuracy"]["ci_high"] and r["accuracy"]["ci_high"] - r["accuracy"]["ci_low"] > 0
    assert bootstrap_ci([], [])["n"] == 0
