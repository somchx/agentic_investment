"""dev-v0.2 human workflow: blind packages, numeric checklist, provenance and the approval gate.

All fixtures are synthetic files in tmp_path; no real annotation or adjudication file is written.
"""
import importlib.util
import json
import os
import shutil

import pytest
from openpyxl import load_workbook

from engine.datasets import append_adjudication
from engine.schema import Adjudication, SchemaError

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


hw = _load("dev_v0_2_human_workflow")
ev = _load("a3v2_dev_evaluate")


def write_ann(path, rid, labels, note=lambda c: f"independent reasoning for {c} by the test annotator", **extra):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for cid, lab in labels.items():
            f.write(json.dumps({"claim_id": cid, "reviewer_id": rid, "gold_label": lab, "reviewer_type": "human",
                                "review_notes": note(cid), "supporting_evidence": [], "contradictory_evidence": [], **extra}) + "\n")
    return str(path)


def test_blind_package_has_the_44_required_claims_and_detects_leaks(tmp_path):
    out, audit = tmp_path / "blind.xlsx", tmp_path / "audit.json"
    res = hw.blind_package(str(out), str(audit))
    assert res["claims"] == 44 and res["blind"] and sorted(res["required_ids"]) == sorted(hw.required_second())
    assert res["by_type"] == {"interpretive": 19, "ambiguous": 25}
    first_note = hw.first_labels()["DEV-ADBE-01"]["review_notes"]
    for leak in (first_note, "pred_RG", "SUPPORTED"):
        bad = tmp_path / f"leak{len(leak)}.xlsx"
        shutil.copy(out, bad)
        wb = load_workbook(bad)
        cs = wb["Claims"]
        col = [c.value for c in cs[1]].index("✎ เหตุผล / หมายเหตุ\nReview notes") + 1
        cs.cell(2, col, leak)
        wb.save(bad)
        assert not hw.audit_blind_annotation(str(bad), hw.required_second())["blind"], leak


def test_aapl05_packet_is_blind_and_recordable(tmp_path):
    if os.path.exists(hw.ADJ) and "DEV-AAPL-05" in hw.load_adjudications(hw.ADJ):
        with pytest.raises(SystemExit, match="already adjudicated"):
            hw.aapl05_packet(str(tmp_path / "p.xlsx"), str(tmp_path / "a.json"))
        return
    res = hw.aapl05_packet(str(tmp_path / "p.xlsx"), str(tmp_path / "a.json"))
    assert res["blind"] and res["claims"] == 1
    wb = load_workbook(tmp_path / "p.xlsx")
    assert [c.value for c in wb["Adjudication"][1]] == hw.da.HEAD
    assert {"Declaration", "Provenance", "Filings"} <= set(wb.sheetnames)
    row = [c.value for c in wb["Adjudication"][2]]
    assert row[0] == "DEV-AAPL-05" and row[6] == "INSUFFICIENT_EVIDENCE" and row[11] == "SUPPORTED" and row[15:] == [None] * 3


