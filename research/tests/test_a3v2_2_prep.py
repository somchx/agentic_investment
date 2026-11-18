"""A3 v2.2 preparation: guard 0.2 rules (G3, G6), the decidability schema and gate,
the guard-version config switch and the offline replay. Synthetic findings only;
no claim id appears in any rule."""
import importlib.util
import json
import os

import pytest

from a3v2.config import load_v2_config
from a3v2.decidability import gate, normalize, scope_covered, scope_terms
from a3v2.guard import decide, uncited_references
from engine.config import config_hash

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
ROOT = os.path.join(os.path.dirname(__file__), "..")


def F(fid, relation, ids, justification="", status="VALID", **kw):
    return {"finding_id": fid, "relation": relation, "declared_relation": relation, "evidence_ids": ids, "validation_status": status,
            "justification": justification, "definition_mismatch": False, "downgraded_reason": None, **kw}


def run(findings, proposed="CONTRADICTED", initial="INSUFFICIENT_EVIDENCE", cited=("E1",), version="0.1"):
    check = lambda ledger, claim, period, items: ([{"evidence_id": i["evidence_id"], "issues": []} for i in items], [])  # noqa: E731
    return decide(initial_label=initial, proposed_label=proposed, initial_rule="NOT_APPLICABLE", initial_checks=[],
                  supporting=[{"evidence_id": c, "quote": "q"} for c in cited], contradicting=[], assessments=[],
                  counter_numeric=[], findings=findings, ledger=None, claim=None, period=None, version=version, citation_check=check)


def test_uncited_references():
    assert uncited_references(F("R1", "ENTAILS", ["E7"], "Combined with E10 and E7, … (E12)")) == ["E10", "E12"]
    assert uncited_references(F("R1", "ENTAILS", ["E7"], "E7 states it; SE1 and E7x are not ids")) == []


def test_g3_blocks_finding_whose_reasoning_rests_on_uncited_evidence():
    f = [F("R1", "ENTAILS", ["E1"], "E1 shows growth; combined with E9 this establishes the cause")]
    assert run(f, "SUPPORTED")["outcome"] == "ACCEPT"                       # guard 0.1 unchanged
    d = run(f, "SUPPORTED", version="0.2")
    assert (d["outcome"], d["reason_code"], d["final_label"]) == ("REJECT", "INVALID_DECIDING_EVIDENCE:UNCITED_REFERENCE", "INSUFFICIENT_EVIDENCE")
    assert d["version"] == "a3v2-guard-0.2" and any(t.startswith("G3") for t in d["rule_trace"])
    # another self-contained deciding finding still decides
    f2 = f + [F("R2", "ENTAILS", ["E1"], "E1 alone states the cause")]
    assert run(f2, "SUPPORTED", version="0.2")["reason_code"] == "DECIDING_EVIDENCE_CITED"


def test_g6_conflict_now_blocks_changes_to_contradicted_too():
    f = [F("R1", "CONTRADICTS", ["E1"], "E1 shows a decline"), F("R2", "ENTAILS", ["E1"], "E1 shows growth")]
    assert run(f, "CONTRADICTED")["outcome"] == "ACCEPT"                    # 0.1: only SUPPORTED was checked
    d = run(f, "CONTRADICTED", version="0.2")
    assert (d["reason_code"], d["initial_basis"]) == ("CONFLICTING_DECIDING_EVIDENCE", ["R2"])
    assert run(f, "SUPPORTED")["reason_code"] == "CONFLICTING_DECIDING_EVIDENCE"  # SUPPORTED as before
    assert run([F("R2", "ENTAILS", ["E1"], "E1"), F("R3", "CONTRADICTS", ["E1"], "x", status="PERIOD_MISMATCH")],
               "SUPPORTED", version="0.2")["outcome"] == "ACCEPT"         # only VALID findings conflict


def test_guard_version_switch_keeps_old_hashes():
    with pytest.raises(ValueError):
        run([], version="9.9")
    base = load_v2_config(os.path.join(ROOT, "configs", "a3v2_1_1_dev_v0_2.json"))
    assert {n: config_hash(c)[:8] for n, c in base["approaches"].items()} == \
        {"A2_rag_numeric": "6d298e34", "A3v2_1_1_R": "b2736e77", "A3v2_1_1_RG": "b1ec2fe9"}
    raw = json.load(open(os.path.join(ROOT, "configs", "a3v2_1_1_dev_v0_2.json")))
    rg = next(a for a in raw["approaches"] if a["name"] == "A3v2_1_1_RG")
    rg["overrides"]["guard"] = {"enabled": True, "version": "0.2"}
    cfg = load_v2_config(raw)["approaches"]["A3v2_1_1_RG"]
    assert cfg["versions"]["guard"] == "a3v2-guard-0.2" and config_hash(cfg)[:8] != "b1ec2fe9"
    rg["overrides"]["guard"]["version"] = "0.9"
    with pytest.raises(ValueError, match="guard version"):
        load_v2_config(raw)


