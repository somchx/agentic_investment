"""A3 v2.1.1: A2-numeric derived values take their window from their source
facts; key-quote years and statement time (historical vs forward-looking);
API retries with backoff, resume of ERROR claims, ledger accounting. Offline:
cached SEC data, fake API, injected sleep. No reference label is read."""
import json
import os
from types import SimpleNamespace

import pytest
import requests

from a3v2.config import load_v2_config
from a3v2.periods import PERIODS_VERSION, PERIODS_VERSION_V11, compatibility, evidence_period, normalize_claim_period, temporal_class
from a3v2.reviewer import validate_findings
from engine.config import config_hash
from engine.cost_ledger import CostLedger
from engine.llm import CachedLLM, PaidRunApproval, Pricing, ScriptedLLM, TransientRetriesExhausted
from engine.numeric import verify_assertion
from engine.runner import run_experiment, select_claims
from engine.schema import ClaimInput
from evidence_ledger import EvidenceLedger, EvidenceUnit
from test_a3v2_graph import change_to_contradicted, review_with
from test_approaches import PLAN, verdict

V211 = "configs/a3v2_1_1_dev_v0_2.json"
APPROVAL = PaidRunApproval(max_cost_usd=50.0, max_calls=1000, phrase="t")


def claim(company, text, cutoff, rp=None):
    return ClaimInput(claim_id="T", company=company, claim=text, as_of_date=cutoff, reporting_period=rp)


def p11(c):
    return normalize_claim_period(c, PERIODS_VERSION_V11)


# ------------------------------------------------- A2-numeric derived windows

AAPL02 = claim("AAPL", "Apple's operating margin exceeded 30% in the quarter ended June 27, 2026.", "2026-08-15", "FY2026 Q3")
CAT12 = claim("CAT", "Caterpillar's total sales and revenues grew 21% in the third quarter of 2026.", "2026-11-15", "FY2026 Q3")


def numeric(c, a):
    led = EvidenceLedger()
    r = verify_assertion(c.company, c.as_of_date, {"stated_value": None, "comparison": ">", **a}, led)
    return led, led.get(r["evidence_ids"][0])


def test_aapl02_operating_margin_window_comes_from_its_source_facts():
    led, u = numeric(AAPL02, {"metric": "OperatingMargin", "measure": "level", "period_basis": "quarter", "period_end": "2026-06-27", "threshold": 0.3})
    assert u.kind == "derived_metric" and u.period_start is None
    ev = evidence_period(u, None, p11(AAPL02), led)
    assert (ev["source"], ev["start"], ev["months"]) == ("numeric_derivation", "2026-03-29", [3])
    assert compatibility(p11(AAPL02), ev)["status"] == "COMPATIBLE_AFTER_VERIFIED_DERIVATION"
    v10 = normalize_claim_period(AAPL02, PERIODS_VERSION)  # A3 v2.1 behaviour, preserved
    assert compatibility(v10, evidence_period(u, None, v10, led))["status"] == "UNKNOWN"


def test_cat12_growth_window_comes_from_its_source_facts():
    led, u = numeric(CAT12, {"metric": "Revenue", "measure": "yoy_growth", "period_basis": "quarter", "period_end": "2026-09-30", "threshold": 0.2})
    ev = evidence_period(u, None, p11(CAT12), led)
    assert ev["start"] == "2026-07-01" and compatibility(p11(CAT12), ev)["status"] == "COMPATIBLE_AFTER_VERIFIED_DERIVATION"


def test_numeric_value_without_its_source_facts_stays_unknown():
    _, u = numeric(CAT12, {"metric": "Revenue", "measure": "yoy_growth", "period_basis": "quarter", "period_end": "2026-09-30", "threshold": 0.2})
    ev = evidence_period(u, None, p11(CAT12), EvidenceLedger())
    assert ev["kind"] is None and compatibility(p11(CAT12), ev)["status"] == "UNKNOWN"


