"""SEC retrieval, evidence cutoff enforcement and deterministic numeric checks
(real cached SEC data, no network)."""
import pytest

from engine.corpus import RetrievalConfig, Retriever, eligible_filings
from engine.numeric import reconcile_label, verify_assertion
from engine.schema import ClaimInput
from evidence_ledger import EvidenceLedger


def claim(company="AMZN", as_of="2026-08-15", sources=("SEC_10K", "SEC_10Q"), text="AWS operating income increased"):
    return ClaimInput("T1", company, text, as_of, tuple(sources))


def test_eligible_filings_respect_cutoff_and_forms():
    late = {f["accession_number"] for f in eligible_filings("AMZN", "2026-08-15", {"10-Q", "10-K"}, {"10-Q": 9, "10-K": 9})}
    early = eligible_filings("AMZN", "2026-05-15", {"10-Q", "10-K"}, {"10-Q": 9, "10-K": 9})
    assert all(f["filed"] <= "2026-05-15" for f in early)
    assert "0001018724-26-000026" in late  # Q2 10-Q filed 2026-07-31
    assert "0001018724-26-000026" not in {f["accession_number"] for f in early}
    only_q = eligible_filings("AMZN", "2026-08-15", {"10-Q"}, {"10-Q": 2})
    assert {f["form"] for f in only_q} == {"10-Q"} and len(only_q) == 2


def test_retrieval_returns_registered_point_in_time_passages():
    ledger = EvidenceLedger()
    r = Retriever(claim(), RetrievalConfig(), ledger)
    hits = r.search("AWS segment operating income increase")
    assert hits and len(hits) <= 6
    for h in hits:
        unit = ledger.get(h["evidence_id"])
        assert unit.kind == "filing_passage" and unit.ticker == "AMZN"
        assert unit.filed <= "2026-08-15" and unit.excerpt
        assert h["chunk_id"].startswith(unit.accession_number)
    assert any("aws" in h["text"].lower() for h in hits)


def test_retrieval_cannot_see_filings_after_cutoff():
    r = Retriever(claim(as_of="2026-05-15"), RetrievalConfig(), EvidenceLedger())
    assert all(f["filed"] <= "2026-05-15" for f in r.filings)
    assert all(p.filing["filed"] <= "2026-05-15" for p in r.passages)


def test_exclude_shown_returns_new_passages():
    r = Retriever(claim(), RetrievalConfig(), EvidenceLedger())
    first = {h["chunk_id"] for h in r.search("AWS operating income", top_k=3)}
    second = {h["chunk_id"] for h in r.search("AWS operating income", top_k=3, exclude_shown=True)}
    assert first and second and not first & second


def test_chunk_ids_are_stable():
    a = [h["chunk_id"] for h in Retriever(claim(), RetrievalConfig(), EvidenceLedger()).search("net sales")]
    b = [h["chunk_id"] for h in Retriever(claim(), RetrievalConfig(), EvidenceLedger()).search("net sales")]
    assert a == b


# ------------------------------------------------------------- numeric

def check(company, cutoff, **a):
    return verify_assertion(company, cutoff, {"period_end": None, "threshold": None, "stated_value": None, **a}, EvidenceLedger())


def test_revenue_growth_is_deterministic_and_reuses_app_extraction(monkeypatch):
    import tools
    from engine.numeric import company_facts
    monkeypatch.setattr(tools, "get_company_facts", company_facts)  # same frozen file, no TTL refresh
    r1 =check("AAPL", "2026-08-15", metric="Revenue", measure="yoy_growth", period_basis="quarter", comparison=">", threshold=0.10)
    r2 = check("AAPL", "2026-08-15", metric="Revenue", measure="yoy_growth", period_basis="quarter", comparison=">", threshold=0.10)
    assert r1["computed"] == r2["computed"]
    assert r1["status"] == "TRUE" and r1["computed"]["period_end"] == "2026-06-27"
    # the application's rule engine computes the same growth
    app =tools.check_reason_status("AAPL", "revenue_growth", as_of="2026-08-15")
    assert abs(app["computed_value"] - r1["computed"]["yoy_change"]) < 1e-9


