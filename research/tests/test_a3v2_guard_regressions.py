"""A3 v2 Evidence Reviewer validation + Reconciliation Guard on known v1 cases.

Each case rebuilds, from the FROZEN v1 trace, the evidence ledger (same ids,
real SEC passages / XBRL facts), the claim, A2's verdict and A3 v1's
reconciliation proposal. Reviewer findings are SCRIPTED: these tests check
the deterministic validation and the guard rules given those findings. They
say nothing about how often a real reviewer would produce them, and they are
regression examples, not a dataset for choosing rules or prompts (the cases
are gold claims already inspected in the v1 error analysis)."""
import json
import os

import pytest

from a3v2.checks import check_citations, check_evidence, claim_period, period_status
from a3v2.derived import run_computation
from a3v2.guard import decide
from a3v2.reviewer import validate_findings
from engine.datasets import load_split

from evidence_ledger import EvidenceLedger, EvidenceUnit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUN = "claimverif-main-v1-20261110T104207Z"
RUN_DIR = os.path.join(ROOT, "results", "runs", RUN)
pytestmark = pytest.mark.skipif(not os.path.isdir(RUN_DIR), reason="frozen v1 run not present")
UNIT_FIELDS = ("kind", "ticker", "source", "accession_number", "form", "filed", "period_start", "period_end", "source_url",
               "locator", "excerpt", "values", "unit", "evidence_id")


@pytest.fixture(scope="module")
def gold_inputs():
    return {c.claim_id: c.to_input() for c in load_split("gold")}


@pytest.fixture(scope="module")
def a3_preds():
    out = {}
    with open(os.path.join(RUN_DIR, "predictions.jsonl")) as f:
        for line in f:
            p = json.loads(line)
            if p["approach"].startswith("A3"):
                out[p["claim_id"]] = p
    return out


class Case:
    """A frozen v1 A3 claim, rebuilt for the v2 guard."""

    def __init__(self, cid, gold_inputs, a3_preds):
        with open(os.path.join(RUN_DIR, "traces", "A3_contradiction_aware", f"{cid}.json")) as f:
            self.trace = json.load(f)
        self.claim = gold_inputs[cid]
        self.pred = a3_preds[cid]
        self.ledger = EvidenceLedger()
        for e in self.trace["evidence"]:
            u = EvidenceUnit(**{k: e.get(k) for k in UNIT_FIELDS})
            u.values = list(u.values or [])
            self.ledger.units[u.evidence_id] = u
        self.period = claim_period(self.claim, self.trace["corpus"]["filings"])
        nv = next(s for s in self.trace["stages"] if s["stage"] == "numeric_verification")
        self.initial_label, self.initial_rule, self.initial_checks = nv["label"], nv["rule"], nv["checks"]
        self.recon = next(c for c in self.trace["llm_calls"] if c["stage"] == "reconciliation")["output"]
        self.assessments = self.pred["contradiction"].get("assessments") or []  # absent when v1's reconciliation was truncated
        self.counter_numeric = self.pred["contradiction"].get("counter_numeric") or []

    def findings(self, *raw):
        ids = {"A0"}
        f, dropped = validate_findings([dict(r, assertion_id=r.get("assertion_id", "A0")) for r in raw], self.ledger, self.claim,
                                       self.period, ids, allow_partial_period=False)
        assert not dropped
        return f

    def guard(self, findings, proposed=None, supporting=None, contradicting=None, assessments=None):
        return decide(initial_label=self.initial_label, proposed_label=proposed or self.recon["label"], initial_rule=self.initial_rule,
                      initial_checks=self.initial_checks,
                      supporting=self.recon.get("supporting_evidence") if supporting is None else supporting,
                      contradicting=self.recon.get("contradicting_evidence") if contradicting is None else contradicting,
                      assessments=self.assessments if assessments is None else assessments, counter_numeric=self.counter_numeric,
                      findings=findings, ledger=self.ledger, claim=self.claim, period=self.period)


