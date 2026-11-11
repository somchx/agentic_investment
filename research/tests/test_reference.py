"""Final Gold reference labels: loading, validation, provenance, and that no
part of them can reach an approach."""
import json
import os
import shutil

import pytest
from openpyxl import load_workbook

from engine import RESEARCH_ROOT
from engine.datasets import file_sha256, load_split
from engine.llm import CachedLLM, ScriptedLLM
from engine.reference import REFERENCE_PATH, REFERENCE_SHEET, accessions_in, load_reference, normalize_label, validate_reference
from engine.schema import ClaimInput, SchemaError
from graphs import run_graph

from test_approaches import CRITIQUE, PLAN, keep, verdict


@pytest.fixture(scope="module")
def ref():
    return load_reference()


def _copy_with(tmp_path, edit):
    path = tmp_path / "ref.xlsx"
    shutil.copy(REFERENCE_PATH, path)
    wb = load_workbook(path)
    edit(wb[REFERENCE_SHEET])
    wb.save(path)
    return str(path)


def test_reference_loads_all_150_with_provenance(ref):
    labels, prov = ref["labels"], ref["provenance"]
    assert len(labels) == 150 and set(labels) == {c.claim_id for c in load_split("gold")}
    assert {e["label"] for e in labels.values()} <= {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}
    assert prov["independent_human_gold"] is False and prov["sha256"] == file_sha256(REFERENCE_PATH)
    assert prov["label_source"] == "llm_annotated_ai_adjudicated_researcher_reviewed"
    # passage-level gold evidence is not exposed: quotes are not verbatim-verified
    assert all(e["supporting_evidence"] == [] and e["contradictory_evidence"] == [] for e in labels.values())


def test_loading_never_modifies_the_workbook():
    before = file_sha256(REFERENCE_PATH)
    load_reference()
    assert file_sha256(REFERENCE_PATH) == before


def test_label_normalisation_is_case_and_space_only():
    assert normalize_label(" supported ") == "SUPPORTED"
    for bad in ("SUPPORT", "INSUFFICIENT", "", None, "true"):
        with pytest.raises(SchemaError):
            normalize_label(bad)


def test_invalid_label_and_duplicate_id_are_errors(tmp_path):
    with pytest.raises(SchemaError, match="not one of"):
        load_reference(_copy_with(tmp_path, lambda ws: ws.cell(row=2, column=6, value="PROBABLY")))
    with pytest.raises(SchemaError, match="duplicate claim id"):
        load_reference(_copy_with(tmp_path, lambda ws: ws.cell(row=3, column=1, value=ws.cell(row=2, column=1).value)))


def test_normalised_labels_are_reported(tmp_path):
    r = load_reference(_copy_with(tmp_path, lambda ws: ws.cell(row=2, column=6, value=" supported")))
    assert r["provenance"]["label_normalisations"] == [{"claim_id": "GOLD-AAPL-01", "raw": " supported", "label": "SUPPORTED"}]


def test_validation_of_the_real_reference(ref):
    v = validate_reference(load_split("gold"), ref)
    assert v["errors"] == []
    assert sorted(v["future_period_claims"]) == ["GOLD-AAPL-04", "GOLD-AMZN-05", "GOLD-MSFT-05", "GOLD-NVDA-05", "GOLD-WMT-05"]
    assert any("not verbatim-verified" in w for w in v["warnings"])
    assert any("not independent human gold" in w for w in v["warnings"])


def test_validation_catches_mismatches_and_unobservable_decisive_labels(tmp_path):
    def edit(ws):
        ws.cell(row=2, column=4, value="A different claim text.")      # GOLD-AAPL-01
        ws.cell(row=5, column=6, value="SUPPORTED")                    # GOLD-AAPL-04 (future period)
    v = validate_reference(load_split("gold"), load_reference(_copy_with(tmp_path, edit)))
    assert any("GOLD-AAPL-01: claim text differs" in e for e in v["errors"])
    assert any("GOLD-AAPL-04: period not observable" in e for e in v["errors"])


def test_accession_parsing():
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000006/aapl-20251227.htm"
    assert accessions_in(url + " ; " + url) == ["0000320193-26-000006"]
    assert accessions_in(None) == []


def test_claim_input_cannot_carry_reference_fields():
    with pytest.raises(SchemaError):
        ClaimInput.from_record({"claim_id": "X1", "company": "AAPL", "claim": "c", "as_of_date": "2026-01-01",
                                "final_label": "SUPPORTED"})


def test_agent_code_never_imports_the_reference():
    for sub in ("graphs", "experiments"):
        d = os.path.join(RESEARCH_ROOT, sub)
        for name in os.listdir(d):
            if name.endswith(".py"):
                src = open(os.path.join(d, name)).read()
                assert "engine.reference" not in src and "import reference" not in src, name
                assert "workbooks" not in src and "Final_Gold" not in src, name


@pytest.mark.parametrize("kind", ["contradiction_aware", "self_reflection"])
def test_reference_content_never_reaches_the_model(ref, main_cfg, kind):
    claims = {c.claim_id: c for c in load_split("gold")}
    name = {"contradiction_aware": "A3_contradiction_aware", "self_reflection": "SR_self_reflection"}[kind]
    for cid in ("GOLD-AAPL-08", "GOLD-TSLA-03"):
        scripted = ScriptedLLM({"submit_verdict": verdict(), "submit_contradiction_plan": PLAN, "submit_reconciliation": keep("SUPPORTED"),
                                "submit_self_critique": CRITIQUE, "submit_revision": keep("SUPPORTED")})
        llm = CachedLLM(mode="mock", inner=scripted, model=main_cfg["common"]["llm"]["model"])
        run_graph(kind, claims[cid].to_input(), main_cfg["approaches"][name], llm, "test")
        sent = json.dumps(scripted.requests, ensure_ascii=False)
        entry = ref["labels"][cid]
        for secret in (entry["rationale"], entry["vote_pattern"], entry["qa_status"], "Final_Gold", "label_source"):
            assert secret and secret[:40] not in sent
        assert "claim_category" not in sent and "difficulty" not in sent  # dataset design fields are withheld
