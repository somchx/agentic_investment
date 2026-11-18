"""dev-v0.2 evaluation pipeline: consolidation of the A3 v2.1.1 runs, the
approved-label gate and paired metrics, the evidence-review workbook and the
label-status report. Labels used here are synthetic test input in a temp
directory, never reference labels."""
import importlib.util
import json
import os

import pytest
from openpyxl import load_workbook

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


con, ev, wbk, ls = (_load(n) for n in ("a3v2_dev_consolidate", "a3v2_dev_evaluate", "a3v2_evidence_review_workbook", "dev_v0_2_label_status"))


@pytest.fixture(scope="module")
def rows():
    r, meta = con.consolidate()
    return r, meta


def test_consolidation_has_72_claims_and_216_completed_predictions(rows):
    r, meta = rows
    assert len(r) == 72 == len({x["claim_id"] for x in r}) and meta["predictions"] == 216
    assert all(x[k] == "COMPLETED" for x in r for k in ("stop_reason_A2", "stop_reason_R", "stop_reason_RG"))
    assert all(json.loads(x["rg_llm_sources"]) == {"cache": json.loads(x["rg_llm_sources"]).get("cache", 0)} for x in r)  # RG cache-only
    assert sum(x["R_changed_vs_A2"] for x in r) == 22 and sum(x["RG_changed_vs_A2"] for x in r) == 12


def test_consolidation_refuses_a_run_listed_twice():
    with pytest.raises(SystemExit, match="duplicates"):
        con.consolidate(list(con.DEFAULT_RUNS) + [con.DEFAULT_RUNS[0]])


def write_labels(tmp_path, rows, label_of, name="ref.approved.jsonl", **over):
    p = tmp_path / name
    with open(p, "w") as f:
        for x in rows:
            f.write(json.dumps({"claim_id": x["claim_id"], "final_label": label_of(x), "label_status": "AGREED", "approved_by": "test",
                                "approved_at": "2026-11-18", "source": "synthetic test", **over}) + "\n")
    return str(p)


def test_label_gate_refuses_reviewer_files_unapproved_and_partial(tmp_path, rows):
    r, _ = rows
    ids = {x["claim_id"] for x in r}
    with pytest.raises(ev.NotApproved, match="not an approved"):
        ev.load_reference(write_labels(tmp_path, r, lambda x: "SUPPORTED", name="rev_som.v4.jsonl"), ids)
    with pytest.raises(ev.NotApproved, match="not approved"):
        ev.load_reference(write_labels(tmp_path, r, lambda x: "SUPPORTED", name="a.jsonl", label_status="SINGLE"), ids)
    p = write_labels(tmp_path, r[:10], lambda x: "SUPPORTED", name="b.jsonl")
    with pytest.raises(ev.NotApproved, match="no approved label"):
        ev.load_reference(p, ids)
    _, cov = ev.load_reference(p, ids, allow_partial=True)
    assert cov["partial"] and cov["labelled"] == 10


def test_metrics_on_synthetic_labels(tmp_path, rows):
    r, _ = rows
    labels, cov = ev.load_reference(write_labels(tmp_path, r, lambda x: x["pred_RG"]), {x["claim_id"] for x in r})
    res = ev.evaluate(r, labels, n_boot=200)
    assert res["overall"]["RG"]["accuracy"] == 1.0 and res["paired"]["A2_vs_RG"]["mcnemar"]["b_right_a_wrong"] == 12
    assert res["vs_A2"]["RG"]["correction"]["k"] == 12 and res["vs_A2"]["RG"]["regression"]["k"] == 0
    g = res["guard"]
    assert g["r_changes"] == 22 and g["decisions"].get("helpful_block", 0) == 10 and g["decisions"].get("helpful_accept", 0) == 12
    assert sum(m["n"] for m in res["by_claim_type"].values()) == 72
    assert "UNANIMOUS" in res["vote_patterns"]["approach_agreement"]


def test_guard_classification_and_statistics():
    rows = [{"claim_id": "a", "claim_type": "ambiguous", "pred_A2": "INSUFFICIENT_EVIDENCE", "pred_R": "SUPPORTED", "pred_RG": "INSUFFICIENT_EVIDENCE", "guard_reason": "CONTEXT_ONLY"},
            {"claim_id": "b", "claim_type": "ambiguous", "pred_A2": "INSUFFICIENT_EVIDENCE", "pred_R": "SUPPORTED", "pred_RG": "SUPPORTED", "guard_reason": "DECIDING_EVIDENCE_CITED"}]
    labels = {"a": {"final_label": "SUPPORTED"}, "b": {"final_label": "INSUFFICIENT_EVIDENCE"}}
    g = ev.evaluate(rows, labels, n_boot=50)["guard"]
    assert g["decisions"] == {"harmful_block": 1, "harmful_accept": 1} and g["net_helpful_legacy"] == -2 and g["rg_minus_r"] == -1 and g["rg_minus_a2"] == -1
    assert ev.wilson(0, 0)["rate"] is None and abs(ev.wilson(5, 10)["ci_low"] - 0.2366) < 1e-3
    assert abs(ev.fisher_exact(3, 1, 1, 3)["p_value"] - 0.4857) < 1e-3


def test_evidence_workbook_has_no_labels_and_round_trips(tmp_path):
    out = str(tmp_path / "w.xlsx")
    n = wbk.export(out)
    assert n["claims"] == 72 and n["findings"] >= n["p1"] > 0
    wb = load_workbook(out)
    text = " ".join(str(c.value) for s in ("Findings", "Claims") for row in wb[s].iter_rows() for c in row if c.value is not None)
    assert "pred_RG" not in text and "final_label" not in text and "design_intent" not in text
    ws = wb["Findings"]
    head = [c.value for c in ws[1]]
    ws.cell(2, head.index("✎ Evidence relevance") + 1, "IRRELEVANT")
    ws.cell(2, head.index("✎ Temporal compatibility") + 1, "DIFFERENT_DURATION")
    wb["คำแนะนำ"]["B8"] = "codex-x"
    wb.save(out)
    with pytest.raises(SystemExit, match="looks like a model"):
        wbk.import_review(out, str(tmp_path / "rev"))
    wb["คำแนะนำ"]["B8"] = "human_a"
    ws.cell(3, head.index("✎ Evidence relevance") + 1, "MAYBE")
    wb.save(out)
    with pytest.raises(SystemExit, match="problems"):
        wbk.import_review(out, str(tmp_path / "rev"))
    ws.cell(3, head.index("✎ Evidence relevance") + 1).value = None
    wb.save(out)
    p = wbk.import_review(out, str(tmp_path / "rev"))
    got = [json.loads(x) for x in open(p)]
    assert len(got) == 1 and got[0]["Evidence relevance"] == "IRRELEVANT" and got[0]["reviewer_id"] == "human_a"


def test_label_status_report():
    rows = ls.status_rows()
    st = {r["claim_id"]: r for r in rows}
    assert len(rows) == 72 and st["DEV-AAPL-05"]["status"] in ("DISAGREED", "ADJUDICATED")
    assert st["DEV-AAPL-05"]["needs_adjudication"] == (st["DEV-AAPL-05"]["status"] == "DISAGREED")
    # every claim still SINGLE in this (pre-second-annotation) status view and ambiguous / interpretive needs a second label
    assert all(r["needs_second_annotation"] == (r["status"] == "SINGLE" and r["claim_type"] != "numerical") for r in rows)