def test_decidability_schema_defaults_to_unknown():
    assert normalize(None)["status"] == "UNKNOWN"
    r = normalize({"predicate_type": "VIBES", "criterion_source": 3, "required_evidence": [{"kind": "X"}, "y"]})
    assert r["predicate_type"] == "UNKNOWN" and r["criterion_source"] == "UNKNOWN" and r["required_evidence"] == [] and len(r["issues"]) == 4
    e = normalize({"predicate_type": "EVALUATIVE", "criterion_source": "NONE"})
    assert e["status"] == "NEEDS_CRITERION"
    m = normalize({"predicate_type": "MEASURABLE", "criterion_source": "CLAIM_STATES",
                   "required_evidence": [{"kind": "SCOPE_MATCHED_FACT", "scope": {"region": " Region X ", "segment": ""}}]})
    assert m["status"] == "DECIDABLE" and scope_terms(m) == ["Region X"]


def test_decidability_gate():
    fnd = [{"key_quote": "Global share of category Y fell", "support_mode": "INFERRED", "polarity_match": False}]
    ok = lambda rec, label="CONTRADICTED", f=fnd: gate(normalize(rec), label, f)  # noqa: E731
    assert ok(None) == (True, None)                                                  # UNKNOWN never gates
    assert ok({"predicate_type": "EVALUATIVE", "criterion_source": "NONE"}) == (False, "NO_CRITERION")
    assert ok({"predicate_type": "EVALUATIVE", "criterion_source": "NONE"}, "INSUFFICIENT_EVIDENCE") == (True, None)
    assert ok({"predicate_type": "CAUSAL", "criterion_source": "CLAIM_STATES"}) == (False, "CAUSE_NOT_EXPLICIT")
    assert ok({"predicate_type": "CAUSAL", "criterion_source": "CLAIM_STATES"}, f=[{"support_mode": "EXPLICIT"}]) == (True, None)
    assert ok({"predicate_type": "NEGATIVE", "criterion_source": "CLAIM_STATES"}) == (False, "POLARITY_MISMATCH")
    assert ok({"predicate_type": "NEGATIVE", "criterion_source": "CLAIM_STATES"}, "SUPPORTED") == (True, None)
    scoped = {"predicate_type": "MEASURABLE", "criterion_source": "CLAIM_STATES",
              "required_evidence": [{"kind": "SCOPE_MATCHED_FACT", "scope": {"region": "Region X"}}]}
    assert ok(scoped) == (False, "SCOPE_NOT_COVERED")
    assert ok(scoped, f=[{"key_quote": "Share in region  x rose"}]) == (True, None)
    assert scope_covered([], "anything")


