"""Agentic investigation workflow 2.0 -- offline tests.

Real deterministic tools over the committed SEC cache (analysis date in the
past, live features off, so no network and no price provider), a scripted
MockLLM in place of Claude (no paid calls), and in-memory purchases instead
of the database. Covers the 15 scenarios of the upgrade spec.
"""
import json
import re
import unittest
from unittest.mock import patch

import answer_guard
import evidence_ledger as el
import intent as intent_mod
import investigation_tools as it
import portfolio_assistant as pa
import tools
from investigation_engine import EngineConfig, InvestigationEngine
from investigation_tools import ToolContext, run_tool

AS_OF = "2026-10-29"
KEYS = ["revenue_growth", "operating_margin", "debt_growth"]


def snapshot(ticker, key, purchase_date):
    r = tools.REASON_DEFS[key]
    rule = {"metric": r.metric, "comparison": r.comparison, "threshold": r.threshold, "kind": r.kind,
            "denominator_metric": r.denominator_metric, "instant": r.instant, "is_custom": False,
            "description": r.description, "rule_definition": None, "original_text": ""}
    ev = tools.evaluate_frozen_reason(ticker, rule, as_of=purchase_date)
    return {**rule, "rule_status_at_purchase": ev["rule_status"], "evidence_status_at_purchase": ev["evidence_status"],
            "status_at_purchase": ev["status"], "computed_value_at_purchase": ev["computed_value"],
            "explanation_at_purchase": ev["explanation"]}


def purchase(pid, ticker, date, qty=10, price=100.0, keys=KEYS):
    return {"id": pid, "ticker": ticker, "quantity": qty, "purchase_price": price, "purchase_date": date, "thesis": None,
            "reasons": [{"id": pid * 10 + i, "reason_key": k, "reason_snapshot": snapshot(ticker, k, date)} for i, k in enumerate(keys)]}


def ctx_with(*lots, as_of=AS_OF):
    return ToolContext(analysis_date=as_of, user_id=None, live_override=False, _purchases=list(lots))


# ----------------------------------------------------------------- mock LLM