def _fill_numeric(path, verifier, accession=None):
    wb = load_workbook(path)
    wb["คำแนะนำ"]["B2"] = verifier
    cs, ip = wb["Claims"], wb["Inputs"]
    c = hw.claims()["DEV-AAPL-01"]
    acc = accession or hw.dwb.dev_eligible_filings(c, hw.dwb.aw.load_manifest())[-1]["accession_number"]
    form = next(f["form"] for f in hw.dwb.aw.load_manifest() if f["accession_number"] == acc) if accession is None else "10-Q"
    h = hw.NUM_CLAIM_HEAD
    vals = {"✎ Metric(s) the claim tests": "net sales growth", "✎ Formula (use input refs I1, I2 …)": "(I1 - I2) / I2",
            "✎ Computed result": 0.05, "✎ Result unit": "RATIO", "✎ Claim threshold / comparison": "> 0.10",
            "✎ Rounding changes the outcome?": "NO", "✎ Period check": "MATCHES_CLAIM_PERIOD", "✎ Units / scale check": "CONSISTENT",
            "✎ Sources check": "ALL_ELIGIBLE", "✎ Calculation done with": "CALCULATOR", "✎ Verifier conclusion": "CONTRADICTED",
            "✎ Confidence": "HIGH"}
    r = next(i for i in range(2, cs.max_row + 1) if cs.cell(i, 1).value == "DEV-AAPL-01")
    for k, v in vals.items():
        cs.cell(r, h.index(k) + 1, v)
    for i, (ref, pe) in enumerate((("I1", "2026-06-27"), ("I2", "2025-06-28"))):
        row = next(j for j in range(2, ip.max_row + 1) if ip.cell(j, 1).value == "DEV-AAPL-01" and ip.cell(j, 2).value == ref)
        for k, v in {"✎ Line item / XBRL concept": "Net sales", "✎ Value as reported": 100 + i, "✎ Scale": "MILLIONS", "✎ Unit": "USD",
                     "✎ Period end": pe, "✎ Duration": "QUARTER", "✎ Source form": form, "✎ Accession number": acc,
                     "✎ Location in filing": "Income statement"}.items():
            ip.cell(row, hw.NUM_INPUT_HEAD.index(k) + 1, v)
    wb.save(path)


def test_numeric_checklist_round_trip_and_checks(tmp_path):
    p = tmp_path / "num.xlsx"
    ids = hw.numeric_checklist(str(p))
    assert len(ids) == 20 and set(ids) == set(hw.numerical_ids())
    assert hw.audit_workbook(str(p), ids)["blind"]
    ok = tmp_path / "ok.xlsx"
    shutil.copy(p, ok)
    _fill_numeric(ok, "rev_tester")
    rows = hw.read_numeric(str(ok))
    assert [(r["claim_id"], r["gold_label"], r["annotation_kind"], len(r["inputs"])) for r in rows] == \
        [("DEV-AAPL-01", "CONTRADICTED", "numeric_verification", 2)]
    for name, verifier, acc, msg in (("model", "claude-x", None, "verifier id"), ("first", "rev_som", None, "first labeller"),
                                     ("acc", "rev_tester", "0000000000-26-000000", "not an eligible")):
        bad = tmp_path / f"{name}.xlsx"
        shutil.copy(p, bad)
        _fill_numeric(bad, verifier, acc)
        with pytest.raises(SchemaError, match=msg):
            hw.read_numeric(str(bad))


def test_approval_refuses_ai_excluded_and_non_independent_sources(tmp_path):
    ann = tmp_path / "annotations_dev"
    req = hw.required_second()
    first = hw.first_labels()
    same = {c: first[c]["gold_label"] for c in req}
    ai_text = hw.known_ai_texts()[0]
    cases = {
        "ai_codex_dev48": (ann / "a.jsonl", "ai_codex_dev48", {}, "looks like a model"),
        "rev_person3": (ann / "b.jsonl", "rev_person3", {}, "excluded"),
        "llm type": (ann / "c.jsonl", "rev_x", {"reviewer_type": "llm"}, "not 'human'"),
        "copied first notes": (ann / "d.jsonl", "rev_y", {"note": lambda c: first[c]["review_notes"]}, "identical to the first"),
        "copied AI text": (ann / "e.jsonl", "rev_z", {"note": lambda c: ai_text}, "repeats AI-produced text"),
        "design intent path": (ann / "design_intent_x.jsonl", "rev_w", {}, "path marks"),
        "outside annotations": (tmp_path / "results" / "f.jsonl", "rev_v", {}, "must be in"),
    }
    for name, (path, rid, extra, msg) in cases.items():
        note = extra.pop("note", None)
        p = write_ann(path, rid, same, **({"note": note} if note else {}), **extra)
        with pytest.raises(SchemaError, match=msg):
            hw.derive([p], [], adjudication_path=str(tmp_path / "none.jsonl"), ann_dir=str(ann), ai_texts=[ai_text])
    with pytest.raises(SchemaError, match="cannot be approved"):
        hw.approve([], [], "rev_som", str(tmp_path / "x.approved.jsonl"), adjudication_path=str(tmp_path / "none.jsonl"))
    with pytest.raises(SchemaError, match="person's id"):
        hw.approve([], [], "gpt-5", str(tmp_path / "x.approved.jsonl"))
    with pytest.raises(SchemaError, match="approved.jsonl"):
        hw.approve([], [], "rev_som", str(tmp_path / "rev_x.jsonl"))