def test_annual_numeric_value_does_not_match_a_quarter_claim():
    led, u = numeric(CAT12, {"metric": "Revenue", "measure": "level", "period_basis": "annual", "period_end": "2025-12-31", "threshold": 1})
    assert compatibility(p11(CAT12), evidence_period(u, None, p11(CAT12), led))["status"] == "MISMATCH"


# ------------------------------------------------- statement time and years

CAT07 = claim("CAT", "Demand from data centers drove the growth in Caterpillar's order backlog during 2025.", "2026-03-01", "FY2025")
FWD = ("In Power & Energy, we anticipate growth in Power Generation for both reciprocating engines and turbines and turbine-related "
       "services in 2026, driven by increasing energy demand to support data center build-out.")
HIST = "Compared with year-end 2024, the order backlog increased across the primary segments, with the largest increase in Power & Energy."
MIXED = "Sales increased 4 percent in 2025, and we expect further growth in 2026."


@pytest.mark.parametrize("quote,expect", [(FWD, "FORWARD_LOOKING"), (HIST, "HISTORICAL_FACT"), (MIXED, "MIXED_OR_UNCLEAR"),
                                          ("Free cash flow $ 18,184 $ (7,604)", "HISTORICAL_FACT"),
                                          ("The company will continue to invest in AI infrastructure.", "FORWARD_LOOKING")])
def test_statement_time(quote, expect):
    assert temporal_class(quote) == expect


def cat_ledger():
    led = EvidenceLedger()
    eid = led.add(EvidenceUnit(kind="filing_passage", ticker="CAT", accession_number="0000018230-26-000008", form="10-K",
                               filed="2026-02-13", period_end="2025-12-31", locator="10-K c1", excerpt=f"{HIST} {FWD} {MIXED}"))
    return led, eid


def finding(eid, quote, relation="ENTAILS"):
    return [{"assertion_id": "A0", "evidence_ids": [eid], "relation": relation, "evidence_type": "OBSERVED_RESULT", "addresses": "CAUSE",
             "key_quote": quote, "justification": "s"}]


def test_cat07_forward_looking_2026_statement_cannot_support_a_2025_claim():
    led, eid = cat_ledger()
    p = p11(CAT07)
    f, _ = validate_findings(finding(eid, FWD), led, CAT07, p, {"A0"}, False)
    assert f[0]["relation"] == "RELATED_NOT_DECIDING" and f[0]["downgraded_reason"] == "PERIOD_MISMATCH"
    assert f[0]["checks"][0]["period_compatibility"]["reason"] == "QUOTE_REFERS_TO_OTHER_YEAR:2026"
    no_year = FWD.replace(" in 2026", "")
    led.add(EvidenceUnit(kind="filing_passage", ticker="CAT", accession_number="a", form="10-K", filed="2026-02-13",
                         period_end="2025-12-31", locator="10-K c2", excerpt=no_year))
    f, _ = validate_findings(finding("E2", no_year), led, CAT07, p, {"A0"}, False)
    assert f[0]["downgraded_reason"] == "FORWARD_LOOKING_FOR_HISTORICAL_CLAIM"


def test_mixed_statement_is_not_decisive_but_historical_comparison_is_valid():
    led, eid = cat_ledger()
    p = p11(CAT07)
    f, _ = validate_findings(finding(eid, MIXED), led, CAT07, p, {"A0"}, False)
    assert f[0]["downgraded_reason"] == "TEMPORAL_MIXED_OR_UNCLEAR"
    f, _ = validate_findings(finding(eid, HIST), led, CAT07, p, {"A0"}, False)  # names 2024, the comparison year
    assert f[0]["validation_status"] == "VALID" and f[0]["relation"] == "ENTAILS" and f[0]["statement_time"] == ["HISTORICAL_FACT"]