@pytest.fixture(scope="module")
def case(gold_inputs, a3_preds):
    cache = {}

    def get(cid):
        if cid not in cache:
            cache[cid] = Case(cid, gold_inputs, a3_preds)
        return cache[cid]
    return get


def F(eids, relation, quote, etype="OBSERVED_RESULT", addresses="LEVEL", **kw):
    return {"evidence_ids": [eids] if isinstance(eids, str) else list(eids), "relation": relation, "key_quote": quote,
            "evidence_type": etype, "addresses": addresses, "justification": "scripted for the test", **kw}


# ------------------------------------------------------------ deterministic checks

def test_deterministic_quote_check_reproduces_v1_validator(case, a3_preds):
    """Port check on every frozen A3 passage citation: v2 flags exactly what
    v1 flagged QUOTE_NOT_IN_PASSAGE, except quotes that differ from the
    passage only in typographic quotes / dashes, which v2 accepts."""
    n, typographic_only = 0, []
    for cid, p in a3_preds.items():
        c = case(cid)
        for cit in p["citations"]:
            if cit.get("kind") != "filing_passage":
                continue
            ch = check_evidence(c.ledger, c.claim, c.period, cit["evidence_id"], cit["quote"])
            v1_flag, v2_flag = "QUOTE_NOT_IN_PASSAGE" in cit["issues"], ch["quote_status"] == "NOT_IN_PASSAGE"
            if v1_flag and not v2_flag:
                typographic_only.append((cid, cit["evidence_id"]))
            else:
                assert v1_flag == v2_flag, (cid, cit["evidence_id"])
            n += 1
    assert n == 286
    assert sorted(typographic_only) == [("GOLD-AAPL-09", "E3"), ("GOLD-KO-05", "E10"), ("GOLD-KO-13", "E1"), ("GOLD-KO-13", "E5"),
                                        ("GOLD-NVDA-14", "E8")]


def test_claim_period_resolution(case):
    assert case("GOLD-NFLX-11").period["period_end"] == "2026-09-30" and case("GOLD-NFLX-11").period["source"] == "stated_date"
    assert case("GOLD-AAPL-12").period == {"period_end": "2025-09-27", "basis": "annual", "comparison_end": "2024-09-27",
                                           "source": "fiscal_year_10k"}
    assert case("GOLD-NVDA-14").period["period_end"] == "2026-01-25"
    p = case("GOLD-TSLA-13").period
    assert period_status("2025-06-30", p) == "COMPARISON" and period_status("2025-12-31", p) == "OTHER_PERIOD"
    assert period_status("2025-06-28", case("GOLD-AAPL-12").period) == "PARTIAL_PERIOD"


# ------------------------------------------------------------ blocking wrong changes

def test_aapl12_resilience_from_context_is_rejected(case):
    """Profit growth is on topic but does not establish 'resilient despite tariffs'."""
    c = case("GOLD-AAPL-12")
    d = c.guard(c.findings(F("E7", "RELATED_NOT_DECIDING", "Operating income 133,050 123,216 114,301", addresses="CHANGE"),
                           F("E1", "RELATED_NOT_DECIDING", "partially offset by tariff costs", addresses="CAUSE")))
    assert (c.initial_label, d["proposed_label"]) == ("INSUFFICIENT_EVIDENCE", "SUPPORTED")
    assert d["outcome"] == "REJECT" and d["final_label"] == "INSUFFICIENT_EVIDENCE"
    assert d["reason_code"] == "REFUTED_CHALLENGES_ONLY"  # v1: 2 REFUTED + 1 NO_RELEVANT, nothing deciding


