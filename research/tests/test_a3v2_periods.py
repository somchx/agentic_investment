"""A3 v2.1 reporting-period normalisation and compatibility (a3v2.periods),
its use in the evidence review and the guard, and the preservation of A3 v2.0.
Offline: cached SEC data, scripted model responses. No reference label is read."""
import json
from types import SimpleNamespace

import pytest

from a3v2.checks import check_evidence
from a3v2.config import load_v2_config
from a3v2.periods import PERIODS_VERSION, compatibility, derive_for_claim, evidence_period, is_decisive, normalize_claim_period
from engine.config import config_hash
from engine.llm import CachedLLM, ScriptedLLM
from engine.runner import select_claims
from engine.schema import ClaimInput
from evidence_ledger import EvidenceLedger, EvidenceUnit
from test_a3v2_graph import change_to_contradicted
from test_approaches import PLAN, verdict

V21 = "configs/a3v2_1_dev_v0_2.json"


def claim(company, text, cutoff, rp=None):
    return ClaimInput(claim_id="T", company=company, claim=text, as_of_date=cutoff, reporting_period=rp)


def fact(start, end, kind="xbrl_fact", locator="Revenue x"):
    return SimpleNamespace(kind=kind, period_start=start, period_end=end, locator=locator, excerpt="", form="10-Q")


def passage(text, end, form="10-Q"):
    return SimpleNamespace(kind="filing_passage", period_start=None, period_end=end, locator="p", excerpt=text, form=form)


H1_AMZN = normalize_claim_period(claim("AMZN", "Amazon's free cash flow improved alongside its operating income in the first half of 2026.",
                                       "2026-08-15", "2026 H1"))


# ---------------------------------------------------------------- claim periods

@pytest.mark.parametrize("company,text,cutoff,rp,expect", [
    ("AMZN", "Amazon's free cash flow improved in the first half of 2026.", "2026-08-15", "2026 H1", ("duration", "2026-01-01", "2026-06-30", 6)),
    ("ADBE", "Adobe's fiscal 2025 results were strong.", "2026-01-31", "FY2025", ("duration", "2024-11-30", "2025-11-28", 12)),
    ("PG", "P&G's costs in fiscal 2026 were flat.", "2026-08-20", "FY2026", ("duration", "2025-07-01", "2026-06-30", 12)),
    ("PG", "P&G's first quarter of fiscal 2027 was good.", "2026-11-05", "FY2027 Q1", ("duration", "2026-07-01", "2026-09-30", 3)),
    ("INTC", "Intel earned more in 2026 through the end of September.", "2026-11-15", "FY2026 Q3", ("duration", "2025-12-28", "2026-09-26", 9)),
    ("ADBE", "Adobe repurchased less in the first nine months of fiscal 2026.", "2026-10-05", "FY2026 Q3", ("duration", "2025-11-29", "2026-08-28", 9)),
    ("INTC", "Intel's balance sheet ended 2025 stronger.", "2026-02-15", "FY2025", ("instant", None, "2025-12-27", 0)),
    ("AAPL", "Apple's long-term debt was lower as of June 27, 2026 than a year earlier.", "2026-08-15", None, ("instant", None, "2026-06-27", 0)),
    ("INTC", "Supply constraints limited server revenue in the fourth quarter of 2025.", "2026-02-15", "FY2025", ("duration", "2025-09-28", "2025-12-27", 3)),
])
def test_claim_periods_are_normalised(company, text, cutoff, rp, expect):
    p = normalize_claim_period(claim(company, text, cutoff, rp))
    assert (p["kind"], p["start"], p["end"], p["months"]) == expect and p["version"] == PERIODS_VERSION


def test_calendar_quarter_on_a_non_calendar_fiscal_year_is_unknown():
    p = normalize_claim_period(claim("ADBE", "Adobe's results in the third quarter of 2026 were solid.", "2026-10-05"))
    assert p["kind"] is None and "does not coincide" in p["notes"][-1]


def test_missing_period_is_unknown_and_never_decisive():
    p = normalize_claim_period(claim("PG", "P&G is a resilient company.", "2026-08-20"))
    assert p["kind"] is None
    c = compatibility(p, evidence_period(fact("2025-07-01", "2026-06-30")))
    assert c["status"] == "UNKNOWN" and not is_decisive(c["status"])