def test_v21_rules_are_unchanged_for_the_same_quote():
    led, eid = cat_ledger()
    f, _ = validate_findings(finding(eid, FWD), led, CAT07, normalize_claim_period(CAT07), {"A0"}, False)
    assert f[0]["validation_status"] == "VALID"  # what v2.1 did (the defect the smoke test exposed)


def test_amzn07_ttm_still_mismatches_and_fiscal_years_unchanged():
    h1 = p11(claim("AMZN", "Amazon's free cash flow improved alongside its operating income in the first half of 2026.", "2026-08-15", "2026 H1"))
    ttm = SimpleNamespace(kind="filing_passage", period_start=None, period_end="2026-06-30", locator="p", form="10-Q",
                          excerpt="Free cash flow for the trailing twelve months ended June 30, 2026")
    assert compatibility(h1, evidence_period(ttm, "Free cash flow $ 18,184 $ (7,604)", h1))["reason"] == "TTM_vs_6M"
    for c in (claim("ADBE", "Adobe's fiscal 2025 results were strong.", "2026-01-31", "FY2025"),
              claim("PG", "P&G's first quarter of fiscal 2027 was good.", "2026-11-05", "FY2027 Q1")):
        a, b = normalize_claim_period(c), p11(c)
        assert (a["start"], a["end"], a["months"]) == (b["start"], b["end"], b["months"])


def test_v21_and_v20_configs_keep_their_hashes():
    m21 = json.load(open("results/runs/a3v2.1-dev-v0.2-20261117T085608Z/manifest.json"))
    assert {n: config_hash(a) for n, a in load_v2_config("configs/a3v2_1_dev_v0_2.json")["approaches"].items()} == m21["approach_config_hashes"]
    cfg = load_v2_config(V211)
    assert cfg["approaches"]["A3v2_1_1_RG"]["versions"]["periods"] == PERIODS_VERSION_V11 and cfg["api_retry"]["max_retries"] == 5
    assert config_hash(cfg["approaches"]["A2_rag_numeric"]) == m21["approach_config_hashes"]["A2_rag_numeric"]


# ------------------------------------------------- API retries and recovery

def http_error(code, retry_after=None):
    r = requests.Response()
    r.status_code = code
    if retry_after is not None:
        r.headers["retry-after"] = str(retry_after)
    return requests.HTTPError(f"{code} error", response=r)


class Flaky(ScriptedLLM):
    def __init__(self, resp, errors=(), fail_tool=None):
        super().__init__(resp)
        self.errors, self.fail_tool, self.attempts = list(errors), fail_tool, 0

    def create(self, system, messages, tools, max_tokens, tool_choice=None):
        self.attempts += 1
        if self.errors and (self.fail_tool is None or tools[-1]["name"] == self.fail_tool):
            raise self.errors.pop(0)
        return super().create(system, messages, tools, max_tokens, tool_choice)


def live(tmp_path, api, ledger=None, sleeps=None, retry=None):
    return CachedLLM(mode="live", model="claude-sonnet-4-5-20250929", temperature=0, cache_dir=str(tmp_path / "cache"), inner=api,
                     approval=APPROVAL, ledger=ledger, retry=retry or {"max_retries": 5, "base_s": 2.0, "max_s": 60.0, "jitter": True},
                     sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


REQ = ("s", [{"role": "user", "content": "x"}], [{"name": "submit_verdict", "input_schema": {}}], 100)
RESP = {"submit_verdict": {"label": "SUPPORTED"}}


def test_repeated_529_then_success_with_backoff_and_retry_after(tmp_path):
    sleeps = []
    led = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "l"))
    api = Flaky(RESP, [http_error(529), http_error(529, retry_after=7), http_error(503)])
    llm = live(tmp_path, api, led, sleeps)
    out = llm.create(*REQ)
    assert out["_source"] == "live" and api.attempts == 4 and llm.stats["retries"] == 3
    assert 1.0 <= sleeps[0] <= 2.0 and sleeps[1] >= 7 and 4.0 <= sleeps[2] <= 8.0   # jittered 2^n, Retry-After honoured
    s = led.status()
    assert s["paid_calls"] == 1 and s["failed_calls"] == 3 and s["open_reservations"] == []


