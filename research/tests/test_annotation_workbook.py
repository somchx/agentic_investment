"""Reviewer workbook: export carries no labels; import validates and never overwrites."""
import importlib.util
import os

import pytest
from openpyxl import load_workbook

from engine.datasets import DEV_PATH, load_annotations
from engine.schema import SchemaError

_spec = importlib.util.spec_from_file_location(
    "annotation_workbook", os.path.join(os.path.dirname(__file__), "..", "scripts", "annotation_workbook.py"))
aw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aw)


@pytest.fixture
def blank(tmp_path):
    path = tmp_path / "blank.xlsx"
    aw.export([DEV_PATH], str(path))
    return path


def _fill(path, out, evidence, labels, reviewer="rev_test"):
    wb = load_workbook(path)
    sheet, ref = next(wb.defined_names["ReviewerID"].destinations)
    wb[sheet][ref.replace("$", "")] = reviewer
    claims = wb["Claims"]
    row_of = {claims.cell(row=r, column=1).value: r for r in range(2, claims.max_row + 1)}
    label_col = next(c.column for c in claims[1] if c.value == aw.H_LABEL)
    for cid, label in labels.items():
        claims.cell(row=row_of[cid], column=label_col, value=label)
    for i, ev in enumerate(evidence, start=2):
        for j, v in enumerate(ev, start=1):
            wb["Evidence"].cell(row=i, column=j, value=v)
    wb.save(out)
    return out


def test_export_has_every_claim_and_no_label_values(blank):
    wb = load_workbook(blank)
    claims = wb["Claims"]
    ids = [claims.cell(row=r, column=1).value for r in range(2, claims.max_row + 1)]
    assert len(ids) == 24 and ids[0] == "DEV-AAPL-01"
    label_col = next(c.column for c in claims[1] if c.value == aw.H_LABEL)
    assert all(claims.cell(row=r, column=label_col).value is None for r in range(2, claims.max_row + 1))
    assert "ReviewerID" in wb.defined_names


def test_each_claim_links_only_its_eligible_sec_filings(blank):
    claims = load_workbook(blank)["Claims"]
    link_cols = [c.column for c in claims[1] if str(c.value).startswith("🔗")]
    cutoff_col = 7
    for r in range(2, claims.max_row + 1):
        claim = next(c for c in aw.load_claims(DEV_PATH) if c.claim_id == claims.cell(row=r, column=1).value)
        expected = {aw.filing_url(f) for f in aw.eligible_filings(claim, aw.load_manifest())}
        links = {claims.cell(row=r, column=c).hyperlink.target for c in link_cols if claims.cell(row=r, column=c).hyperlink}
        assert links == expected and expected, claim.claim_id
        assert all(u.startswith("https://www.sec.gov/Archives/edgar/data/") for u in links)
        assert claims.cell(row=r, column=cutoff_col).value is not None


def test_eligible_filings_respect_cutoff_and_company():
    claim = next(c for c in aw.load_claims(DEV_PATH) if c.claim_id == "DEV-AAPL-08")  # cutoff 2026-05-15
    elig = aw.eligible_filings(claim, aw.load_manifest())
    assert elig and all(f["company"] == "AAPL" and f["filed"] <= "2026-05-15" for f in elig)
    assert "0000320193-26-000020" not in {f["accession_number"] for f in elig}  # filed 2026-07-31


def test_round_trip_writes_valid_annotations(blank, tmp_path):
    filled = _fill(blank, tmp_path / "f.xlsx",
                   [("DEV-AAPL-01", "supporting", "filing_passage", "0000320193-26-000020", "MD&A", "Total net sales increased.")],
                   {"DEV-AAPL-01": "SUPPORTED", "DEV-AAPL-02": "INSUFFICIENT_EVIDENCE"})
    out_dir = tmp_path / "annotations"
    target = aw.import_workbook(str(filled), [DEV_PATH], str(out_dir))
    anns = {a.claim_id: a for a in load_annotations(str(out_dir))}
    assert os.path.basename(target) == "rev_test.jsonl" and set(anns) == {"DEV-AAPL-01", "DEV-AAPL-02"}
    ev = anns["DEV-AAPL-01"].supporting_evidence[0]
    assert ev["form"] == "10-Q" and ev["quote"] == "Total net sales increased."
    with pytest.raises(SchemaError, match="already exists"):
        aw.import_workbook(str(filled), [DEV_PATH], str(out_dir))


@pytest.mark.parametrize("evidence,labels,message", [
    ([("DEV-AAPL-08", "supporting", "filing_passage", "0000320193-26-000020", "x", "q")],
     {"DEV-AAPL-08": "SUPPORTED"}, "not an eligible filing"),
    ([("DEV-AAPL-01", "supporting", "filing_passage", "0001018724-26-000026", "x", "q")],
     {"DEV-AAPL-01": "SUPPORTED"}, "not an eligible filing"),
    ([], {"DEV-AAPL-01": "CONTRADICTED"}, "has no evidence row"),
    ([("DEV-AAPL-01", "supporting", "filing_passage", "0000320193-26-000020", "x", None)],
     {"DEV-AAPL-01": "SUPPORTED"}, "verbatim quote"),
])
def test_invalid_rows_reject_whole_workbook(blank, tmp_path, evidence, labels, message):
    filled = _fill(blank, tmp_path / "f.xlsx", evidence, labels)
    with pytest.raises(SchemaError, match=message):
        aw.import_workbook(str(filled), [DEV_PATH], str(tmp_path / "annotations"))
    assert not (tmp_path / "annotations").exists()


def test_model_like_reviewer_id_is_rejected(blank, tmp_path):
    filled = _fill(blank, tmp_path / "f.xlsx", [], {"DEV-AAPL-02": "INSUFFICIENT_EVIDENCE"}, reviewer="claude-annotator")
    with pytest.raises(SchemaError, match="looks like a model"):
        aw.read_workbook(str(filled), [DEV_PATH])
