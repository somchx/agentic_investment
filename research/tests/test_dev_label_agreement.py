"""Second-review tooling: the blind export carries only the chosen claims and
no labels; the agreement script compares two reviewers without changing either
file. Annotation rows here are synthetic test input in a temp directory."""
import importlib.util
import json
import os
import re

import pytest
from openpyxl import load_workbook

from engine.datasets import cohen_kappa

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


daw, agr = _load("dev_annotation_workbook"), _load("dev_label_agreement")
BLIND = ["DEV-AAPL-05", "DEV-AAPL-07", "DEV-MSFT-05", "DEV-MSFT-06", "DEV-MSFT-07", "DEV-AMZN-05", "DEV-AMZN-06", "DEV-AMZN-07"]


def test_blind_export_has_only_selected_blank_claims(tmp_path):
    out = tmp_path / "blind.xlsx"
    assert daw.export(str(out), ids=BLIND) == 8
    wb = load_workbook(out)
    cs = wb["Claims"]
    h = {c.value: c.column for c in cs[1]}
    assert [cs.cell(row=r, column=1).value for r in range(2, cs.max_row + 1)] == BLIND
    inputs = [daw.aw.H_LABEL, daw.aw.H_NOTES, *[x for x, _ in daw.DEV_COLUMNS]]
    assert all(cs.cell(row=r, column=h[x]).value is None for r in range(2, 10) for x in inputs)
    sheet, ref = next(wb.defined_names["ReviewerID"].destinations)
    assert wb[sheet][ref.replace("$", "")].value in (None, "")
    text = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None)
    assert not re.search(r"rev_som(?!chai)", text)  # "rev_somchai" is the template's example reviewer id
    with pytest.raises(SystemExit, match="unknown claim ids"):
        daw.export(str(tmp_path / "x.xlsx"), ids=["DEV-NOPE-01"])


def _write(path, reviewer, labels):
    with open(path, "w", encoding="utf-8") as f:
        for cid, lab in labels.items():
            f.write(json.dumps({"claim_id": cid, "reviewer_id": reviewer, "gold_label": lab, "confidence": "MEDIUM",
                                "uncertainty_type": "NONE"}) + "\n")
    return str(path)


def test_agreement_on_shared_claims(tmp_path):
    a = _write(tmp_path / "a.jsonl", "rev_a", {"C1": "SUPPORTED", "C2": "CONTRADICTED", "C3": "INSUFFICIENT_EVIDENCE", "C4": "SUPPORTED"})
    b = _write(tmp_path / "b.jsonl", "rev_b", {"C1": "SUPPORTED", "C2": "INSUFFICIENT_EVIDENCE", "C3": "INSUFFICIENT_EVIDENCE", "C9": "SUPPORTED"})
    before = open(a, encoding="utf-8").read(), open(b, encoding="utf-8").read()
    res = agr.compare(agr.load(a), agr.load(b), n_boot=200)
    assert res["n_shared"] == 3 and res["only_a"] == ["C4"] and res["only_b"] == ["C9"]
    assert res["raw_agreement"] == pytest.approx(2 / 3)
    assert res["cohen_kappa"] == pytest.approx(cohen_kappa([("SUPPORTED", "SUPPORTED"), ("CONTRADICTED", "INSUFFICIENT_EVIDENCE"),
                                                             ("INSUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE")]))
    assert [d["claim_id"] for d in res["disagreements"]] == ["C2"]
    assert (open(a, encoding="utf-8").read(), open(b, encoding="utf-8").read()) == before


def test_agreement_refuses_same_reviewer_and_overwrite(tmp_path):
    a = _write(tmp_path / "a.jsonl", "rev_a", {"C1": "SUPPORTED"})
    with pytest.raises(SystemExit, match="same reviewer"):
        agr.compare(agr.load(a), agr.load(a))
    b = _write(tmp_path / "b.jsonl", "rev_b", {"C1": "SUPPORTED"})
    out = tmp_path / "res.json"
    agr.main([a, b, "--out", str(out)])
    with pytest.raises(SystemExit, match="exists"):
        agr.main([a, b, "--out", str(out)])