def test_ko11_refuted_challenges_do_not_prove_the_claim(case):
    c = case("GOLD-KO-11")
    d = c.guard(c.findings(F("E7", "RELATED_NOT_DECIDING", "In 2025, worldwide concentrate sales volume grew 1%", addresses="CHANGE")))
    assert {a["assessment"] for a in c.assessments} == {"CHALLENGE_REFUTED"}
    assert d["outcome"] == "REJECT" and d["reason_code"] == "REFUTED_CHALLENGES_ONLY" and d["final_label"] == "INSUFFICIENT_EVIDENCE"


def test_nflx11_wrong_period_is_excluded_and_downgraded(case):
    c = case("GOLD-NFLX-11")
    quote = "Revenues earned from sources other than monthly membership fees were not a material component of revenues"
    f = c.findings(F("E12", "CONTRADICTS", quote))
    assert f[0]["relation"] == "RELATED_NOT_DECIDING" and f[0]["downgraded_reason"] == "PERIOD_MISMATCH"
    d = c.guard(f)
    assert [e["evidence_id"] for e in d["excluded_citations"]] == ["E12"]
    assert d["excluded_citations"][0]["issues"] == ["PERIOD_MISMATCH"]
    assert d["outcome"] == "REJECT" and d["reason_code"] == "INVALID_DECIDING_EVIDENCE:PERIOD_MISMATCH"


def test_tsla13_argument_from_silence(case):
    c = case("GOLD-TSLA-13")
    assert {a["assessment"] for a in c.assessments} == {"NO_RELEVANT_EVIDENCE"}
    d = c.guard(c.findings(F("E5", "RELATED_NOT_DECIDING", "offset by favorable impacts related to warranty adjustments and tariffs",
                             addresses="CAUSE")))
    assert d["outcome"] == "REJECT" and d["reason_code"] == "ARGUMENT_FROM_SILENCE" and d["final_label"] == "INSUFFICIENT_EVIDENCE"


def test_nvda14_quote_check_and_policy_text(case):
    """Correction of the step-2 audit: E8's quote IS in the passage; v1 flagged
    it only because the filing writes "customers’" and the model "customers'".
    v2 accepts it, so the block must come from the content: a credit-policy
    statement and a stable $4M allowance do not decide collection quality."""
    c = case("GOLD-NVDA-14")
    q = "We perform ongoing credit evaluations of our customers' financial condition and maintain an allowance for potential credit losses."
    assert "customers’ financial condition" in c.ledger.get("E8").excerpt
    assert check_evidence(c.ledger, c.claim, c.period, "E8", q)["quote_status"] == "VERIFIED"
    d = c.guard(c.findings(F("E8", "RELATED_NOT_DECIDING", q, etype="DISCLOSED_FACT"),
                           F("E7", "RELATED_NOT_DECIDING", "Allowance for doubtful accounts $ 4")))
    assert d["excluded_citations"] == []
    assert d["outcome"] == "REJECT" and d["reason_code"] == "CONTEXT_ONLY" and d["final_label"] == "INSUFFICIENT_EVIDENCE"


def test_quote_beyond_the_retrieved_passage_is_rejected(case):
    """A quote that continues past the text the model was shown fails, even if a deciding relation is declared."""
    c = case("GOLD-NVDA-14")
    tail = c.ledger.get("E8").excerpt[-60:]
    beyond = tail + " and therefore collection quality improved during fiscal 2026"
    f = c.findings(F("E8", "CONTRADICTS", beyond, etype="DISCLOSED_FACT"))
    assert f[0]["validation_status"] == "KEY_QUOTE_NOT_IN_EVIDENCE" and f[0]["relation"] == "RELATED_NOT_DECIDING"
    d = c.guard(f, contradicting=[{"evidence_id": "E8", "quote": beyond}])
    assert d["excluded_citations"][0]["issues"] == ["QUOTE_NOT_IN_PASSAGE"]
    assert d["outcome"] == "REJECT" and d["reason_code"] == "INVALID_DECIDING_EVIDENCE:KEY_QUOTE_NOT_IN_EVIDENCE"


