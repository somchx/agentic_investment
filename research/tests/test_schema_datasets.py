"""Claim input validation, dataset loading, split separation, gold assembly."""
import json

import pytest

from engine.datasets import (ADJUDICATED, AGREED, DISAGREED, PENDING, SINGLE, append_adjudication, bootstrap_agreement,
                             check_split_separation, cohen_kappa, finalized_gold, fleiss_kappa, gold_status,
                             krippendorff_alpha_nominal, load_adjudications, load_claims, load_split)
from engine.schema import Adjudication, Annotation, ClaimInput, DatasetClaim, SchemaError


def base(**kw):
    return {"claim_id": "T1", "company": "AAPL", "claim": "Revenue grew.", "as_of_date": "2026-08-15", **kw}


def test_claim_input_accepts_task_example():
    c = ClaimInput.from_record({"claim_id": "FC001", "company": "AAPL",
                                "claim": "The company's operating profitability improved because its core operations became more efficient.",
                                "as_of_date": "2026-06-30", "allowed_sources": ["SEC_10K", "SEC_10Q"]})
    assert c.allowed_forms() >= {"10-K", "10-Q"}
    assert "8-K" not in c.allowed_forms()


@pytest.mark.parametrize("bad", [
    {"claim_id": "bad id!"}, {"company": "aapl"}, {"claim": ""}, {"as_of_date": "30/06/2026"},
    {"allowed_sources": ["WEB"]}, {"allowed_sources": []},
])
def test_claim_input_rejects_invalid(bad):
    with pytest.raises(SchemaError):
        ClaimInput.from_record(base(**bad))


def test_claim_input_refuses_annotation_fields():
    for field in ("gold_label", "review_notes", "supporting_evidence", "dev_label"):
        with pytest.raises(SchemaError, match="annotation fields"):
            ClaimInput.from_record(base(**{field: "SUPPORTED"}))


def test_development_dataset_loads_and_is_unlabelled():
    dev = load_split("development")
    assert len(dev) >= 20
    assert {c.company for c in dev} == {"AAPL", "MSFT", "AMZN"}
    assert {c.claim_category for c in dev} == {"numerical", "interpretive", "ambiguous"}
    raw = open("datasets/development_cases.jsonl").read()
    assert "gold_label" not in raw and "dev_label" not in raw


def test_split_mismatch_and_duplicates_rejected(tmp_path):
    p = tmp_path / "x.jsonl"
    row = {**base(), "claim_category": "numerical", "split": "gold"}
    p.write_text(json.dumps(row) + "\n")
    with pytest.raises(SchemaError, match="split"):
        load_claims(str(p), expected_split="development")
    p.write_text((json.dumps({**row, "split": "development"}) + "\n") * 2)
    with pytest.raises(SchemaError, match="duplicate"):
        load_claims(str(p))


def test_split_separation_detects_overlap():
    d = DatasetClaim(**base(), claim_category="numerical", split="development")
    g = DatasetClaim(**{**base(claim_id="T2"), "claim": "  revenue GREW. "}, claim_category="numerical", split="gold")
    assert any("duplicates development" in p for p in check_split_separation([d], [g]))


def test_model_reviewers_rejected():
    with pytest.raises(SchemaError, match="model"):
        Annotation("T1", "claude-sonnet", "SUPPORTED")
    with pytest.raises(SchemaError, match="human"):
        Annotation("T1", "rev1", "SUPPORTED", reviewer_type="llm")


def _claims(n):
    return [DatasetClaim(**base(claim_id=f"C{i}"), claim_category="numerical", split="gold") for i in range(n)]


def test_gold_status_and_finalization():
    claims = _claims(5)
    ev = [{"accession_number": "0000320193-26-000020", "quote": "Total net sales increased"}]
    anns = [Annotation("C0", "r1", "SUPPORTED", supporting_evidence=ev), Annotation("C0", "r2", "SUPPORTED", supporting_evidence=ev),
            Annotation("C1", "r1", "SUPPORTED"), Annotation("C1", "r2", "CONTRADICTED"),
            Annotation("C2", "r1", "INSUFFICIENT_EVIDENCE"),
            Annotation("C3", "r1", "SUPPORTED", supporting_evidence=ev), Annotation("C3", "r2", "CONTRADICTED")]
    adj = {"C3": Adjudication("C3", "adj", "SUPPORTED", "r2 misread the period")}
    status = {r["claim_id"]: r for r in gold_status(claims, anns, adj)}
    assert [status[f"C{i}"]["adjudication_status"] for i in range(5)] == [AGREED, DISAGREED, SINGLE, ADJUDICATED, PENDING]
    assert status["C1"]["reviewers_missing_evidence"] == ["r1", "r2"]
    final = finalized_gold(claims, anns, adj)
    assert set(final) == {"C0", "C3"}
    assert final["C3"]["label"] == "SUPPORTED" and len(final["C3"]["supporting_evidence"]) == 1


def test_adjudication_is_append_once(tmp_path):
    path = str(tmp_path / "adj.jsonl")
    append_adjudication(Adjudication("C1", "adj", "SUPPORTED", "reason"), path)
    with pytest.raises(SchemaError, match="already adjudicated"):
        append_adjudication(Adjudication("C1", "adj", "CONTRADICTED", "changed mind"), path)
    assert load_adjudications(path)["C1"].final_label == "SUPPORTED"


def test_cohen_kappa():
    assert cohen_kappa([("A", "A"), ("B", "B")]) == 1.0
    assert cohen_kappa([("A", "B"), ("B", "A")]) == -1.0
    assert cohen_kappa([]) is None


# Expected values from statsmodels.stats.inter_rater.fleiss_kappa and the `krippendorff` package.
THREE_RATERS = [["A", "A", "B"], ["A", "A", "A"], ["B", "B", "B"], ["C", "B", "C"], ["A", "C", "C"], ["B", "B", "A"]]


def test_fleiss_kappa():
    assert fleiss_kappa(THREE_RATERS) == pytest.approx(0.3142857142857143)
    assert fleiss_kappa([["A", "A", "A"], ["B", "B", "B"]]) == 1.0
    assert fleiss_kappa([]) is None
    with pytest.raises(ValueError):
        fleiss_kappa([["A", "A"], ["A", "B", "B"]])


def test_krippendorff_alpha_nominal():
    assert krippendorff_alpha_nominal(THREE_RATERS) == pytest.approx(0.35238095238095246)
    with_missing = [["A", "A", None], ["A", "B", "B"], ["C", None, None], ["B", "B", "B"], [None, "C", "C"]]
    assert krippendorff_alpha_nominal(with_missing) == pytest.approx(0.7096774193548387)
    assert krippendorff_alpha_nominal([["A", None]]) is None


def test_bootstrap_agreement_is_reproducible_and_brackets_estimate():
    lo, hi = bootstrap_agreement(THREE_RATERS * 5, fleiss_kappa, n_boot=300)
    assert (lo, hi) == bootstrap_agreement(THREE_RATERS * 5, fleiss_kappa, n_boot=300)
    assert lo <= fleiss_kappa(THREE_RATERS * 5) <= hi
