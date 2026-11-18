"""Development annotation workbook: export carries no labels and only
development claims; import keeps the gold-workflow validation and records the
uncertainty fields separately from gold annotations. Rows filled here are
synthetic test input in a temp directory, not labels."""
import importlib.util
import json
import os

import pytest
from openpyxl import load_workbook

from engine.schema import SchemaError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("daw", os.path.join(ROOT, "scripts", "dev_annotation_workbook.py"))
daw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daw)


@pytest.fixture
def blank(tmp_path):
    out = tmp_path / "dev.xlsx"
    assert daw.export(str(out)) == 24
    return out


def headers(ws):
    return {c.value: c.column for c in ws[1]}


def test_export_is_blank_development_only(blank):
    wb = load_workbook(blank)
    assert wb.sheetnames[:2] == ["คำแนะนำ", "เกณฑ์ Dev"]
    cs = wb["Claims"]
    h = headers(cs)
    ids = [cs.cell(row=r, column=1).value for r in range(2, cs.max_row + 1)]
    assert len(ids) == 24 and all(i.startswith("DEV-") for i in ids)
    inputs = [daw.aw.H_LABEL, daw.aw.H_NOTES, *[x for x, _ in daw.DEV_COLUMNS]]
    assert all(cs.cell(row=r, column=h[x]).value is None for r in range(2, 26) for x in inputs)
    lists = {str(d.sqref): d.formula1 for d in cs.data_validations.dataValidation}
    assert any("HIGH,MEDIUM,LOW" in f for f in lists.values()) and any("UNDEFINED_PREDICATE" in f for f in lists.values())
    assert "Development" in wb["คำแนะนำ"]["A1"].value


def fill(path, label, conf="MEDIUM", utype="CAUSE_NOT_STATED", evidence=True, accn=None):
    wb = load_workbook(path)
    sheet, ref = next(wb.defined_names["ReviewerID"].destinations)
    wb[sheet][ref.replace("$", "")] = "rev_test"
    cs = wb["Claims"]
    h = headers(cs)
    row = next(r for r in range(2, cs.max_row + 1) if cs.cell(row=r, column=1).value == "DEV-AMZN-04")
    elig = cs.cell(row=row, column=9).value.split("\n")[0]
    accn = accn or elig.split("(")[1].rstrip(")")
    cs.cell(row=row, column=h[daw.aw.H_LABEL], value=label)
    cs.cell(row=row, column=h[daw.aw.H_NOTES], value="synthetic test row")
    cs.cell(row=row, column=h[daw.H_CONF], value=conf)
    cs.cell(row=row, column=h[daw.H_UTYPE], value=utype)
    if evidence:
        es = wb["Evidence"]
        for c, v in enumerate(["DEV-AMZN-04", "supporting", "filing_passage", accn, "MD&A", "synthetic quote for the test"], start=1):
            es.cell(row=2, column=c, value=v)
    wb.save(path)


def test_import_roundtrip_writes_dev_dir_with_uncertainty(blank, tmp_path):
    fill(blank, "SUPPORTED")
    target = daw.import_dev(str(blank), annotation_dir=str(tmp_path / "annotations_dev"))
    rows = [json.loads(line) for line in open(target, encoding="utf-8")]
    assert len(rows) == 1 and rows[0]["claim_id"] == "DEV-AMZN-04" and rows[0]["split"] == "development"
    assert rows[0]["confidence"] == "MEDIUM" and rows[0]["uncertainty_type"] == "CAUSE_NOT_STATED"
    assert rows[0]["reviewer_type"] == "human" and rows[0]["supporting_evidence"]
    with pytest.raises(SchemaError, match="not overwritten"):
        daw.import_dev(str(blank), annotation_dir=str(tmp_path / "annotations_dev"))


@pytest.mark.parametrize("kw,msg", [({"conf": "SURE"}, "confidence must be"), ({"conf": None}, "confidence is required"),
                                    ({"evidence": False}, "no evidence row")])
def test_import_rejects_bad_rows(blank, tmp_path, kw, msg):
    fill(blank, "SUPPORTED", **kw)
    with pytest.raises(SchemaError, match=msg):
        daw.import_dev(str(blank), annotation_dir=str(tmp_path / "a"))


def test_negative_claim_uncertainty_type(blank, tmp_path):
    lists = [d.formula1 for d in load_workbook(blank)["Claims"].data_validations.dataValidation]
    assert any("NEGATIVE_CLAIM" in f for f in lists) and all(len(f) <= 257 for f in lists)  # Excel list limit
    fill(blank, "SUPPORTED", utype="NEGATIVE_CLAIM")
    rows = [json.loads(x) for x in open(daw.import_dev(str(blank), annotation_dir=str(tmp_path / "a")), encoding="utf-8")]
    assert rows[0]["uncertainty_type"] == "NEGATIVE_CLAIM"


def _filings(company, **kw):
    return [f for f in daw.aw.load_manifest() if f["company"] == company and all(f[k] == v for k, v in kw.items())]


def test_dev_rule_accepts_older_same_company_filing(blank, tmp_path):
    """DEV-AMZN-04 (cutoff 2026-08-15): the Q2 2025 10-Q is outside the system's retrieval set but filed before the cutoff."""
    claim = next(c for c in daw.load_claims(daw.DEV_PATH) if c.claim_id == "DEV-AMZN-04")
    old = next(f for f in _filings("AMZN", form="10-Q") if f["report_date"] == "2025-06-30")
    assert old not in daw.aw.eligible_filings(claim, daw.aw.load_manifest())  # gold / system rule: not eligible
    assert old in daw.dev_eligible_filings(claim, daw.aw.load_manifest())
    fill(blank, "SUPPORTED", accn=old["accession_number"])
    rows = [json.loads(x) for x in open(daw.import_dev(str(blank), annotation_dir=str(tmp_path / "a")), encoding="utf-8")]
    assert rows[0]["evidence_outside_system_corpus"] == [old["accession_number"]]
    assert daw.aw.eligible_filings.__name__ == "eligible_filings"  # gold rule restored after import


@pytest.mark.parametrize("pick", ["after_cutoff", "other_company"])
def test_dev_rule_still_rejects_bad_filings(blank, tmp_path, pick):
    accn = (next(f for f in _filings("AMZN") if f["filed"] > "2026-08-15") if pick == "after_cutoff"
            else _filings("AAPL", form="10-Q")[0])["accession_number"]
    fill(blank, "SUPPORTED", accn=accn)
    with pytest.raises(SchemaError, match="not an eligible filing"):
        daw.import_dev(str(blank), annotation_dir=str(tmp_path / "a"))


def test_versioned_import_keeps_earlier_file(blank, tmp_path):
    fill(blank, "SUPPORTED")
    d = tmp_path / "a"
    first = daw.import_dev(str(blank), annotation_dir=str(d))
    before = open(first, encoding="utf-8").read()
    second = daw.import_dev(str(blank), annotation_dir=str(d), version="v2")
    assert os.path.basename(second) == "rev_test.v2.jsonl" and open(first, encoding="utf-8").read() == before
    row = json.loads(open(second, encoding="utf-8").readline())
    assert row["annotation_version"] == "v2" and len(row["source_workbook_sha256"]) == 64
    with pytest.raises(SchemaError, match="not overwritten"):
        daw.import_dev(str(blank), annotation_dir=str(d), version="v2")
    with pytest.raises(SchemaError, match="letters, digits"):
        daw.import_dev(str(blank), annotation_dir=str(d), version="../x")