def test_exhausted_retry_budget_raises_a_non_transient_error(tmp_path):
    api = Flaky(RESP, [http_error(529)] * 6)
    llm = live(tmp_path, api)
    with pytest.raises(TransientRetriesExhausted, match="after 5 retries"):
        llm.create(*REQ)
    assert api.attempts == 6
    from graphs.build import is_transient
    assert not is_transient(TransientRetriesExhausted("x"))  # graph retry policies do not multiply attempts


def test_401_is_never_retried(tmp_path):
    api = Flaky(RESP, [http_error(401)])
    with pytest.raises(requests.HTTPError):
        live(tmp_path, api).create(*REQ)
    assert api.attempts == 1


def test_retries_off_keeps_v1_behaviour(tmp_path):
    api = Flaky(RESP, [http_error(529)])
    llm = CachedLLM(mode="live", model="m", temperature=0, cache_dir=str(tmp_path / "c"), inner=api, approval=APPROVAL)
    with pytest.raises(requests.HTTPError):
        llm.create(*REQ)
    assert api.attempts == 1 and llm.retry is None


def responses():
    return {"submit_verdict": verdict(ctype="interpretive"), "submit_contradiction_plan": PLAN,
            "submit_evidence_review": review_with("RELATED_NOT_DECIDING"), "submit_reconciliation": change_to_contradicted}


def test_interrupted_claim_is_resumed_with_retry_errors_without_paying_twice(tmp_path):
    cfg = load_v2_config(V211)
    claims = select_claims(cfg, claim_ids=["DEV-PG-05", "DEV-CAT-12"])
    led = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "l"))
    runs = str(tmp_path / "runs")
    # the first process: every review call of the first claim fails 6 times (529) -> retries exhausted -> ERROR
    api1 = Flaky(responses(), [http_error(529)] * 6, fail_tool="submit_evidence_review")
    rid = run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api1, led), ledger=led,
                         runs_dir=runs, progress=lambda *_: None)
    rows = [json.loads(x) for x in open(os.path.join(runs, rid, "predictions.jsonl"))]
    errs = [r for r in rows if r["stop_reason"] == "ERROR"]
    assert len(errs) == 1 and "TransientRetriesExhausted" in errs[0]["error"]
    assert json.load(open(os.path.join(runs, rid, "status.json")))["state"] == "incomplete"
    paid_before = led.status()["paid_calls"]
    # a new process resumes with --retry-errors: the failed claim runs again; its initial and hypotheses calls come from the cache
    api2 = Flaky(responses())
    run_experiment(cfg, *claims, llm_mode="live", approval=APPROVAL, llm=live(tmp_path, api2, led), ledger=led, resume_run_id=rid,
                   retry_errors=True, runs_dir=runs, progress=lambda *_: None)
    assert [r["tools"] for r in api2.requests] == [["submit_evidence_review"], ["submit_reconciliation"]]
    rows = [json.loads(x) for x in open(os.path.join(runs, rid, "predictions.jsonl"))]
    assert len(rows) == 6 and len({(r["approach"], r["claim_id"]) for r in rows}) == 6 and all(r["stop_reason"] == "COMPLETED" for r in rows)
    assert os.path.exists(os.path.join(runs, rid, "superseded_errors.jsonl"))
    s = led.status()
    assert s["paid_calls"] == paid_before + 2 and s["failed_calls"] == 6 and s["open_reservations"] == []
    st = json.load(open(os.path.join(runs, rid, "status.json")))
    assert st["state"] == "complete" and st["replay_llm_stats"]["live_calls"] == 0  # RG stays cache-only