class MockLLM:
    """Each step is a function(messages, tools, tool_choice) -> list of content
    blocks. Records every request so tests can assert on what was sent."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.requests = []

    def create(self, system, messages, tools, max_tokens, tool_choice=None):
        self.requests.append({"messages": json.loads(json.dumps(messages, default=str)), "tools": [t["name"] for t in tools],
                              "tool_choice": tool_choice})
        step = self.steps.pop(0) if self.steps else (lambda *a: [{"type": "text", "text": "done"}])
        content = step(messages, tools, tool_choice)
        stop = "tool_use"
        if isinstance(content, tuple):  # (content, stop_reason) to simulate e.g. max_tokens
            content, stop = content
        return {"content": content, "usage": {"input_tokens": 1000, "output_tokens": 200}, "stop_reason": stop}


_n = [0]


def use(name, **args):
    _n[0] += 1
    return {"type": "tool_use", "id": f"tu{_n[0]}", "name": name, "input": args}


def calls(*uses):
    return lambda m, t, c: list(uses)


def tool_outputs(messages):
    """Every tool_result payload seen so far, parsed."""
    out = []
    for m in messages:
        if m["role"] == "user" and isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_result" and not b.get("is_error"):
                    try:
                        out.append(json.loads(b["content"]))
                    except ValueError:
                        pass
    return out


def find(messages, pred):
    for o in tool_outputs(messages):
        for item in _walk(o):
            if isinstance(item, dict) and pred(item):
                return item
    raise AssertionError("expected tool output not found")


def _walk(o):
    yield o
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def assess(**extra):
    def step(messages, t, c):
        ids = sorted({i for o in tool_outputs(messages) for i in re.findall(r'"(E\d+)"', json.dumps(o))}, key=lambda x: int(x[1:]))
        return [use("record_evidence_assessment", assessments=[{"topic": "all reasons", "supporting_evidence_ids": ids[:2],
                                                              "contradicting_evidence_ids": [], "sufficiency": "SUFFICIENT", **extra}])]
    return step


def evaluation(messages, ticker, key):
    return find(messages, lambda d: d.get("ticker") == ticker and d.get("reason_key") == key and "computed_value" in d and "evidence_ids" in d)


def finalize_from_evaluations(pairs, extra_paragraph=None):
    """A truthful answer built from the evaluation numbers the tools returned."""
    def step(messages, t, c):
        claims, paras = [], []
        for i, (ticker, key) in enumerate(pairs, 1):
            e = evaluation(messages, ticker, key)
            pct = f"{e['computed_value'] * 100:.1f}%"
            claims.append({"claim_id": f"c{i}", "ticker": ticker, "reason_key": key, "claim_type": "numeric",
                           "status": "SUPPORTED", "evidence_ids": e["evidence_ids"][:1],
                           "proposition": f"{ticker} {key} is {pct} against a {e['threshold'] * 100:.0f}% threshold"})
            paras.append({"text": f"{ticker}: ค่าล่าสุดอยู่ที่ {pct} เทียบกับเกณฑ์ {e['threshold'] * 100:.0f}%", "claim_ids": [f"c{i}"]})
        sections = [{"key": "supported", "paragraphs": paras}]
        if extra_paragraph:
            sections.append({"key": "risks", "paragraphs": [extra_paragraph]})
        return [use("finalize_answer", sections=sections, claims=claims,
                    scope_note="ตรวจเฉพาะเกณฑ์ตัวเลขที่คุณตั้งไว้ ไม่ได้ประเมินราคาหรือปัจจัยอื่น")]
    return step


def run_chat(ctx, question, *steps):
    llm = MockLLM(*steps)
    with patch.object(pa, "db"):  # no database in these tests
        return pa.answer_portfolio_question_v2(None, question, language="th", llm=llm, ctx=ctx), llm


PORTFOLIO_Q = "ตอนนี้พอร์ตของฉันเป็นยังไงบ้าง?"


def portfolio_steps(tickers, finalize):
    return [calls(use("get_user_portfolio"), use("get_latest_thesis_evaluations")),
            calls(*[use("compare_financial_periods", ticker=t) for t in tickers], *[use("check_new_sec_filings", ticker=t) for t in tickers]),
            assess(), finalize]


# ===================================================================== tests

class PortfolioToolTests(unittest.TestCase):
    def test_01_one_holding_overview(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15", qty=10, price=210))
        p = run_tool(ctx, "get_user_portfolio", {})
        self.assertTrue(p["single_holding"])
        self.assertEqual(p["holdings"][0]["cost_basis"], 2100)
        self.assertEqual(p["holdings"][0]["price_status"], "not_used_for_historical_analysis")
        self.assertNotIn("market_value", p["holdings"][0])  # no verified price -> no P&L

    def test_02_multiple_holdings_weights_and_concentration(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15", qty=10, price=210), purchase(2, "MSFT", "2026-05-01", qty=1, price=100))
        p = run_tool(ctx, "get_user_portfolio", {})
        self.assertEqual(p["weights_basis"], "cost_basis")
        self.assertEqual(p["concentration_flags"], ["AAPL"])
        self.assertAlmostEqual(sum(h["weight"] for h in p["holdings"]), 1.0)

    def test_02b_verified_price_gives_pnl(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15", qty=10, price=210))
        ctx.live_override = True
        with patch("market_data.get_quote", return_value={"price": 300.0, "as_of": AS_OF, "source": "test", "currency": "USD"}):
            h = run_tool(ctx, "get_user_portfolio", {})["holdings"][0]
        self.assertEqual((h["market_value"], h["unrealized_pnl"]), (3000.0, 900.0))
        self.assertEqual(ctx.ledger.get(h["price_evidence_id"]).values, [300.0])

    def test_03_all_rules_satisfied(self):
        ev = run_tool(ctx_with(purchase(1, "AAPL", "2026-08-15")), "get_latest_thesis_evaluations", {})["evaluations"]
        self.assertEqual({e["rule_status"] for e in ev}, {"SATISFIED"})
        self.assertTrue(all(e["evidence_ids"] for e in ev))

    def test_04_breached_rule(self):
        ev = run_tool(ctx_with(purchase(1, "AMZN", "2026-03-02")), "get_latest_thesis_evaluations", {})["evaluations"]
        debt = next(e for e in ev if e["reason_key"] == "debt_growth")
        self.assertEqual(debt["rule_status"], "BREACHED")
        self.assertGreater(debt["computed_value"], 1.5)

    def test_05_missing_financial_data(self):
        ctx = ctx_with()
        bogus = {"metric": "NoSuchTagEver", "comparison": ">", "threshold": 0.1, "kind": "yoy_growth", "denominator_metric": "",
                 "instant": False, "is_custom": True, "description": "x"}
        summary = it._rule_summary(ctx, "AAPL", it._evaluate(ctx, "AAPL", "custom_x", bogus, AS_OF), "custom_x", bogus)
        self.assertEqual(summary["rule_status"], "NOT_EVALUATED")
        self.assertEqual(summary["evidence_status"], "INSUFFICIENT")
        with self.assertRaises(it.ToolInputError):
            run_tool(ctx, "get_verified_financial_metrics", {"ticker": "AAPL", "metrics": ["Ebitda"]})

    def test_06_missing_historical_evaluation(self):
        h = run_tool(ctx_with(purchase(1, "AAPL", "2026-08-15")), "get_historical_evaluations", {"ticker": "AAPL", "reason_key": "revenue_growth"})
        self.assertFalse(h["longitudinal"])
        self.assertIn("no trend", h["note"])

    def test_07_same_day_purchase_and_evaluation(self):
        c = run_tool(ctx_with(purchase(1, "AAPL", AS_OF)), "compare_financial_periods", {"ticker": "AAPL"})["comparisons"]
        self.assertTrue(all(x["same_reporting_period"] for x in c))
        self.assertTrue(all("not evidence of change" in x["longitudinal_note"] for x in c))

    def test_08_new_sec_filings_and_no_future_leakage(self):
        ctx = ctx_with(purchase(1, "AMZN", "2026-03-02"), as_of="2026-10-28")
        f = run_tool(ctx, "check_new_sec_filings", {"ticker": "AMZN"})
        forms = {x["form"] for x in f["filings"]}
        self.assertIn("424B5", forms)
        self.assertGreaterEqual(f["new_periodic_reports"], 2)
        self.assertTrue(all("2026-03-02" < x["filed"] <= "2026-10-28" for x in f["filings"]))
        with self.assertRaises(it.ToolInputError):  # the 2026-10-29 earnings 8-K is after the analysis date
            run_tool(ctx, "search_filing_sections", {"ticker": "AMZN", "query": "net sales", "accession_number": "0001018724-26-000038"})

    def test_metrics_basis_is_explicit(self):
        m = run_tool(ctx_with(), "get_verified_financial_metrics", {"ticker": "AAPL", "metrics": ["OperatingCashFlow", "LongTermDebt"]})["metrics"]
        self.assertEqual(m[0]["basis"], "year_to_date")
        self.assertEqual(m[1]["basis"], "point_in_time_balance")


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = el.EvidenceLedger()
        self.fact = self.ledger.add(el.EvidenceUnit(kind="derived_metric", ticker="AMZN", filed="2026-07-31", values=[1.5413857, 0.15]))
        self.future = self.ledger.add(el.EvidenceUnit(kind="xbrl_fact", ticker="AMZN", filed="2026-11-30", values=[5.0]))
        self.passage = self.ledger.add(el.EvidenceUnit(kind="filing_passage", ticker="AMZN", filed="2026-07-31",
                                                       excerpt="We issued $15.0 billion of senior notes in the second quarter."))

    def check(self, **claim):
        base = {"claim_id": "c1", "claim_type": "numeric", "status": "SUPPORTED", "ticker": "AMZN"}
        return el.verify_claims([{**base, **claim}], self.ledger, "2026-10-29")[1]

    def test_09_supporting_and_contradicting_evidence_assessment(self):
        ctx = ctx_with(purchase(1, "AMZN", "2026-03-02"))
        engine = InvestigationEngine(EngineConfig("B3", "s", ["get_latest_thesis_evaluations"], pa.FINALIZE_ANSWER_TOOL,
                                                  {"max_tool_calls": 4, "max_retrieval_iterations": 4, "max_iterations": 6, "max_output_tokens": 100,
                                                   "max_seconds": 60, "max_gate_rejections": 1}, True, True), ctx, llm=MockLLM(
            calls(use("get_latest_thesis_evaluations")),
            calls(use("record_evidence_assessment", assessments=[{"topic": "debt", "supporting_evidence_ids": ["E999"], "contradicting_evidence_ids": [], "sufficiency": "SUFFICIENT"}])),
            lambda m, t, c: [use("record_evidence_assessment", assessments=[{"topic": "debt", "supporting_evidence_ids": [evaluation(m, "AMZN", "revenue_growth")["evidence_ids"][0]],
                                                                             "contradicting_evidence_ids": [evaluation(m, "AMZN", "debt_growth")["evidence_ids"][0]], "sufficiency": "CONFLICTING",
                                                                             "conflicts": ["revenue supports, debt contradicts"]}])],
            lambda m, t, c: [use("finalize_answer", sections=[{"key": "summary", "paragraphs": [{"text": "สรุปตามหลักฐาน", "claim_ids": []}]}], claims=[], scope_note="x")]))
        out = engine.run([{"role": "user", "content": "q"}])
        self.assertEqual(out["stop_reason"], "FINALIZED")
        self.assertIn("unknown evidence ids", json.dumps(out["trace"]["tool_calls"][1]["output"]))
        a = out["trace"]["assessments"][0]
        self.assertTrue(a["supporting_evidence_ids"] and a["contradicting_evidence_ids"])

    def test_10_incorrect_citations_rejected(self):
        self.assertEqual(self.check(proposition="Debt grew 154.1%, above the 15% limit", evidence_ids=[self.fact]), [])
        self.assertTrue(any("NUMBER_NOT_IN_EVIDENCE" in p for p in self.check(proposition="Debt grew 120.0%", evidence_ids=[self.fact])))
        self.assertTrue(any("UNKNOWN_EVIDENCE_ID" in p for p in self.check(proposition="Debt grew", evidence_ids=["E77"])))
        self.assertTrue(any("FUTURE_EVIDENCE" in p for p in self.check(proposition="x", evidence_ids=[self.future])))
        self.assertTrue(any("TICKER_MISMATCH" in p for p in self.check(proposition="x", ticker="AAPL", evidence_ids=[self.fact])))
        self.assertTrue(any("NO_EVIDENCE" in p for p in self.check(proposition="Debt grew", evidence_ids=[])))
        bad_quote = self.check(claim_type="causal_interpretation", proposition="Debt rose because of a notes offering",
                               evidence_ids=[self.passage], quoted_span="we acquired a large company for cash")
        self.assertTrue(any("QUOTED_SPAN_NOT_IN_CITED_PASSAGE" in p for p in bad_quote))
        good_quote = self.check(claim_type="causal_interpretation", proposition="Debt rose because of a notes offering",
                                evidence_ids=[self.passage], quoted_span="issued $15.0 billion of senior notes")
        self.assertEqual(good_quote, [])
        no_passage = self.check(claim_type="management_attribution", proposition="Management says demand drove it", evidence_ids=[self.fact])
        self.assertTrue(any("WITHOUT_FILING_PASSAGE" in p for p in no_passage))

    def test_number_parsing_form_names_and_thai_text(self):
        self.assertEqual(el.stated_numbers("อ่านเอกสาร 424B5 และ 10-Q ของปี 2026"), [])
        self.assertEqual(el.stated_numbers("รายได้โต16.4%เทียบเกณฑ์10%"), [(16.4, True), (10.0, True)])
        self.assertEqual(el.stated_numbers("หนี้ 42,232ล้านดอลลาร์"), [(42232.0, False)])

    def test_15_abstention_when_evidence_insufficient(self):
        self.assertEqual(self.check(claim_type="causal_interpretation", status="NOT_ESTABLISHED",
                                    proposition="The cause of the debt increase is not disclosed in the reviewed filings", evidence_ids=[]), [])


class GuardTests(unittest.TestCase):
    def test_12_unsupported_reassurance_detected(self):
        for text in ["พอร์ตของคุณไม่มีความเสี่ยง", "ไม่ต้องกังวลครับ", "ควรถือต่อ", "หุ้นตัวนี้ปลอดภัย", "Your portfolio looks good", "you should buy more"]:
            with self.subTest(text=text):
                self.assertTrue(answer_guard.find_reassurance(text))
        for text in ["การผ่านเกณฑ์ไม่ได้หมายความว่าไม่มีความเสี่ยง", "This does not mean there is no risk",
                     "เหตุผลทั้งสามข้อยังผ่านเกณฑ์ แต่ยังมีปัจจัยอื่นที่ต้องพิจารณา"]:
            with self.subTest(text=text):
                self.assertEqual(answer_guard.find_reassurance(text), [])

    def test_raw_codes_detected(self):
        self.assertTrue(answer_guard.find_raw_codes("สถานะ SATISFIED ตาม C1"))
        self.assertEqual(answer_guard.find_raw_codes("รายได้ผ่านเกณฑ์"), [])

    def test_intents(self):
        cases = {PORTFOLIO_Q: "portfolio_review", "เหตุผลที่ซื้อ Apple ยังจริงอยู่ไหม?": "thesis_check",
                 "มีอะไรที่ต้องระวัง?": "risk_review", "ทำไมรายได้โต แต่กำไรลด?": "change_explanation",
                 "มีอะไรเปลี่ยนไปจากตอนซื้อ?": "change_since_purchase"}
        for q, expected in cases.items():
            with self.subTest(q=q):
                self.assertEqual(intent_mod.classify(q, ["AAPL"]).intent, expected)
        self.assertEqual(intent_mod.classify("เหตุผลที่ซื้อ Apple ยังจริงอยู่ไหม?", ["AAPL"]).tickers, ["AAPL"])
        self.assertEqual(intent_mod.classify("ทำไมหนี้ amazon เพิ่ม", ["AAPL"]).task_scope, "CHANGE_EXPLANATION")


class ChatWorkflowTests(unittest.TestCase):
    def test_portfolio_review_end_to_end(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"), purchase(2, "AMZN", "2026-03-02"))
        pairs = [("AAPL", "revenue_growth"), ("AMZN", "debt_growth")]
        out, llm = run_chat(ctx, PORTFOLIO_Q, *portfolio_steps(["AAPL", "AMZN"], finalize_from_evaluations(pairs)))
        a = out["answer"]
        self.assertEqual(a["stop_reason"], "FINALIZED")
        self.assertEqual(a["intent"]["intent"], "portfolio_review")
        self.assertTrue(all(c["verified"] and c["evidence"] for c in a["claims"]))
        self.assertEqual(a["sections"][0]["title"], "เหตุผลที่ยังได้รับการสนับสนุน")
        self.assertIn("154.1%", out["answer_text"])
        t = out["trace"]
        import agent_config
        self.assertEqual(t["config"]["workflow_version"], agent_config.AGENT_WORKFLOW_VERSION)
        self.assertTrue(t["evidence"] and t["assessments"] and t["llm_calls"])
        self.assertEqual(t["usage"], {"input_tokens": 4000, "output_tokens": 800})
        self.assertIn("Intent: portfolio_review", llm.requests[0]["messages"][-1]["content"])

    def test_11_no_material_change_note_is_deterministic(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        out, _ = run_chat(ctx, PORTFOLIO_Q, *portfolio_steps(["AAPL"], finalize_from_evaluations([("AAPL", "revenue_growth")])))
        self.assertTrue(any("งวดเดียวกับตอนที่คุณซื้อ" in n for n in out["answer"]["system_notes"]))

    def test_07b_same_day_answer_cannot_claim_trend(self):
        out, _ = run_chat(ctx_with(purchase(1, "AAPL", AS_OF)), PORTFOLIO_Q,
                          *portfolio_steps(["AAPL"], finalize_from_evaluations([("AAPL", "operating_margin")])))
        self.assertTrue(out["answer"]["system_notes"])

    def test_12b_reassurance_rejected_then_corrected(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        bad = finalize_from_evaluations([("AAPL", "revenue_growth")], {"text": "พอร์ตของคุณไม่มีความเสี่ยง ไม่ต้องกังวล", "claim_ids": []})
        good = finalize_from_evaluations([("AAPL", "revenue_growth")], {"text": "การผ่านเกณฑ์ไม่ได้หมายความว่าไม่มีความเสี่ยง เกณฑ์นี้ไม่ได้ครอบคลุมราคาหรือการแข่งขัน", "claim_ids": []})
        steps = portfolio_steps(["AAPL"], bad) + [good]
        out, llm = run_chat(ctx, PORTFOLIO_Q, *steps)
        self.assertEqual(out["answer"]["stop_reason"], "FINALIZED")
        self.assertEqual(len(out["trace"]["gate_rejections"]), 1)
        self.assertIn("UNSUPPORTED_REASSURANCE", json.dumps(llm.requests[-1]["messages"][-1], ensure_ascii=False))
        self.assertNotIn("ไม่ต้องกังวล", out["answer_text"])

    def test_12c_persistent_reassurance_is_removed(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        bad = finalize_from_evaluations([("AAPL", "revenue_growth")], {"text": "หุ้นตัวนี้ปลอดภัย ควรถือต่อ", "claim_ids": []})
        out, _ = run_chat(ctx, PORTFOLIO_Q, *portfolio_steps(["AAPL"], bad), bad, bad)
        self.assertEqual(out["answer"]["stop_reason"], "GATE_REJECTIONS_EXHAUSTED")
        self.assertNotIn("ปลอดภัย", out["answer_text"])
        self.assertIn("ถูกตัดออก", out["answer_text"])
        self.assertTrue(out["trace"]["removed_paragraphs"])

    def test_10b_uncited_number_in_prose_rejected(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        invented = finalize_from_evaluations([("AAPL", "revenue_growth")], {"text": "กำไรน่าจะโต 45.0% ในปีหน้า", "claim_ids": ["c1"]})
        out, llm = run_chat(ctx, PORTFOLIO_Q, *portfolio_steps(["AAPL"], invented), invented, invented)
        self.assertNotIn("45.0%", out["answer_text"])
        self.assertIn("no linked claim's evidence contains it", json.dumps(out["trace"]["gate_rejections"], ensure_ascii=False))

    def test_13_incorrect_tool_selection(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"), purchase(2, "MSFT", "2026-05-01"))
        fin = finalize_from_evaluations([("AAPL", "revenue_growth")])
        steps = [calls(use("get_user_portfolio"), use("get_latest_thesis_evaluations"), use("delete_all_holdings")),
                 calls(use("compare_financial_periods", ticker="AAPL"), use("check_new_sec_filings", ticker="AAPL")),  # MSFT skipped
                 assess(), fin,
                 calls(use("compare_financial_periods", ticker="MSFT"), use("check_new_sec_filings", ticker="MSFT")), fin]
        out, _ = run_chat(ctx, PORTFOLIO_Q, *steps)
        self.assertEqual(out["trace"]["tool_calls"][2]["error"], "UNAVAILABLE_TOOL")
        rejection = json.dumps(out["trace"]["gate_rejections"])
        self.assertIn("required check not done: compare_financial_periods for MSFT", rejection)
        self.assertEqual(out["answer"]["stop_reason"], "FINALIZED")

    def test_truncated_answer_is_rejected_not_accepted(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        good = finalize_from_evaluations([("AAPL", "revenue_growth")])
        cut = lambda m, t, c: ([use("finalize_answer", claims=[], scope_note="")], "max_tokens")
        out, llm = run_chat(ctx, PORTFOLIO_Q, *portfolio_steps(["AAPL"], cut), good)
        self.assertEqual(out["answer"]["stop_reason"], "FINALIZED")
        self.assertIn("cut off", json.dumps(out["trace"]["gate_rejections"]))
        self.assertIn("16.4%", out["answer_text"])

    def test_14_budget_exhaustion_forces_finalize(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        loop = calls(use("check_new_sec_filings", ticker="AAPL"))
        forced = lambda m, t, c: [use("finalize_answer", sections=[{"key": "summary", "paragraphs": [
            {"text": "ตรวจได้ไม่ครบเพราะครบงบการค้นหา", "claim_ids": []}]}], claims=[], scope_note="ไม่ครบ")]
        with patch.dict(pa.CHAT_BUDGET, {"max_tool_calls": 3, "max_retrieval_iterations": 10}):
            out, llm = run_chat(ctx, PORTFOLIO_Q, loop, loop, loop, forced)
        self.assertEqual(out["answer"]["stop_reason"], "BUDGET_EXHAUSTED")
        self.assertEqual(llm.requests[-1]["tool_choice"], {"type": "tool", "name": "finalize_answer"})
        self.assertEqual(llm.requests[-1]["tools"], ["finalize_answer"])
        self.assertTrue(any("ครบงบ" in n for n in out["answer"]["system_notes"]))


if __name__ == "__main__":
    unittest.main()