def test_offline_replay_reproduces_recorded_guard_and_never_calls_llm(monkeypatch):
    spec = importlib.util.spec_from_file_location("gr", os.path.join(SCRIPTS, "a3v2_guard_replay.py"))
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    import engine.llm as llm
    monkeypatch.setattr(llm.CachedLLM, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM constructed")))
    rows = [json.loads(x) for x in open(gr.CLAIMS_TABLE)]
    res, mismatches = gr.replay(rows)
    assert mismatches == [] and len(res["preds"]["RG-0.1"]) == len(rows) == 72
    assert all(res["preds"]["RG-0.1"][r["claim_id"]] == r["pred_RG"] for r in rows)
    assert gr.selective("INSUFFICIENT_EVIDENCE", "SUPPORTED", False) == "INSUFFICIENT_EVIDENCE"
    assert gr.selective("INSUFFICIENT_EVIDENCE", "SUPPORTED", True) == "SUPPORTED"
    assert gr.selective("CONTRADICTED", "SUPPORTED", False) == "SUPPORTED"


def test_guard_03_g3b_allows_references_to_surviving_citations_only():
    f = [F("R1", "CONTRADICTS", ["E1"], "E1 shows a fall; compared with E2 this contradicts the claim")]
    assert run(f, cited=("E1", "E2"), version="0.3")["reason_code"] == "DECIDING_EVIDENCE_CITED"      # E2 is a final citation
    d = run(f, cited=("E1",), version="0.3")
    assert d["reason_code"] == "INVALID_DECIDING_EVIDENCE:UNCITED_REFERENCE" and d["version"] == "a3v2-guard-0.3"
    assert run(f, cited=("E1", "E2"), version="0.2")["reason_code"] == "INVALID_DECIDING_EVIDENCE:UNCITED_REFERENCE"  # G3 stricter


def test_quote_check_11_tolerates_stitched_tables_but_not_paraphrase():
    from a3v2.checks import tolerant_quote_status as t
    passage = "RESULTS 2026 2025 Change Segment A Revenue $ 139,996 $ 120,810 16% Cost of revenue 25,017 22,422 12% Operating expenses 31,100 28,615 9%"
    assert t("Segment A Revenue $ 139,996 $ 120,810 16%", passage) == "VERIFIED"
    assert t("Fiscal 2026 Segment A Revenue $ 139,996 $ 120,810 16% Operating expenses 31,100 28,615 9%", passage) == "VERIFIED_NUMBERS"
    assert t("Segment A Revenue $ 139,996 ... Operating expenses 31,100 28,615", passage) == "VERIFIED_FRAGMENTS"
    assert t("Operating expenses 31,100 ... Segment A Revenue $ 139,996", passage) == "NOT_IN_PASSAGE"  # out of order: neither rule
    assert t("Segment A Revenue $ 120,810 $ 139,996", passage) == "NOT_IN_PASSAGE"        # figures out of order
    assert t("Segment A revenue grew strongly in 2026 versus 2025", passage) == "NOT_IN_PASSAGE"  # years are not figures
    assert t("on track", passage + " on track") == "TOO_SHORT"


def test_contribution_checks():
    from a3v2.contribution import largest_factor, parse_bp_bridge, primarily_driven
    assert primarily_driven(9.0, 15.0)["status"] == "TRUE" and primarily_driven(5.0, 15.0)["status"] == "FALSE"
    assert primarily_driven(-1.0, 15.0)["status"] == "FALSE" and primarily_driven(3.0, 0)["status"] == "UNVERIFIABLE"
    bridge = parse_bp_bridge("Margin decreased 100 basis points. The decrease was due to: • 120 basis points of decline from "
                             "unfavorable item mix, • 70 basis points of packaging investments, • 30 basis points of higher input costs. "
                             "These decreases were partially offset by: • 180 basis points of productivity savings.")
    assert [(b["bps"], b["side"]) for b in bridge] == [(120, "main"), (70, "main"), (30, "main"), (180, "offset")]
    assert largest_factor(bridge, ["mix"])["status"] == "TRUE"
    assert largest_factor(bridge, ["packaging"])["status"] == "FALSE"
    assert largest_factor(bridge, ["currency"])["status"] == "NOT_LISTED"
    headline = parse_bp_bridge("Margin decreased 300 basis points to 40.0%. The decrease in margin was due to: 120 basis points of mix, "
                               "90 basis points of input costs")
    assert [b["bps"] for b in headline] == [120, 90] and largest_factor(headline, ["mix"])["status"] == "TRUE"
    tie = parse_bp_bridge("due to: 140 basis points of higher input costs, 140 basis points of packaging investments")
    assert largest_factor(tie, ["input"])["status"] == "TIE"


def test_decidability_classifier_record_and_phase1_gate():
    from a3v2.decidability import DECIDABILITY_TOOL, decidability_request, gate_phase1, record_from_output
    system, messages, tools, mt, choice = decidability_request({"claim": "Co X handled 2030 well.", "company": "X", "reporting_period": "FY2030",
                                                                "claim_category": "ambiguous", "notes": "secret"})
    sent = json.dumps(messages)
    assert "ambiguous" not in sent and "secret" not in sent and tools == [DECIDABILITY_TOOL] and choice["name"] == "classify_claim"
    ev = record_from_output({"predicate_type": "EVALUATIVE", "evaluative_terms": ["well"], "criterion_source": "NONE",
                             "contribution": {"type": "NONE"}, "required_evidence": ["CRITERION_DEFINITION"], "scope": {"region": "Region X"}})
    assert gate_phase1(ev, "CONTRADICTED", ["Operating income fell 15%"]) == (False, "NO_CRITERION")
    assert gate_phase1(ev, "SUPPORTED", ["Management said the year was handled well"]) == (True, None)   # filing uses the word
    assert gate_phase1(ev, "INSUFFICIENT_EVIDENCE", []) == (True, None)
    neg = record_from_output({"predicate_type": "NEGATIVE", "evaluative_terms": [], "criterion_source": "NONE",
                              "contribution": {"type": "NONE"}, "required_evidence": [], "scope": {"region": "Region X"}})
    assert gate_phase1(neg, "CONTRADICTED", ["Global share fell"]) == (True, None)                      # G4 off by default
    assert gate_phase1(neg, "CONTRADICTED", ["Global share fell"], use_scope=True) == (False, "SCOPE_NOT_COVERED")
    assert gate_phase1(neg, "CONTRADICTED", ["Share in Region X fell"], use_scope=True) == (True, None)
    assert record_from_output(None)["status"] == "UNKNOWN" and gate_phase1(record_from_output(None), "SUPPORTED", []) == (True, None)


def test_replay_decidability_policy():
    spec = importlib.util.spec_from_file_location("gr2", os.path.join(SCRIPTS, "a3v2_guard_replay.py"))
    gr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gr)
    from a3v2.decidability import record_from_output
    ev = record_from_output({"predicate_type": "EVALUATIVE", "evaluative_terms": ["strong"], "criterion_source": "NONE",
                             "contribution": {"type": "NONE"}, "required_evidence": []})
    f = [{"validation_status": "VALID", "relation": "CONTRADICTS", "key_quote": "sales fell 5%"},
         {"validation_status": "VALID", "relation": "ENTAILS", "key_quote": "sales rose 5%"}]
    I, S, C = "INSUFFICIENT_EVIDENCE", "SUPPORTED", "CONTRADICTED"
    assert gr.with_decidability(I, C, ev, f, False, False) == (I, "NO_CRITERION")              # G1 reverts the change
    assert gr.with_decidability(C, C, ev, f, False, False) == (C, None)                        # no change, no D
    assert gr.with_decidability(C, C, ev, f, False, True) == (I, "DOWNGRADE_NO_CRITERION")     # D
    assert gr.with_decidability(C, C, ev, f, False, "supported") == (C, None)                  # D-sup keeps CONTRADICTED
    assert gr.with_decidability(S, S, ev, f, False, "supported") == (I, "DOWNGRADE_NO_CRITERION")
    assert gr.with_decidability(S, S, None, f, False, True) == (S, None)                       # no record: untouched