def test_false_threshold_and_stated_value_mismatch():
    r = check("AMZN", "2026-08-15", metric="OperatingMargin", measure="level", period_basis="quarter", comparison=">", threshold=0.30)
    assert r["status"] == "FALSE"
    r = check("AAPL", "2026-08-15", metric="Revenue", measure="yoy_growth", period_basis="quarter", comparison="approximately", stated_value=0.50)
    assert r["status"] == "FALSE" and any("STATED_VALUE_MISMATCH" in i for i in r["issues"])


def test_units_concepts_and_periods_checked():
    r = check("AAPL", "2026-08-15", metric="Revenue", measure="yoy_growth", period_basis="quarter", comparison=">", threshold=10)
    assert r["status"] == "UNVERIFIABLE" and r["issues"][0].startswith("UNIT_MISMATCH")
    r = check("AAPL", "2026-08-15", metric="Bitcoin", measure="level", period_basis="quarter", comparison="increase")
    assert r["issues"] == ["UNKNOWN_CONCEPT:Bitcoin"]
    r = check("AAPL", "2026-08-15", metric="LongTermDebt", measure="level", period_basis="quarter", comparison="decrease")
    assert r["issues"][0].startswith("BASIS_MISMATCH")
    r = check("AAPL", "2026-08-15", metric="Revenue", measure="level", period_basis="quarter", comparison="increase", period_end="2027-03-31")
    assert r["status"] == "UNVERIFIABLE" and r["issues"][0].startswith("PERIOD_NOT_AVAILABLE")


def test_numeric_cutoff_hides_later_periods():
    before = check("AMZN", "2026-05-15", metric="Revenue", measure="level", period_basis="quarter", comparison="increase")
    after = check("AMZN", "2026-08-15", metric="Revenue", measure="level", period_basis="quarter", comparison="increase")
    assert before["computed"]["period_end"] == "2026-03-31"
    assert after["computed"]["period_end"] == "2026-06-30"
    assert all(f["filed"] <= "2026-05-15" for f in before["computed"]["facts"])


def test_numeric_evidence_registered_with_values():
    ledger = EvidenceLedger()
    r = verify_assertion("MSFT", "2026-08-15", {"metric": "Revenue", "measure": "yoy_growth", "period_basis": "annual",
                                                "comparison": ">", "threshold": 0.15}, ledger)
    derived = ledger.get(r["evidence_ids"][0])
    assert derived.kind == "derived_metric" and derived.filed <= "2026-08-15"
    assert any(abs(v - r["computed"]["yoy_change"]) < 1e-12 for v in derived.values)


@pytest.mark.parametrize("statuses,ctype,llm,expected", [
    ([], "numeric", "SUPPORTED", ("SUPPORTED", "NOT_APPLICABLE")),
    (["TRUE", "FALSE"], "mixed", "SUPPORTED", ("CONTRADICTED", "NUMERIC_FALSE")),
    (["TRUE"], "numeric", "INSUFFICIENT_EVIDENCE", ("SUPPORTED", "NUMERIC_ALL_TRUE")),
    (["TRUE"], "interpretive", "INSUFFICIENT_EVIDENCE", ("INSUFFICIENT_EVIDENCE", "NUMERIC_TRUE_QUALITATIVE_UNCHANGED")),
    (["TRUE", "UNVERIFIABLE"], "numeric", "SUPPORTED", ("SUPPORTED", "NUMERIC_PARTIALLY_UNVERIFIABLE")),
])
def test_reconcile_rule(statuses, ctype, llm, expected):
    assert reconcile_label(llm, ctype, [{"status": s} for s in statuses]) == expected