def test_full_human_path_approves_validates_and_detects_tampering(tmp_path):
    ann = tmp_path / "annotations_dev"
    first = hw.first_labels()
    req = hw.required_second()
    second = {c: first[c]["gold_label"] for c in req}
    second["DEV-ADBE-01"] = "SUPPORTED" if first["DEV-ADBE-01"]["gold_label"] != "SUPPORTED" else "CONTRADICTED"
    sp = write_ann(ann / "rev_second.jsonl", "rev_second", second)
    npth = write_ann(ann / "numcheck_rev_num.jsonl", "rev_num", {c: first[c]["gold_label"] for c in hw.numerical_ids()},
                     annotation_kind="numeric_verification")
    adj = str(tmp_path / "adjudications.jsonl")
    open(adj, "w").close()
    ok, missing = hw.derive([sp], [npth], adjudication_path=adj, ann_dir=str(ann))
    assert set(missing) == set(hw.MUST_ADJUDICATE) | {"DEV-ADBE-01"} and missing["DEV-ADBE-01"].startswith("DISAGREED")
    for cid in [*hw.MUST_ADJUDICATE, "DEV-ADBE-01"]:
        append_adjudication(Adjudication(claim_id=cid, adjudicator_id="rev_third", final_label="INSUFFICIENT_EVIDENCE",
                                         decision_notes="test decision", considered_reviewers=["a", "b"]), adj)
    out = str(tmp_path / "dev.approved.jsonl")
    m = hw.approve([sp], [npth], "rev_som", out, adjudication_path=adj, ann_dir=str(ann))
    assert m["claims_approved"] == 72 and m["label_status"] == {"AGREED": 66, "ADJUDICATED": 6} and not m["partial"]
    assert hw.validate(out, ann_dir=str(ann)) == []
    labels, cov = ev.load_reference(out, set(hw.claims()))
    assert cov["labelled"] == 72 and not cov["partial"]
    rows = [json.loads(x) for x in open(out)]
    rows[0]["final_label"] = "SUPPORTED" if rows[0]["final_label"] != "SUPPORTED" else "CONTRADICTED"
    os.chmod(out, 0o644)
    with open(out, "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    assert any("changed after approval" in p for p in hw.validate(out, ann_dir=str(ann)))
    handmade = tmp_path / "hand.approved.jsonl"
    shutil.copy(out, handmade)
    assert any("not produced by `approve`" in p for p in hw.validate(str(handmade)))


def test_provenance_marks_ai_affected_claims_and_kappa_subsets():
    rows = {r["claim_id"]: r for r in hw.provenance_rows()}
    assert len(rows) == 72
    assert {c for c, r in rows.items() if r["ai_exposure_flags"]} == set(hw.AI_AFFECTED)
    from collections import Counter
    assert Counter(r["kappa_subset"] for r in rows.values()) == {"PRIMARY_44": 44, "NUMERICAL_VERIFICATION": 20, "HISTORICAL_DEV_V0_1": 8}
    assert rows["DEV-AAPL-07"]["first_label_for_kappa"] == "CONTRADICTED"  # pre-review v3, not v4
    assert all(r["approval_route"].startswith("ADJUDICATION") for c, r in rows.items() if c in hw.MUST_ADJUDICATE)