def test_v22_config_switches_and_validation():
    raw = json.load(open(os.path.join(ROOT, "configs", "a3v2_2_dev_v0_2.json")))
    cfg = load_v2_config(raw)["approaches"]["A3v2_2"]
    assert cfg["versions"]["a3v2"] == "a3v2-0.3.0-dev" and cfg["versions"]["quote_check"] == "a3v2-quote-check-1.1"
    assert cfg["versions"]["decidability_prompt"] == "a3v2-decidability-prompt-0.1" and cfg["guard"]["version"] == "0.3"
    arm = next(a for a in raw["approaches"] if a["name"] == "A3v2_2")
    for key, bad, msg in (("decidability", {"name": "llm_9"}, "unknown decidability"),
                          ("decidability", {"name": "llm_0.1", "downgrade": "all"}, "downgrade"),
                          ("quote_check", "2.0", "quote_check"),
                          ("guard", {"enabled": False}, "inside the reconciliation guard")):
        bad_raw = json.loads(json.dumps(raw))
        a = next(x for x in bad_raw["approaches"] if x["name"] == "A3v2_2")
        a["overrides"][key] = bad
        with pytest.raises(ValueError, match=msg):
            load_v2_config(bad_raw)
    assert arm["overrides"]["decidability"]["downgrade"] == "supported"
    # v2.1.1 configs are untouched by the new switches
    old = load_v2_config(os.path.join(ROOT, "configs", "a3v2_1_1_dev_v0_2.json"))["approaches"]["A3v2_1_1_RG"]
    assert "quote_check" not in old["versions"] and "decidability_prompt" not in old["versions"]


