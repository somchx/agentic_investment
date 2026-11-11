"""Researcher-confirmation workbook for the discordant-case review: export
leaves the researcher columns empty and flags DEBATABLE cases; import
copies only those columns and refuses edited analyst columns."""
import csv
import importlib.util
import os

import pytest
from openpyxl import Workbook, load_workbook

from engine.schema import SchemaError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("drw", os.path.join(ROOT, "scripts", "discordant_review_workbook.py"))
drw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drw)

RUN = "claimverif-main-v1-20261110T104207Z"
FIELDS = ["claim_id", "mechanism", "counterevidence_genuine", "interpretation_correct", "final_citations_entail_verdict",
          "note", "reviewer", "researcher_confirmed", "researcher_note"]


def test_flag_and_trace_text():
    assert drw.flag({"interpretation_correct": "DEBATABLE"}) == "CLOSER REVIEW"
    assert drw.flag({"interpretation_correct": "NO"}) is None
    pred = {"contradiction": {
        "hypotheses": [{"hypothesis_id": "H1", "challenge": "Did margin fall?", "search_query": "margin"}],
        "queries": [{"hypothesis_id": "H1", "query": "operating margin 2025"}],
        "assessments": [{"item_id": "H1", "assessment": "CHALLENGE_REFUTED",
                         "evidence": [{"evidence_id": "E7", "kind": "filing_passage", "form": "10-K", "filed": "2025-10-31",
                                       "period_end": "2025-09-27", "valid": False, "issues": ["QUOTE_NOT_IN_PASSAGE"],
                                       "quote": "Net income $ 112,010"}]}],
        "guard_reverted": "CHANGE_TO_SUPPORTED_WITHOUT_VALID_EVIDENCE"}}
    t = drw.contradiction_text(pred)
    assert "query: operating margin 2025" in t and "-> CHALLENGE_REFUTED" in t
    assert "INVALID QUOTE_NOT_IN_PASSAGE" in t and "Guard reverted" in t
    assert "no final verdict" in drw.contradiction_text({"contradiction": {"hypotheses": []}})


def _setup(tmp_path, monkeypatch):
    csv_path = tmp_path / "review.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for cid in ("C1", "C2"):
            w.writerow({"claim_id": cid, "mechanism": "TERM_MISREADING", "counterevidence_genuine": "YES",
                        "interpretation_correct": "NO", "final_citations_entail_verdict": "NO", "note": "n",
                        "reviewer": "AI", "researcher_confirmed": "", "researcher_note": ""})
    monkeypatch.setattr(drw, "review_path", lambda run_id: str(csv_path))
    wb = Workbook()
    ws = wb.active
    ws.title = "Cases"
    ws.append(["Claim ID", "Proposed mechanism", "Counter-evidence genuine?", "Interpretation correct?",
               "Final citations entail verdict?", drw.H_CONFIRM, drw.H_NOTE])
    ws.append(["C1", "TERM_MISREADING", "YES", "NO", "NO", "confirmed", "agree"])
    ws.append(["C2", "TERM_MISREADING", "YES", "NO", "NO", None, None])
    return csv_path, wb, ws


def test_import_copies_only_researcher_columns(tmp_path, monkeypatch):
    csv_path, wb, _ = _setup(tmp_path, monkeypatch)
    wb.save(tmp_path / "filled.xlsx")
    drw.import_workbook(str(tmp_path / "filled.xlsx"), RUN)
    rows = {r["claim_id"]: r for r in csv.DictReader(open(csv_path, encoding="utf-8"))}
    assert rows["C1"]["researcher_confirmed"] == "CONFIRMED" and rows["C1"]["researcher_note"] == "agree"
    assert rows["C2"]["researcher_confirmed"] == "" and rows["C1"]["mechanism"] == "TERM_MISREADING"


@pytest.mark.parametrize("cell,value,msg", [("B2", "LEVEL_VS_CHANGE", "analyst column"), ("F2", "MAYBE", "not one of")])
def test_import_refuses_bad_workbooks(tmp_path, monkeypatch, cell, value, msg):
    _, wb, ws = _setup(tmp_path, monkeypatch)
    ws[cell] = value
    wb.save(tmp_path / "bad.xlsx")
    with pytest.raises(SchemaError, match=msg):
        drw.import_workbook(str(tmp_path / "bad.xlsx"), RUN)


@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "results", "runs", RUN)), reason="frozen v1 run not present")
def test_export_of_frozen_run(tmp_path):
    out = drw.export(RUN, str(tmp_path / "review.xlsx"))
    ws = load_workbook(out)["Cases"]
    head = [c.value for c in ws[1]]
    rows = [dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True)]
    assert len(rows) == 23
    assert sorted(r["Claim ID"] for r in rows if r["Review flag"]) == ["GOLD-AAPL-12", "GOLD-KO-11", "GOLD-MSFT-13"]
    assert all(r[drw.H_CONFIRM] is None and r[drw.H_NOTE] is None for r in rows)
    assert {r["Outcome"] for r in rows} == {"A2 only correct", "A3 only correct"}
    assert all(r["Contradiction trace"] and r["Reference label"] for r in rows)