def test_failed_attempts_are_counted_conservatively_in_the_ledger(tmp_path):
    led = CostLedger("t", 15.0, ledger_dir=str(tmp_path / "l"))
    api = Flaky(RESP, [http_error(529)] * 2)
    live(tmp_path, api, led).create(*REQ)
    s = led.status()
    assert s["failed_reserved_usd"] > 0 and s["settled_usd"] == pytest.approx(Pricing().cost(1000, 200))


def test_truncated_review_never_becomes_a_valid_assessment():
    from a3v2.graph import run as run_v2
    cfg = load_v2_config(V211)
    c = select_claims(cfg, claim_ids=["DEV-PG-05"])[0][0]

    class Truncating(ScriptedLLM):
        def create(self, system, messages, tools, max_tokens, tool_choice=None):
            out = super().create(system, messages, tools, max_tokens, tool_choice)
            if tools[-1]["name"] == "submit_evidence_review":
                out["stop_reason"], out["usage"] = "max_tokens", {"input_tokens": 8000, "output_tokens": max_tokens}
            return out
    llm = CachedLLM(mode="mock", inner=Truncating(responses()), model="claude-sonnet-4-5-20250929")
    pred, trace = run_v2(c.to_input(), cfg["approaches"]["A3v2_1_1_RG"], llm, "t")
    rev = next(x for x in trace["llm_calls"] if x["stage"] == "evidence_review")
    assert rev["stop_reason"] == "max_tokens" and rev["output_tokens"] == 4096          # logged at the 4,096 cap
    assert pred["stop_reason"] == "NO_FINAL_VERDICT" and pred["predicted_label"] == pred["initial_label"]  # A2 kept


def test_review_cap_is_4096_and_only_the_review_changed():
    from engine.config import thaw
    from engine.llm import request_key
    cfg = load_v2_config(V211)
    r = thaw(cfg["approaches"]["A3v2_1_1_R"])
    assert r["review"]["max_output_tokens"] == 4096 and r["llm"]["max_output_tokens"] == 1500
    v21 = thaw(load_v2_config("configs/a3v2_1_dev_v0_2.json")["approaches"]["A3v2_1_R"])
    assert {k for k in r if r.get(k) != v21.get(k)} == {"review", "periods", "versions", "name", "description"}
    assert {k for k in r["review"] if r["review"][k] != v21["review"][k]} == {"max_output_tokens"}
    k = lambda mt: request_key("m", 0, "s", [{"role": "user", "content": "x"}], [], mt, None)
    assert k(3000) != k(4096)  # the cap is part of the cache key: no 3,000-token response is reused


def test_long_review_up_to_4096_tokens_is_accepted_and_reaches_reconciliation():
    from a3v2.graph import run as run_v2
    cfg = load_v2_config(V211)
    c = select_claims(cfg, claim_ids=["DEV-PG-05"])[0][0]

    class Long(ScriptedLLM):
        def create(self, system, messages, tools, max_tokens, tool_choice=None):
            out = super().create(system, messages, tools, max_tokens, tool_choice)
            if tools[-1]["name"] == "submit_evidence_review":
                out["usage"] = {"input_tokens": 9000, "output_tokens": 4000}  # under the cap, complete tool call
            return out
    inner = Long(responses())
    pred, trace = run_v2(c.to_input(), cfg["approaches"]["A3v2_1_1_R"], CachedLLM(mode="mock", inner=inner, model="m"), "t")
    rev = next(x for x in trace["llm_calls"] if x["stage"] == "evidence_review")
    assert rev["output_tokens"] == 4000 and rev["stop_reason"] == "tool_use" and pred["stop_reason"] == "COMPLETED"
    assert next(r for r in inner.requests if r["tools"] == ["submit_evidence_review"])["max_tokens"] == 4096
    assert any(r["tools"] == ["submit_reconciliation"] for r in inner.requests)