def test_wmt08_quote_not_in_sec_and_strategy_text(case):
    c = case("GOLD-WMT-08")
    f = c.findings(F("E4", "ENTAILS", "Membership and other income increased 6.9% and 6.3% for fiscal 2026 and 2025"),
                   F("E10", "ENTAILS", "Additionally, we focus on our mix of businesses, including expanding our ecosystem in higher margin areas",
                     etype="MANAGEMENT_INTENT", addresses="CAUSE"))
    assert [x["downgraded_reason"] for x in f] == ["KEY_QUOTE_NOT_IN_EVIDENCE", "NON_RESULT_EVIDENCE:MANAGEMENT_INTENT"]
    d = c.guard(f)
    assert {"E3", "E4"} <= {e["evidence_id"] for e in d["excluded_citations"]}
    assert d["outcome"] == "REJECT" and d["final_label"] == "CONTRADICTED"
    assert d["reason_code"] == "INVALID_DECIDING_EVIDENCE:KEY_QUOTE_NOT_IN_EVIDENCE+NON_RESULT_EVIDENCE"


def test_msft12_free_cash_flow_keeps_a2_verdict(case):
    """FCF computed from XBRL (OCF - purchases of PP&E) decides 'no pressure on FCF'; a move to INSUFFICIENT is rejected."""
    c = case("GOLD-MSFT-12")
    comp = run_computation(c.ledger, c.claim, {"computation_id": "C1", "metric": "FreeCashFlow", "basis": "quarter",
                                               "period_end": "2026-09-30"})
    assert comp["status"] == "OK"
    assert (comp["current"], comp["prior"]) == (58_000e6 - 39_367e6, 45_057e6 - 19_394e6)  # 18,633M vs 25,663M
    eid = comp["evidence_id"]
    assert check_evidence(c.ledger, c.claim, c.period, eid, "18,633")["period_status"] == "MATCH"
    f = c.findings(F(eid, "CONTRADICTS", "18,633", etype="OBSERVED_RESULT", addresses="CHANGE"))
    assert f[0]["validation_status"] == "VALID"
    d = c.guard(f)
    assert (c.initial_label, d["proposed_label"]) == ("CONTRADICTED", "INSUFFICIENT_EVIDENCE")
    assert d["outcome"] == "REJECT" and d["reason_code"] == "INITIAL_VERDICT_STILL_DECIDED" and d["final_label"] == "CONTRADICTED"


# ------------------------------------------------------------ allowing legitimate corrections

def test_meta06_correction_without_supported_challenge_is_allowed(case):
    """All three v1 challenges were NO_RELEVANT_EVIDENCE; the correction rests on two figures combined."""
    c = case("GOLD-META-06")
    assert c.pred["contradiction"]["challenges_supported"] == 0
    f = c.findings(F(["E1", "E10"], "ENTAILS", "average price per ad increased by 14%", addresses="CHANGE"))
    d = c.guard(f)
    assert (c.initial_label, d["proposed_label"]) == ("CONTRADICTED", "SUPPORTED")
    assert d["outcome"] == "ACCEPT" and d["final_label"] == "SUPPORTED" and d["deciding_findings"] == ["R1"]
    # without a deciding finding the same proposal is an argument from silence
    assert c.guard(c.findings(F("E1", "RELATED_NOT_DECIDING", "average price per ad increased by 14%")))["reason_code"] == "ARGUMENT_FROM_SILENCE"


def test_ko12_correction_without_supported_challenge_is_allowed(case):
    c = case("GOLD-KO-12")
    assert c.pred["contradiction"]["challenges_supported"] == 0
    f = c.findings(F("E8", "CONTRADICTS", "favorably impacted consolidated operating income by 3%", addresses="CHANGE"))
    d = c.guard(f)
    assert (c.initial_label, d["proposed_label"]) == ("INSUFFICIENT_EVIDENCE", "CONTRADICTED")
    assert d["outcome"] == "ACCEPT" and d["final_label"] == "CONTRADICTED"