def test_quote_revalidation_restores_only_quote_downgrades():
    from a3v2.checks import revalidate_quotes_v11
    passage = "Segment Revenue $ 139,996 $ 120,810 16% Cost 25,017 22,422 12% Operating income $ 83,879 $ 69,773 20%"
    chk = {"evidence_id": "E1", "quote_status": "NOT_IN_PASSAGE", "period_status": "EXACT_MATCH",
           "period_compatibility": {"temporal": "HISTORICAL_FACT"}}
    f = [{"finding_id": "R1", "declared_relation": "ENTAILS", "relation": "RELATED_NOT_DECIDING", "validation_status": "KEY_QUOTE_NOT_IN_EVIDENCE",
          "key_quote": "FY Segment Revenue $ 139,996 $ 120,810 Operating income $ 83,879 $ 69,773", "evidence_type": "OBSERVED_RESULT", "checks": [chk]},
         {"finding_id": "R2", "declared_relation": "ENTAILS", "relation": "RELATED_NOT_DECIDING", "validation_status": "KEY_QUOTE_NOT_IN_EVIDENCE",
          "key_quote": "Segment revenue rose sharply", "evidence_type": "OBSERVED_RESULT", "checks": [chk]},
         {"finding_id": "R3", "declared_relation": "ENTAILS", "relation": "RELATED_NOT_DECIDING", "validation_status": "PERIOD_MISMATCH",
          "key_quote": "x", "evidence_type": "OBSERVED_RESULT", "checks": [chk]}]
    out, restored = revalidate_quotes_v11(f, lambda i: passage, {"orientation": "historical"})
    assert restored == ["R1:VALID"] and out[0]["relation"] == "ENTAILS" and out[1] == f[1] and out[2] == f[2]
    fl = [{**f[0], "checks": [{**chk, "period_compatibility": {"temporal": "FORWARD_LOOKING"}}]}]
    assert revalidate_quotes_v11(fl, lambda i: passage, {"orientation": "historical"})[0][0]["validation_status"] == "FORWARD_LOOKING_FOR_HISTORICAL_CLAIM"


def test_gold_split_needs_a_locked_matching_preregistration(tmp_path, monkeypatch):
    import a3v2.config as ac
    raw = json.load(open(os.path.join(ROOT, "configs", "a3v2_2_dev_v0_2.json")))
    raw["dataset"] = {"split": "gold"}
    with pytest.raises(ValueError, match="no preregistration"):
        load_v2_config(raw)
    monkeypatch.setattr(ac, "RESEARCH_ROOT", str(tmp_path))
    plan = tmp_path / "plan.md"
    plan.write_text("STATUS: DRAFT\n")
    from engine.datasets import file_sha256
    raw["preregistration"] = {"path": "plan.md", "sha256": file_sha256(str(plan))}
    with pytest.raises(ValueError, match="not marked"):
        load_v2_config(raw)
    plan.write_text("STATUS: LOCKED\n")
    with pytest.raises(ValueError, match="changed since"):
        load_v2_config(raw)
    raw["preregistration"]["sha256"] = file_sha256(str(plan))
    assert load_v2_config(raw)["dataset"]["split"] == "gold"


def test_numeric_validity_n1():
    from a3v2.numeric_checks import numeric_validity
    q3 = [{"status": "FALSE", "computed": {"period_end": "2030-08-31"}}]
    q4 = {"end": "2030-11-30", "kind": "duration", "source": "projected", "orientation": "historical"}
    assert numeric_validity("NUMERIC_FALSE", q3, q4, "2030-10-05", None) == ["FUTURE_PERIOD", "PERIOD_MISMATCH"]
    q3p = {"end": "2030-08-31", "kind": "duration", "source": "text_fiscal", "orientation": "historical"}
    assert numeric_validity("NUMERIC_FALSE", q3, q3p, "2030-10-05", None) == []
    assert numeric_validity("NUMERIC_FALSE", q3, q3p, "2030-10-05", {"scope": {"segment": "Segment X"}}) == ["SCOPE_MISMATCH"]
    assert numeric_validity("NUMERIC_PARTIALLY_UNVERIFIABLE", q3, q4, "2030-10-05", None) == []      # not decisive: nothing to undo


