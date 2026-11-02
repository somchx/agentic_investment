"""Gold-label leakage prevention and experiment configuration isolation."""
import json

import pytest

from engine.config import config_hash, load_config
from engine.datasets import load_annotations
from engine.llm import CachedLLM, ScriptedLLM
from engine.runner import run_experiment, select_claims
from experiments import RUNNERS

CANARY = "CANARY-GOLD-7f3a9c"


def test_annotation_content_never_reaches_the_model(tmp_path, main_cfg, dev_claims, monkeypatch):
    """Write annotations with a canary into a temp annotation dir, run every
    approach, and check no LLM request contains the canary or a gold field."""
    ann_dir = tmp_path / "annotations"
    ann_dir.mkdir()
    (ann_dir / "rev1.jsonl").write_text(json.dumps({
        "claim_id": "DEV-AAPL-04", "reviewer_id": "rev1", "gold_label": "CONTRADICTED", "review_notes": CANARY,
        "contradictory_evidence": [{"accession_number": "0000320193-26-000020", "quote": CANARY}]}) + "\n")
    import engine.datasets as ds
    monkeypatch.setattr(ds, "ANNOTATION_DIR", str(ann_dir))
    assert load_annotations(str(ann_dir))[0].review_notes == CANARY
    scripted = ScriptedLLM({
        "submit_verdict": {"label": "SUPPORTED", "claim_type": "interpretive", "numeric_assertions": [], "supporting_evidence": [],
                           "contradicting_evidence": [], "reasoning_summary": "r"},
        "submit_contradiction_plan": {"hypotheses": [{"hypothesis_id": "H1", "challenge": "c", "search_query": "iPhone net sales"}]},
        "submit_reconciliation": {"assessments": [], "label": "SUPPORTED", "verdict_changed": False, "supporting_evidence": [],
                                  "contradicting_evidence": [], "reasoning_summary": "r"},
        "submit_self_critique": {"weaknesses": [{"weakness_id": "W1", "critique": "c"}]},
        "submit_revision": {"assessments": [], "label": "SUPPORTED", "verdict_changed": False, "supporting_evidence": [],
                            "contradicting_evidence": [], "reasoning_summary": "r"}})
    llm = CachedLLM(mode="mock", inner=scripted)
    claims, info = select_claims(main_cfg, claim_ids=["DEV-AAPL-04"])
    run_experiment(main_cfg, claims, info, llm_mode="mock", llm=llm, runs_dir=str(tmp_path / "runs"), progress=lambda s: None)
    sent = json.dumps(scripted.requests)
    assert scripted.requests and CANARY not in sent
    for field in ("gold_label", "review_notes", "reviewer_id", "adjudication", "claim_category", "difficulty"):
        assert field not in sent


def test_claim_packet_contains_only_whitelisted_fields(main_cfg, dev_claims):
    scripted = ScriptedLLM({"submit_verdict": {"label": "INSUFFICIENT_EVIDENCE", "claim_type": "interpretive", "numeric_assertions": [],
                                               "supporting_evidence": [], "contradicting_evidence": [], "reasoning_summary": "r"}})
    RUNNERS["conventional_rag"](dev_claims["DEV-MSFT-05"].to_input(), main_cfg["approaches"]["A1_conventional_rag"],
                                CachedLLM(mode="mock", inner=scripted))
    text = scripted.requests[0]["messages"][0]["content"][-1]["text"]
    packet = json.loads(text.split("PACKET:", 1)[1])
    assert set(packet["claim"]) == {"claim_id", "company", "claim", "as_of_date", "allowed_sources", "reporting_period"}


def test_gold_split_requires_explicit_permission(main_cfg):
    with pytest.raises(PermissionError):
        select_claims(main_cfg, split="gold")
    claims, info = select_claims(main_cfg, split="gold", allow_gold=True)
    assert info["split"] == "gold"


def test_approach_configs_are_frozen_and_isolated(main_cfg):
    a2, a3 = main_cfg["approaches"]["A2_rag_numeric"], main_cfg["approaches"]["A3_contradiction_aware"]
    with pytest.raises(TypeError):
        a3["contradiction"]["enabled"] = False
    with pytest.raises(TypeError):
        a2["budget"]["max_llm_calls_per_claim"] = 99
    assert a2["contradiction"]["enabled"] is False and a3["contradiction"]["enabled"] is True
    assert config_hash(a2) != config_hash(a3)
    for key in ("llm", "retrieval", "budget"):
        assert dict(a2[key]) == dict(a3[key])


def test_unfair_configs_are_refused():
    base = {"experiment_id": "x", "approaches": [
        {"name": "A2", "kind": "financial_verification"},
        {"name": "A3", "kind": "contradiction_aware", "overrides": {"retrieval": {"top_k": 12}}}]}
    with pytest.raises(ValueError, match="retrieval"):
        load_config(base)
    sr = {"experiment_id": "x", "approaches": [
        {"name": "A3", "kind": "contradiction_aware", "overrides": {"contradiction": {"max_hypotheses": 3}}},
        {"name": "SR", "kind": "self_reflection", "overrides": {"reflection": {"max_items": 5}}}]}
    with pytest.raises(ValueError, match="max_items"):
        load_config(sr)


def test_override_wins_over_kind_switch():
    cfg = load_config("configs/ablation_contradiction.json")
    assert cfg["approaches"]["A3_stage_off"]["contradiction"]["enabled"] is False
    assert cfg["approaches"]["A3_full"]["contradiction"]["enabled"] is True