def test_period_not_yet_reported_is_projected_and_matches_nothing_filed():
    p = normalize_claim_period(claim("ADBE", "Adobe's revenue for the fourth quarter of fiscal 2026 exceeded $7 billion.", "2026-10-05", "FY2026 Q4"))
    assert p["source"] == "projected" and p["months"] == 3
    assert compatibility(p, evidence_period(fact("2026-05-30", "2026-08-28")))["status"] == "MISMATCH"


def test_previously_unknown_claims_are_now_normalised():
    """The 21 dev-v0.2 claims whose period v2.0 could not resolve."""
    ids = ["DEV-AAPL-03", "DEV-AMZN-03", "DEV-AMZN-05", "DEV-AMZN-07", "DEV-ADBE-03", "DEV-ADBE-06", "DEV-ADBE-08", "DEV-ADBE-10",
           "DEV-INTC-02", "DEV-INTC-05", "DEV-INTC-08", "DEV-INTC-10", "DEV-INTC-11", "DEV-INTC-12", "DEV-PG-03", "DEV-CAT-03",
           "DEV-CAT-05", "DEV-CAT-06", "DEV-CAT-09", "DEV-CAT-10", "DEV-CAT-12"]
    cfg = load_v2_config(V21)
    claims = select_claims(cfg, claim_ids=ids)[0]
    srcs = {c.claim_id: normalize_claim_period(c.to_input())["source"] for c in claims}
    assert len(srcs) == 21 and "unknown" not in srcs.values()
    assert sorted(i for i, s in srcs.items() if s == "projected") == ["DEV-ADBE-10", "DEV-INTC-10"]


# ---------------------------------------------------------------- compatibility

def test_amzn07_h1_versus_trailing_twelve_months_is_a_mismatch():
    ev = evidence_period(passage("Free cash flow for the trailing twelve months ended June 30, 2026 ...", "2026-06-30"),
                         quote="Free cash flow $ 18,184 $ (7,604)", claim_period=H1_AMZN)
    c = compatibility(H1_AMZN, ev)
    assert c["status"] == "MISMATCH" and c["reason"] == "TTM_vs_6M"


def test_h1_versus_six_month_ytd_fact_is_exact():
    assert compatibility(H1_AMZN, evidence_period(fact("2026-01-01", "2026-06-30")))["status"] == "EXACT_MATCH"
    c = compatibility(H1_AMZN, evidence_period(fact("2025-01-01", "2025-06-30")))
    assert c["status"] == "EXACT_MATCH" and c["role"] == "comparison"


def test_same_end_different_duration_is_a_mismatch():
    q3 = normalize_claim_period(claim("CAT", "Caterpillar's sales grew in the third quarter of 2026.", "2026-11-15"))
    nine = compatibility(q3, evidence_period(fact("2026-01-01", "2026-09-30")))
    assert nine["status"] == "MISMATCH" and nine["reason"].startswith("DURATION_DIFFERS:9M_vs_3M")
    assert compatibility(q3, evidence_period(fact("2026-07-01", "2026-09-30")))["status"] == "EXACT_MATCH"
    assert compatibility(q3, evidence_period(passage("Sales for the nine months ended September 30, 2026 rose.", "2026-09-30"),
                                             claim_period=q3))["status"] == "MISMATCH"


def test_fiscal_year_boundaries():
    fy = normalize_claim_period(claim("ADBE", "Adobe's fiscal 2025 results were strong.", "2026-01-31", "FY2025"))
    assert compatibility(fy, evidence_period(fact("2024-11-30", "2025-11-28")))["status"] == "EXACT_MATCH"
    assert compatibility(fy, evidence_period(fact("2025-01-01", "2025-12-31")))["status"] == "MISMATCH"       # calendar 2025
    assert compatibility(fy, evidence_period(passage("Revenue grew in fiscal 2025.", "2025-11-28", form="10-K"),
                                             claim_period=fy))["status"] == "EXACT_MATCH"
    ttm = passage("Revenue for the trailing twelve months ended August 29, 2025", "2025-08-29")
    assert compatibility(fy, evidence_period(ttm, claim_period=fy))["status"] == "MISMATCH"