def test_msft08_non_comparable_segment_allows_insufficient(case):
    c = case("GOLD-MSFT-08")
    f = c.findings(F("E10", "RELATED_NOT_DECIDING", "Metrics related to our Devices and Consumer segment", etype="DEFINITION",
                     addresses="DEFINITION", definition_mismatch=True))
    d = c.guard(f)
    assert (c.initial_label, d["proposed_label"]) == ("CONTRADICTED", "INSUFFICIENT_EVIDENCE")
    assert d["outcome"] == "ACCEPT" and d["reason_code"] == "DEFINITION_MISMATCH"
    # the same move is rejected when valid evidence still decides A2's verdict and no mismatch is shown
    still = c.findings(F("E1", "CONTRADICTS", "Devices and Consumer revenue decreased driven by Windows OEM and devices"))
    assert c.guard(still)["reason_code"] == "INITIAL_VERDICT_STILL_DECIDED"


# ------------------------------------------------------------ rule-level checks

def test_a2_numeric_conclusion_is_preserved(case):
    """A2's NUMERIC_FALSE stands unless a counter numeric check or a definition mismatch overturns it."""
    c = case("GOLD-KO-12")
    kw = dict(initial_label="CONTRADICTED", initial_rule="NUMERIC_FALSE",
              initial_checks=[{"status": "FALSE", "evidence_ids": ["E1"]}], supporting=[], contradicting=[], assessments=[],
              ledger=c.ledger, claim=c.claim, period=c.period, findings=[])
    assert decide(proposed_label="INSUFFICIENT_EVIDENCE", counter_numeric=[], **kw)["reason_code"] == "A2_NUMERIC_CONCLUSION_PRESERVED"
    d = decide(proposed_label="INSUFFICIENT_EVIDENCE", counter_numeric=[{"status": "TRUE", "evidence_ids": []}], **kw)
    assert d["reason_code"] != "A2_NUMERIC_CONCLUSION_PRESERVED"


def test_supported_rejected_when_valid_evidence_contradicts(case):
    c = case("GOLD-META-06")
    f = c.findings(F(["E1", "E10"], "ENTAILS", "average price per ad increased by 14%"),
                   F("E10", "CONTRADICTS", "Ad impressions delivered across our Family of Apps in the third quarter of 2026 increased 10%"))
    assert c.guard(f)["reason_code"] == "CONFLICTING_DECIDING_EVIDENCE"


def test_deciding_evidence_must_be_cited(case):
    c = case("GOLD-KO-12")
    f = c.findings(F("E8", "CONTRADICTS", "favorably impacted consolidated operating income by 3%"))
    d = c.guard(f, contradicting=[{"evidence_id": "E7", "quote": c.recon["contradicting_evidence"][-1]["quote"]}])
    assert d["outcome"] == "REJECT" and d["reason_code"] == "DECIDING_EVIDENCE_NOT_CITED"


def test_unchanged_verdict_passes_through(case):
    c = case("GOLD-AAPL-12")
    d = c.guard([], proposed="INSUFFICIENT_EVIDENCE", supporting=[], contradicting=[])
    assert d["outcome"] == "NO_CHANGE" and d["final_label"] == "INSUFFICIENT_EVIDENCE"


def test_check_citations_keeps_valid_and_comparison_period(case):
    c = case("GOLD-AAPL-12")
    kept, excluded = check_citations(c.ledger, c.claim, c.period, [{"evidence_id": "E7", "quote": "Operating income 133,050 123,216 114,301"},
                                                                   {"evidence_id": "E99", "quote": "x" * 20}, "junk"])
    assert [k["evidence_id"] for k in kept] == ["E7"]
    assert [e["issues"] for e in excluded] == [["UNKNOWN_EVIDENCE_ID"], ["MALFORMED_ITEM"]]
