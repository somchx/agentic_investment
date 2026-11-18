"""Dev adjudication (packet, append-only record, status) and claim authoring
(template, validation, versioned build). Rows written here are synthetic test
input in a temp directory, not labels or dataset claims."""
import importlib.util
import json
import os

import pytest
from openpyxl import load_workbook

from engine.schema import SchemaError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


adj, auth = _load("dev_adjudication"), _load("dev_claims_authoring")


def _ann(path, reviewer, labels):
    with open(path, "w", encoding="utf-8") as f:
        for cid, lab in labels.items():
            f.write(json.dumps({"claim_id": cid, "reviewer_id": reviewer, "gold_label": lab, "review_notes": "n", "confidence": "HIGH",
                                "uncertainty_type": "NONE", "supporting_evidence": [], "contradictory_evidence": []}) + "\n")
    return str(path)


def test_adjudication_packet_record_and_status(tmp_path):
    a = _ann(tmp_path / "a.jsonl", "rev_a", {"DEV-AAPL-01": "SUPPORTED", "DEV-AAPL-05": "INSUFFICIENT_EVIDENCE", "DEV-MSFT-01": "SUPPORTED"})
    b = _ann(tmp_path / "b.jsonl", "rev_b", {"DEV-AAPL-01": "SUPPORTED", "DEV-AAPL-05": "SUPPORTED"})
    packet = tmp_path / "packet.xlsx"
    assert adj.export(a, b, str(packet)) == ["DEV-AAPL-05"]
    ws = load_workbook(packet)["Adjudication"]
    assert ws.cell(2, 1).value == "DEV-AAPL-05" and all(ws.cell(2, c).value is None for c in (16, 17, 18))
    store = str(tmp_path / "adjudications.jsonl")
    st = {r["claim_id"]: r["status"] for r in adj.status(a, b, store)}
    assert st == {"DEV-AAPL-01": "AGREED", "DEV-AAPL-05": "DISAGREED", "DEV-MSFT-01": "SINGLE"}
    wb = load_workbook(packet)
    for col, v in ((16, "rev_a"), (17, "SUPPORTED"), (18, "test")):
        wb["Adjudication"].cell(2, col).value = v
    wb.save(packet)
    with pytest.raises(SchemaError, match="must not be one of the reviewers"):
        adj.record(str(packet), store)
    wb["Adjudication"].cell(2, 16).value = "claude-x"
    wb.save(packet)
    with pytest.raises(SchemaError, match="looks like a model"):
        adj.record(str(packet), store)
    wb["Adjudication"].cell(2, 16).value = "adj_c"
    wb.save(packet)
    assert adj.record(str(packet), store) == ["DEV-AAPL-05"]
    assert {r["claim_id"]: r["status"] for r in adj.status(a, b, store)}["DEV-AAPL-05"] == "ADJUDICATED"
    with pytest.raises(SchemaError, match="already adjudicated"):
        adj.record(str(packet), store)


def _authoring(tmp_path, rows):
    out = tmp_path / "author.xlsx"
    auth.template(str(out))
    wb = load_workbook(out)
    ws = wb["Claims"]
    ws.delete_rows(2)
    for r in rows:
        ws.append(r)
    wb.save(out)
    return str(out)


ROW = ["DEV-ZZZ-01", "ZZZ", "ZZZ's results for the quarter ended March 31, 2027 show disciplined cost management.", "ambiguous", "2027 Q1",
       "2027-05-15", "SEC_10K,SEC_10Q", "medium", "EVALUATIVE_NO_CRITERION", "INSUFFICIENT_EVIDENCE", "author_x", ""]


def test_authoring_validation_rules(tmp_path):
    gold_copy = list(ROW)
    gold_copy[0], gold_copy[1] = "DEV-NVDA-50", "NVDA"
    gold_copy[2] = auth.load_claims(auth.GOLD_PATH)[0].claim.replace("Apple", "NVIDIA")
    bad_intent = list(ROW)
    bad_intent[0], bad_intent[9] = "DEV-ZZZ-02", "PROBABLY"
    res = auth.validate(_authoring(tmp_path, [ROW, gold_copy, bad_intent]))
    assert res["valid"] == 1 and res["rows"][0]["claim_id"] == "DEV-ZZZ-01"
    assert any("gold company" in e for e in res["errors"]) and any("design_intent" in e for e in res["errors"])
    assert any("NEEDS_DOWNLOAD" in w for w in res["warnings"])


def test_build_writes_new_version_and_separate_intent(tmp_path):
    path = _authoring(tmp_path, [ROW])
    claims, intent = auth.build(path, "dev-test", out_dir=str(tmp_path))
    rows = [json.loads(x) for x in open(claims, encoding="utf-8")]
    assert len(rows) == 25 and rows[-1]["claim_id"] == "DEV-ZZZ-01" and "design_intent" not in rows[-1]
    assert json.loads(open(intent, encoding="utf-8").readline())["design_intent"] == "INSUFFICIENT_EVIDENCE"
    with pytest.raises(SchemaError, match="exists"):
        auth.build(path, "dev-test", out_dir=str(tmp_path))


def test_near_duplicate_of_a_gold_claim_is_blocked(tmp_path):
    g = auth.load_claims(auth.GOLD_PATH)[0]
    row = list(ROW)
    row[2] = g.claim.replace(g.company, "ZZZ").replace("Apple", "ZZZ")
    assert auth.similarity(row[2], g.claim) >= auth.NEAR_DUPLICATE
    res = auth.validate(_authoring(tmp_path, [row]))
    assert res["valid"] == 0 and "too similar" in res["errors"][0]


def test_dev_manifest_is_separate_from_the_frozen_one(tmp_path, monkeypatch):
    corpus = _load("dev_corpus")
    frozen = [{"company": "AAPL", "form": "10-Q", "filed": "2026-07-31", "accession_number": "A-1"}]
    extra = [{"company": "ADBE", "form": "10-Q", "filed": "2026-09-22", "accession_number": "B-1"},
             {"company": "AAPL", "form": "10-Q", "filed": "2026-07-31", "accession_number": "A-1"}]
    (tmp_path / "corpus_manifest.json").write_text(json.dumps(frozen))
    (tmp_path / "corpus_manifest_dev-x.json").write_text(json.dumps(extra))
    monkeypatch.setattr(corpus, "DATASET_DIR", str(tmp_path))
    monkeypatch.setattr(corpus, "FROZEN_MANIFEST", str(tmp_path / "corpus_manifest.json"))
    assert [r["accession_number"] for r in corpus.load_manifest()] == ["A-1", "B-1"]
    assert corpus.manifest_path("dev-x").endswith("corpus_manifest_dev-x.json")
    assert auth.aw.load_manifest is auth.dev_corpus.load_manifest


def test_research_ciks_extend_the_app_list_without_changing_it():
    from engine.corpus import ALL_KNOWN_CIKS, RESEARCH_CIKS, _cik
    assert _cik("ADBE") == "0000796343" and _cik("AAPL") == ALL_KNOWN_CIKS["AAPL"].zfill(10)
    assert not set(RESEARCH_CIKS) & set(ALL_KNOWN_CIKS)


def test_built_claims_record_the_author(tmp_path):
    claims, _ = auth.build(_authoring(tmp_path, [ROW]), "dev-test2", out_dir=str(tmp_path))
    last = json.loads(open(claims, encoding="utf-8").readlines()[-1])
    assert "drafted by author_x" in last["notes"]