def test_instant_values():
    bal = normalize_claim_period(claim("AAPL", "Apple's long-term debt was lower as of June 27, 2026 than a year earlier.", "2026-08-15"))
    assert compatibility(bal, evidence_period(fact(None, "2026-06-27")))["status"] == "EXACT_MATCH"
    prior = compatibility(bal, evidence_period(fact(None, "2025-06-28")))
    assert prior["status"] == "EXACT_MATCH" and prior["role"] == "comparison"
    assert compatibility(bal, evidence_period(fact(None, "2025-09-27")))["status"] == "MISMATCH"
    assert compatibility(bal, evidence_period(fact("2026-03-29", "2026-06-27")))["status"] == "MISMATCH"
    q = normalize_claim_period(claim("AAPL", "Apple's net sales for the quarter ended June 27, 2026 grew.", "2026-08-15"))
    assert compatibility(q, evidence_period(fact(None, "2026-06-27")))["reason"] == "BALANCE_EVIDENCE_FOR_A_DURATION_CLAIM"


def test_ambiguous_passages_are_unknown_unless_the_quote_names_the_period():
    q3 = normalize_claim_period(claim("CAT", "Caterpillar's sales grew in the third quarter of 2026.", "2026-11-15"))
    both = passage("Sales increased in the third quarter and in the nine months ended September 30, 2026.", "2026-09-30")
    assert compatibility(q3, evidence_period(both, claim_period=q3))["status"] == "UNKNOWN"
    assert compatibility(q3, evidence_period(both, quote="Sales increased in the third quarter", claim_period=q3))["status"] == "EXACT_MATCH"
    bare = passage("Sales increased because of higher volume.", "2026-09-30")
    assert compatibility(q3, evidence_period(bare, claim_period=q3))["status"] == "UNKNOWN"


# ---------------------------------------------------------------- derivations

def test_derivation_uses_a_filed_ytd_fact_with_provenance():
    led = EvidenceLedger()
    out = derive_for_claim(led, claim("AMZN", "x", "2026-08-15", "2026 H1"), H1_AMZN, "OperatingCashFlow")
    assert {d["role"] for d in out} == {"current", "comparison"}
    cur = next(d for d in out if d["role"] == "current")
    assert (cur["start"], cur["end"]) == ("2026-01-01", "2026-06-30") and "filed fact" in cur["formula"] and cur["inputs"][0]["accession_number"]
    u = led.get(cur["evidence_id"])
    assert compatibility(H1_AMZN, evidence_period(u))["status"] == "COMPATIBLE_AFTER_VERIFIED_DERIVATION"


def test_derivation_sums_filed_single_quarters():
    led = EvidenceLedger()
    p = {**normalize_claim_period(claim("CAT", "Caterpillar's sales grew in the third quarter of 2026.", "2026-11-15")),
         "start": "2026-04-01", "months": 6, "comparison": {"start": "2025-04-01", "end": "2025-09-30"}}
    out = derive_for_claim(led, claim("CAT", "x", "2026-11-15"), p, "OperatingIncome")
    cur = next(d for d in out if d["role"] == "current")
    assert len(cur["inputs"]) == 2 and cur["value"] == sum(i["value"] for i in cur["inputs"]) and " + " in cur["formula"]


def test_no_derivation_when_a_quarter_is_missing_or_the_metric_is_a_ratio():
    led = EvidenceLedger()
    p = {**H1_AMZN, "start": "2025-07-01", "months": 12, "comparison": {"start": None, "end": None}}  # TTM: Q4 2025 not filed as a quarter
    assert derive_for_claim(led, claim("AMZN", "x", "2026-08-15"), p, "Revenue") == []
    assert derive_for_claim(led, claim("AMZN", "x", "2026-08-15"), H1_AMZN, "OperatingMargin") == []


# ---------------------------------------------------------------- review + guard

def run21(cid, review, name="A3v2_1_RG", reconcile=change_to_contradicted, label="SUPPORTED"):
    from a3v2.graph import run as run_v2
    cfg = load_v2_config(V21)
    c = select_claims(cfg, claim_ids=[cid])[0][0]
    resp = {"submit_verdict": verdict(label, ctype="interpretive"), "submit_contradiction_plan": PLAN,
            "submit_evidence_review": review, "submit_reconciliation": reconcile}
    llm = CachedLLM(mode="mock", inner=ScriptedLLM(resp), model="claude-sonnet-4-5-20250929")
    return run_v2(c.to_input(), cfg["approaches"][name], llm, "t"), llm


