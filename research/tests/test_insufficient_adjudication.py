"""Blind adjudication of decisive answers on INSUFFICIENT_EVIDENCE claims:
export hides approach names, import validates, scoring uses only ACCEPTABLE."""
import importlib.util
import json
import os

import pytest
from openpyxl import load_workbook

from engine.reference import correct
from engine.schema import SchemaError
from engine.stats import compare_correctness

_spec = importlib.util.spec_from_file_location(
    "insufficient_adjudication", os.path.join(os.path.dirname(__file__), "..", "scripts", "insufficient_adjudication.py"))
ia = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ia)


def test_correct_uses_only_acceptable_alternatives():
    gold = {"C1": {"label": "INSUFFICIENT_EVIDENCE"}, "C2": {"label": "SUPPORTED"}}
    p = {"claim_id": "C1", "approach": "A3", "predicted_label": "SUPPORTED"}
    assert not correct(p, gold) and not correct(p, gold, {})
    assert correct(p, gold, {("C1", "A3"): "ACCEPTABLE"})
    assert not correct(p, gold, {("C1", "A3"): "UNSURE"}) and not correct(p, gold, {("C1", "A2"): "ACCEPTABLE"})
    wrong = {"claim_id": "C2", "approach": "A3", "predicted_label": "CONTRADICTED"}
    assert not correct(wrong, gold, {("C2", "A3"): "ACCEPTABLE"})  # only INSUFFICIENT references can be relaxed


def test_compare_correctness():
    r = compare_correctness([True, True, False, False], [True, False, True, True], n_boot=200)
    assert r["mcnemar"]["b_right_a_wrong"] == 2 and r["mcnemar"]["a_right_b_wrong"] == 1
    assert r["accuracy_diff"]["diff_b_minus_a"] == pytest.approx(0.25)


def _fake_key(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "ADJ_DIR", str(tmp_path))
    key = {"run_id": "R", "cases": {"GOLD-X-01-A": {"claim_id": "GOLD-X-01", "label": "SUPPORTED", "approaches": ["A1", "A2"]},
                                    "GOLD-X-01-B": {"claim_id": "GOLD-X-01", "label": "CONTRADICTED", "approaches": ["A3"]}}}
    json.dump(key, open(ia.key_path("R"), "w"))


def _workbook(tmp_path, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Cases"
    ws.append(ia.COLUMNS)
    for cid, label, decision in rows:
        r = [None] * len(ia.COLUMNS)
        r[0], r[ia.COLUMNS.index("Answer label")], r[ia.COLUMNS.index(ia.H_DECISION)] = cid, label, decision
        ws.append(r)
    path = tmp_path / "filled.xlsx"
    wb.save(path)
    return str(path)


def test_import_maps_letters_back_to_approaches(tmp_path, monkeypatch):
    _fake_key(tmp_path, monkeypatch)
    out = ia.import_workbook(_workbook(tmp_path, [("GOLD-X-01-A", "SUPPORTED", "acceptable"),
                                                 ("GOLD-X-01-B", "CONTRADICTED", "NOT_ACCEPTABLE")]), "R", "tester", "adjudicated")
    rows = [json.loads(line) for line in open(out)]
    assert rows[0]["approaches"] == ["A1", "A2"] and rows[0]["decision"] == "ACCEPTABLE" and rows[0]["variant"] == "adjudicated"
    with pytest.raises(SchemaError, match="exists"):
        ia.import_workbook(_workbook(tmp_path, []), "R", "tester", "adjudicated")
    # a second, differently named scoring of the same cases is kept alongside
    both = ia.import_workbook(_workbook(tmp_path, [("GOLD-X-01-A", "SUPPORTED", "ACCEPTABLE"),
                                                  ("GOLD-X-01-B", "CONTRADICTED", "ACCEPTABLE")]), "R", "tester", "lenient")
    assert os.path.exists(out) and os.path.exists(both) and out != both
    with pytest.raises(SchemaError, match="variant"):
        ia.import_workbook(_workbook(tmp_path, []), "R", "tester", "Bad Name")


@pytest.mark.parametrize("rows,msg", [
    ([("GOLD-X-01-A", "SUPPORTED", "ACCEPTABLE")], "missing cases"),
    ([("GOLD-X-01-A", "SUPPORTED", None), ("GOLD-X-01-B", "CONTRADICTED", "UNSURE")], "without a decision"),
    ([("GOLD-X-01-A", "CONTRADICTED", "ACCEPTABLE"), ("GOLD-X-01-B", "CONTRADICTED", "UNSURE")], "edited"),
])
def test_import_rejects_incomplete_or_edited_workbooks(tmp_path, monkeypatch, rows, msg):
    _fake_key(tmp_path, monkeypatch)
    with pytest.raises(SchemaError, match=msg):
        ia.import_workbook(_workbook(tmp_path, rows), "R", "tester", "adjudicated")


def test_exported_workbook_hides_approach_names():
    path = os.path.join(ia.ADJ_DIR, "INSUFFICIENT_adjudication__claimverif-main-v1-20261110T104207Z.xlsx")
    if not os.path.exists(path):
        pytest.skip("no exported workbook")
    text = " ".join(str(c) for ws in load_workbook(path).worksheets for row in ws.iter_rows(values_only=True) for c in row if c)
    for name in ("conventional_rag", "financial_verification", "contradiction_aware", "A1_", "A2_", "A3_"):
        assert name not in text