def test_numeric_checks_policy_and_fcf_parse(monkeypatch):
    import a3v2.numeric_checks as nc
    I, S, C = "INSUFFICIENT_EVIDENCE", "SUPPORTED", "CONTRADICTED"
    ent = [{"validation_status": "VALID", "relation": "ENTAILS"}]
    both = ent + [{"validation_status": "VALID", "relation": "CONTRADICTS"}]
    na = {"status": "NOT_APPLICABLE"}
    assert nc.apply_numeric_checks(C, "NUMERIC_FALSE", ["SCOPE_MISMATCH"], na, ent, None) == (S, "N1_SCOPE_MISMATCH")
    assert nc.apply_numeric_checks(C, "NUMERIC_FALSE", ["SCOPE_MISMATCH"], na, both, None) == (I, "N1_SCOPE_MISMATCH")
    assert nc.apply_numeric_checks(C, "NUMERIC_FALSE", ["FUTURE_PERIOD"], na, ent, None) == (I, "N1_FUTURE_PERIOD")
    assert nc.apply_numeric_checks(I, "NUMERIC_FALSE", ["SCOPE_MISMATCH"], na, ent, None) == (I, None)   # A2's rule was not kept
    assert nc.apply_numeric_checks(I, None, [], {"status": "FALSE"}, [], None) == (C, "N2_FCF_FALSE")
    assert nc.apply_numeric_checks(I, None, [], {"status": "TRUE"}, [], None) == (I, None)                # TRUE never supports alone
    p = {"kind": "duration", "start": "2030-01-01", "end": "2030-06-30", "months": 6, "comparison": {"start": "2029-01-01", "end": "2029-06-30"}}
    vals = {("OperatingCashFlow", "2030-01-01"): 50, ("CapitalExpenditure", "2030-01-01"): 80,
            ("OperatingCashFlow", "2029-01-01"): 40, ("CapitalExpenditure", "2029-01-01"): 45}
    monkeypatch.setattr(nc, "_window_value", lambda t, m, s, e, c, mo: (vals[(m, s)], []))
    assert nc.fcf_direction_check("Co X's free cash flow improved in H1 2030.", "X", "2030-08-01", p)["status"] == "FALSE"   # -30 vs -5
    assert nc.fcf_direction_check("Co X's free cash flow declined in H1 2030.", "X", "2030-08-01", p)["status"] == "TRUE"
    assert nc.fcf_direction_check("Co X's revenue improved in H1 2030.", "X", "2030-08-01", p)["status"] == "NOT_APPLICABLE"


def test_numeric_checks_config():
    raw = json.load(open(os.path.join(ROOT, "configs", "a3v2_2_dev_v0_2.json")))
    assert load_v2_config(raw)["approaches"]["A3v2_2"]["versions"]["numeric_checks"] == "a3v2-numeric-checks-0.1"
    next(a for a in raw["approaches"] if a["name"] == "A3v2_2")["overrides"]["numeric_checks"] = "9"
    with pytest.raises(ValueError, match="numeric_checks"):
        load_v2_config(raw)


def test_contribution_decision_rules():
    from a3v2.contribution import apply_contribution_b, decide_contribution, decide_contribution_b
    P = {"E1": "Segment A $ 54,252 $ 44,582 Segment B $ 10,000 $ 9,000 Total net sales $ 109,417 $ 94,036",
         "E2": "Margin decreased 100 basis points. The decrease in margin was due to: 120 basis points of decline from unfavorable product mix, "
               "70 basis points of packaging investments. These decreases were partially offset by: 180 basis points of productivity savings."}
    item = lambda n, cur, pri, e, q: {"name": n, "current": cur, "prior": pri, "evidence_id": e, "quote": q}  # noqa: E731
    out = {"test": "PRIMARY_DRIVER", "reported": True, "target": item("Segment A", 54252, 44582, "E1", "Segment A $ 54,252 $ 44,582"),
           "total": item("Total net sales", 109417, 94036, "E1", "Total net sales $ 109,417 $ 94,036"), "other_items": []}
    assert decide_contribution(out, "PRIMARY_DRIVER", P.get)["status"] == "TRUE"                     # 9,670 / 15,381 = 63%
    bad = {**out, "target": item("Segment A", 54252, 40000, "E1", "Segment A $ 54,252 $ 44,582")}
    assert decide_contribution(bad, "PRIMARY_DRIVER", P.get)["status"] == "UNVERIFIED"               # 40,000 not in the quote
    assert decide_contribution({"reported": False, "target": None}, "PRIMARY_DRIVER", P.get)["status"] == "NOT_REPORTED"
    lf = {"test": "LARGEST_FACTOR", "reported": True, "target": item("unfavorable product mix", 120, None, "E2", "120 basis points of decline from unfavorable product mix"),
          "other_items": [item("productivity savings", 180, None, "E2", "180 basis points of productivity savings")]}
    assert decide_contribution(lf, "LARGEST_FACTOR", P.get)["status"] == "FALSE"                     # 0.1 compared across sides
    assert decide_contribution_b(lf, "LARGEST_FACTOR", P.get)["status"] == "TRUE"                    # 0.1b: same side only
    I, S, C = "INSUFFICIENT_EVIDENCE", "SUPPORTED", "CONTRADICTED"
    assert apply_contribution_b(I, {"status": "TRUE"}) == (S, "C_TRUE")
    assert apply_contribution_b(C, {"status": "TRUE"}) == (C, None)                                  # never overrides CONTRADICTED
    assert apply_contribution_b(S, {"status": "FALSE"}) == (C, "C_FALSE")
    assert apply_contribution_b(I, {"status": "UNDECIDED"}) == (I, None)