def contradict_where(pred):
    picked = {}

    def review(p):
        ev = next(e for e in p["evidence"] if e["kind"] == "filing_passage" and pred(e))
        picked.update(evidence_id=ev["evidence_id"], quote=ev["text"][20:90])
        return {"findings": [{"assertion_id": "A0", "evidence_ids": [ev["evidence_id"]], "relation": "CONTRADICTS", "evidence_type": "OBSERVED_RESULT",
                              "addresses": "LEVEL", "key_quote": picked["quote"], "justification": "s"}]}

    def reconcile(p):
        item = [dict(picked)]
        return {"assessments": [{"item_id": "H1", "assessment": "CHALLENGE_SUPPORTED", "evidence": item}], "label": "CONTRADICTED",
                "verdict_changed": True, "change_reason": "s", "supporting_evidence": [], "contradicting_evidence": item, "reasoning_summary": "s"}
    return review, reconcile


def test_contradiction_from_an_incompatible_period_is_rejected_and_a2_kept():
    review, reconcile = contradict_where(lambda e: e["period_status"] == "MISMATCH")
    (pred, trace), llm = run21("DEV-AMZN-07", review, reconcile=reconcile)
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["outcome"] == "REJECT" and g["reason_code"] == "INVALID_DECIDING_EVIDENCE:PERIOD_MISMATCH"
    assert pred["predicted_label"] == pred["initial_label"] == "SUPPORTED"


def test_unknown_period_evidence_cannot_decide():
    review, reconcile = contradict_where(lambda e: e["period_status"] == "UNKNOWN")
    (pred, _), _ = run21("DEV-CAT-12", review, reconcile=reconcile)
    g = pred["contradiction"]["a3v2"]["reconciliation_guard"]
    assert g["outcome"] == "REJECT" and g["reason_code"] == "INVALID_DECIDING_EVIDENCE:PERIOD_UNKNOWN"


def test_review_and_reconciliation_receive_period_information():
    review, reconcile = contradict_where(lambda e: True)
    (pred, _), llm = run21("DEV-AMZN-07", review, reconcile=reconcile)
    rev = next(r for r in llm.inner.requests if r["tools"] == ["submit_evidence_review"])
    packet = json.loads(rev["messages"][0]["content"][-1]["text"].split("PACKET:\n", 1)[1])
    assert packet["claim_period"]["months"] == 6 and packet["claim_period"]["start"] == "2026-01-01"
    assert all("period_status" in e and "period_months" in e for e in packet["evidence"])
    assert any(e["kind"] == "derived_metric" and "PeriodDerivation" in e["metric"] for e in packet["evidence"])
    assert "REPORTING PERIODS (v2.1)" in rev["system"]
    rec = next(r for r in llm.inner.requests if r["tools"] == ["submit_reconciliation"])
    assert '"period_compatibility"' in rec["messages"][-1]["content"][-1]["text"]
    assert pred["contradiction"]["a3v2"]["evidence_review"]["period_derivations"]


def test_v20_config_and_requests_are_unchanged():
    m = json.load(open("results/preflight/a3v2-dev-v0.2_reproducibility_manifest.json"))
    cfg = load_v2_config("configs/a3v2_dev_v0_2.json")
    assert {n: config_hash(a) for n, a in cfg["approaches"].items()} == m["approach_config_hashes"]
    assert "periods" not in cfg["approaches"]["A3v2_R"]["versions"]
    v21 = load_v2_config(V21)
    assert config_hash(v21["approaches"]["A2_rag_numeric"]) == m["approach_config_hashes"]["A2_rag_numeric"]  # A2 cache reusable


def test_check_evidence_v20_path_ignores_duration():
    led = EvidenceLedger()
    eid = led.add(EvidenceUnit(kind="xbrl_fact", ticker="CAT", accession_number="a", form="10-Q", filed="2026-11-04",
                               period_start="2026-01-01", period_end="2026-09-30", locator="Revenue", values=[1.0]))
    c = claim("CAT", "Caterpillar's sales grew in the third quarter of 2026.", "2026-11-15")
    v20 = {"period_end": "2026-09-30", "basis": "quarter", "comparison_end": "2025-09-30", "source": "stated_date"}
    assert check_evidence(led, c, v20, eid)["period_status"] == "MATCH"            # v2.0, preserved
    assert check_evidence(led, c, normalize_claim_period(c), eid)["period_status"] == "MISMATCH"   # v2.1
