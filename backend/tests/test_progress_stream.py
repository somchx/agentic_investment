"""Live progress events (display-only) and the SSE chat endpoint -- offline."""
import json
import unittest
from unittest.mock import MagicMock, patch

import portfolio_assistant as pa
from test_agentic_investigation import PORTFOLIO_Q, MockLLM, ctx_with, finalize_from_evaluations, portfolio_steps, purchase


class ProgressEventTests(unittest.TestCase):
    def test_engine_emits_ordered_progress_events(self):
        events = []
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        llm = MockLLM(*portfolio_steps(["AAPL"], finalize_from_evaluations([("AAPL", "revenue_growth")])))
        with patch.object(pa, "db"):
            out = pa.answer_portfolio_question_v2(None, PORTFOLIO_Q, language="th", llm=llm, ctx=ctx, on_event=events.append)
        kinds = [e["type"] for e in events]
        self.assertEqual(kinds[0], "intent")
        self.assertEqual(kinds[-1], "gate_accepted")
        self.assertEqual(kinds.count("tool_start"), kinds.count("tool_end"))
        self.assertEqual(kinds.count("llm_end"), len(out["trace"]["llm_calls"]))
        end = next(e for e in events if e["type"] == "tool_end" and e["name"] == "get_user_portfolio")
        self.assertTrue(end["evidence_ids"] and "holdings" in json.dumps(end["output"]))
        self.assertGreater(events[-1]["counters"]["tool_calls"], 0)

    def test_failing_listener_does_not_break_investigation(self):
        ctx = ctx_with(purchase(1, "AAPL", "2026-08-15"))
        llm = MockLLM(*portfolio_steps(["AAPL"], finalize_from_evaluations([("AAPL", "revenue_growth")])))

        def boom(event):
            if event["type"] != "intent":
                raise RuntimeError("listener bug")
        with patch.object(pa, "db"):
            out = pa.answer_portfolio_question_v2(None, PORTFOLIO_Q, language="th", llm=llm, ctx=ctx, on_event=boom)
        self.assertEqual(out["answer"]["stop_reason"], "FINALIZED")


class StreamEndpointTests(unittest.TestCase):
    def test_sse_streams_progress_then_done(self):
        from fastapi.testclient import TestClient
        import app.api.chat as chat
        from app.main import app
        from app.security import current_user_id

        def fake_answer(user_id, question, on_event=None, **kw):
            on_event({"type": "intent", "intent": "portfolio_review"})
            on_event({"type": "tool_start", "name": "get_user_portfolio", "input": {}})
            return {"answer_text": "ok", "answer": {"intent": {"tickers": []}}, "trace": {"usage": {}, "latency_ms": 1},
                    "tool_calls": [], "cost_usd": 0.0}
        app.dependency_overrides[current_user_id] = lambda: 1
        try:
            with patch.object(chat, "db", MagicMock(create_conversation=MagicMock(return_value=7), save_agent_trace=MagicMock(return_value=3))), \
                 patch.object(chat, "answer_portfolio_question_v2", side_effect=fake_answer), \
                 patch.object(chat, "_build_investor_profile_context", return_value=""):
                r = TestClient(app).post("/api/conversations/messages/stream", json={"question": "q"})
        finally:
            app.dependency_overrides.clear()
        self.assertEqual(r.headers["content-type"].split(";")[0], "text/event-stream")
        events = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]
        self.assertEqual([e["type"] for e in events], ["started", "intent", "tool_start", "done"])
        self.assertEqual(events[-1]["response"]["trace_id"], 3)
        self.assertEqual(events[0]["conversation_id"], 7)


if __name__ == "__main__":
    unittest.main()