def test_contribution_config_needs_decidability():
    raw = json.load(open(os.path.join(ROOT, "configs", "a3v2_2_dev_v0_2.json")))
    cfg = load_v2_config(raw)["approaches"]["A3v2_2c"]
    assert cfg["versions"]["contribution_rules"] == "a3v2-contribution-rules-0.1b"
    arm = next(a for a in raw["approaches"] if a["name"] == "A3v2_2c")
    arm["overrides"]["decidability"] = {"name": "not_assessed"}
    with pytest.raises(ValueError, match="needs the decidability"):
        load_v2_config(raw)


# ---- Phase 5 (pre-flight audit): synthetic edge cases for the numeric / contribution / coverage rules
def _item(n, cur, pri, e, q):
    return {"name": n, "current": cur, "prior": pri, "evidence_id": e, "quote": q}


SYN = {"E1": "Segment A $ 600 $ 500 Segment B $ 450 $ 300 Segment C $ 100 $ 150 Total $ 1,150 $ 950",
       "E2": "Operating income $ 900 $ 700 Gain on sale of a business $ 150 $ 0",
       "E3": "Region X revenue $ 300 $ 200 Total revenue $ 1,000 $ 800"}


def test_contribution_edge_cases():
    from a3v2.contribution import decide_contribution, decide_contribution_b
    tot = _item("Total", 1150, 950, "E1", "Total $ 1,150 $ 950")
    a = _item("Segment A", 600, 500, "E1", "Segment A $ 600 $ 500")
    b = _item("Segment B", 450, 300, "E1", "Segment B $ 450 $ 300")
    c = _item("Segment C", 100, 150, "E1", "Segment C $ 100 $ 150")
    pd = lambda t, others, total=tot: decide_contribution({"reported": True, "target": t, "total": total, "other_items": others}, "PRIMARY_DRIVER", SYN.get)  # noqa: E731
    # multiple causes: A explains 100/200 = 50% (not > 50%) and B is larger -> FALSE
    assert pd(a, [b, c])["status"] == "FALSE"
    assert pd(b, [a, c])["status"] == "TRUE"                                     # 150/200 = 75%
    assert pd(c, [a, b])["status"] == "FALSE"                                    # moved against the total
    # missing denominator / incomplete disclosure
    assert pd(a, [b], total=None)["status"] == "UNVERIFIED"
    assert pd(a, [], total=_item("Total", 1150, None, "E1", "Total $ 1,150"))["status"] in ("UNDECIDED", "FALSE", "TRUE")  # level only
    assert decide_contribution({"reported": False, "target": None}, "PRIMARY_DRIVER", SYN.get)["status"] == "NOT_REPORTED"
    # one-time gain: the gain (150 of a 200 rise) is the main driver; the rule reports it, it does not hide it
    oi = _item("Operating income", 900, 700, "E2", "Operating income $ 900 $ 700")
    gain = _item("Gain on sale of a business", 150, 0, "E2", "Gain on sale of a business $ 150 $ 0")
    assert decide_contribution({"reported": True, "target": gain, "total": oi, "other_items": []}, "PRIMARY_DRIVER", SYN.get)["status"] == "TRUE"
    # scope: a figure quoted from another passage than the one it cites is rejected
    wrong_scope = _item("Region X revenue", 300, 200, "E1", "Region X revenue $ 300 $ 200")
    assert pd(wrong_scope, [])["status"] == "UNVERIFIED"
    # same-side comparison for largest factor (0.1b)
    lf = {"reported": True, "target": _item("mix", 50, None, "E9", "50 basis points of unfavorable mix"), "other_items": []}
    bridge = {"E9": "Margin fell. The decrease was due to: 50 basis points of unfavorable mix, 50 basis points of higher costs."}
    assert decide_contribution_b(lf, "LARGEST_FACTOR", bridge.get)["status"] == "UNDECIDED"           # tie


def test_numeric_validity_edge_cases():
    from a3v2.numeric_checks import numeric_validity
    chk = [{"status": "TRUE", "computed": {"period_end": "2030-06-30"}}]
    inst = {"end": "2030-06-30", "kind": "instant", "source": "text_date", "orientation": "historical"}
    assert numeric_validity("NUMERIC_ALL_TRUE", chk, inst, "2030-08-01", None) == []                     # instant, same date
    fwd = {"end": "2031-06-30", "kind": "duration", "source": "text_fiscal", "orientation": "forward"}
    assert "FUTURE_PERIOD" not in numeric_validity("NUMERIC_ALL_TRUE", chk, fwd, "2030-08-01", None)    # forecasts are not "future historical"
    near = {"end": "2030-07-05", "kind": "duration", "source": "text_fiscal", "orientation": "historical"}
    assert numeric_validity("NUMERIC_ALL_TRUE", chk, near, "2030-08-01", None) == []                    # within 10 days (52/53-week years)
    unk = {"end": "2029-06-30", "kind": "duration", "source": "default", "orientation": "historical"}
    assert numeric_validity("NUMERIC_ALL_TRUE", chk, unk, "2030-08-01", None) == []                     # period not stated: no claim to compare


def test_fcf_window_missing_quarter_is_unverifiable(monkeypatch):
    import a3v2.numeric_checks as nc
    p = {"kind": "duration", "start": "2030-01-01", "end": "2030-06-30", "months": 6, "comparison": {"start": "2029-01-01", "end": "2029-06-30"}}
    monkeypatch.setattr(nc, "_window_value", lambda t, m, s, e, c, mo: (None, []) if s.startswith("2029") else (10, []))
    assert nc.fcf_direction_check("X's free cash flow rose in H1 2030.", "X", "2030-08-01", p)["status"] == "UNVERIFIABLE"


def test_coverage_rule():
    from a3v2.numeric_checks import apply_coverage, evidence_basis
    f = [{"validation_status": "VALID", "relation": "ENTAILS"}, {"validation_status": "PERIOD_MISMATCH", "relation": "RELATED_NOT_DECIDING"}]
    assert evidence_basis("SUPPORTED", f, None, [], False) == ["VALID_FINDING"]
    assert evidence_basis("CONTRADICTED", f, None, [], False) == []
    assert evidence_basis("CONTRADICTED", [], "NUMERIC_FALSE", [], False) == ["A2_NUMERIC_RULE"]
    assert evidence_basis("CONTRADICTED", [], "NUMERIC_FALSE", ["SCOPE_MISMATCH"], False) == []          # invalidated by N1
    assert apply_coverage("CONTRADICTED", []) == ("INSUFFICIENT_EVIDENCE", "E1_NO_VALIDATED_BASIS")
    assert apply_coverage("INSUFFICIENT_EVIDENCE", []) == ("INSUFFICIENT_EVIDENCE", None)


def _gold_evaluator():
    spec = importlib.util.spec_from_file_location("a3v2_gold_evaluate", os.path.join(os.path.dirname(__file__), "..", "scripts", "a3v2_gold_evaluate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cached_call_latency_is_the_original_api_latency(tmp_path):
    g = _gold_evaluator()
    key = "ab" + "0" * 62
    os.makedirs(tmp_path / "ab")
    (tmp_path / "ab" / f"{key}.json").write_text(json.dumps({"latency_ms": 9000}))
    assert g._api_latency({"source": "cache", "request_key": key, "latency_ms": 0}, str(tmp_path)) == 9000
    assert g._api_latency({"source": "live", "request_key": key, "latency_ms": 1200}, str(tmp_path)) == 1200
    assert g._api_latency({"source": "cache", "request_key": "cd" + "0" * 62, "latency_ms": 0}, str(tmp_path)) == 0


def test_gold_errors_block_scoring_unless_scored_as_wrong(tmp_path, monkeypatch):
    g = _gold_evaluator()
    run = tmp_path / "r"
    run.mkdir()
    (run / "status.json").write_text(json.dumps({"state": "complete"}))
    (run / "manifest.json").write_text(json.dumps({"dataset": {"split": "gold", "sha256": g.file_sha256(g.GOLD)}}))
    rows = [{"approach": "A2_rag_numeric", "claim_id": f"G-{i}", "predicted_label": "SUPPORTED", "stop_reason": "COMPLETED"} for i in range(150)]
    rows[3] = {**rows[3], "predicted_label": None, "stop_reason": "ERROR"}
    (run / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(g, "RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(g, "verify_run_integrity", lambda d: [])
    with pytest.raises(SystemExit):
        g.load_run("r")
    errors = {}
    preds = g.load_run("r", errors_as_wrong=True, errors=errors)
    assert preds["A2_rag_numeric"]["G-3"] == "ERROR" and len(preds["A2_rag_numeric"]) == 150   # kept, scored wrong, never dropped
    assert errors == {"A2_rag_numeric": ["G-3"]}
