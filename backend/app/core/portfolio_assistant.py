"""Chat assistant on the shared investigation engine (workflow 2.0).

answer_portfolio_question_v2 = Intent Analyzer -> InvestigationEngine in the
chat configuration (B3 verification + portfolio tools) -> chat-specific
Evidence Gate (required checks, paragraph-level number/citation checks,
reassurance guard) -> deterministic system notes -> human-readable answer
with per-claim evidence for progressive disclosure -> stored trace.
"""

from datetime import datetime, timezone

import db

from agent_config import CHAT_BUDGET
from answer_guard import check_answer_text
from evidence_ledger import _matches, stated_numbers
from intent import classify
from investigation_engine import EngineConfig, InvestigationEngine
from investigation_prompts import CHAT_SYSTEM_PROMPT, language_line
from investigation_tools import CHAT_TOOLS, ToolContext

SECTION_KEYS = ["summary", "supported", "changes", "findings", "risks", "next_checks"]
SECTION_TITLES = {
    "th": {"summary": "สรุปพอร์ตของคุณ", "supported": "เหตุผลที่ยังได้รับการสนับสนุน", "changes": "สิ่งที่เปลี่ยนแปลงจากตอนซื้อ",
           "findings": "ข้อค้นพบเพิ่มเติมจาก AI", "risks": "ความเสี่ยงหรือข้อมูลที่ยังไม่แน่ชัด", "next_checks": "สิ่งที่ควรตรวจสอบต่อ"},
    "en": {"summary": "Your portfolio in brief", "supported": "Reasons still supported", "changes": "What changed since purchase",
           "findings": "Additional AI findings", "risks": "Risks and what is still uncertain", "next_checks": "What to check next"},
}

FINALIZE_ANSWER_TOOL = {
    "name": "finalize_answer",
    "description": "Submit the final answer: readable sections whose paragraphs link to evidence-backed claims.",
    "input_schema": {"type": "object", "properties": {
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "key": {"type": "string", "enum": SECTION_KEYS},
            "paragraphs": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "claim_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["text", "claim_ids"]}}},
            "required": ["key", "paragraphs"]}},
        "claims": {"type": "array", "items": {"type": "object", "properties": {
            "claim_id": {"type": "string"}, "ticker": {"type": "string"}, "reason_key": {"type": "string"},
            "proposition": {"type": "string"},
            "claim_type": {"type": "string", "enum": ["numeric", "management_attribution", "causal_interpretation", "uncertainty"]},
            "status": {"type": "string", "enum": ["SUPPORTED", "CONTRADICTED", "NOT_ESTABLISHED"]},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "quoted_span": {"type": "string"}},
            "required": ["claim_id", "proposition", "claim_type", "status", "evidence_ids"]}},
        "scope_note": {"type": "string"},
    }, "required": ["sections", "claims", "scope_note"]},
}

PER_TICKER_REQUIRED = {"compare_financial_periods", "check_new_sec_filings"}


def _paragraphs(final: dict):
    for s in final.get("sections") or []:
        for p in s.get("paragraphs") or []:
            yield s.get("key"), p


def paragraph_problems(final: dict, ledger) -> list[str]:
    """Every number in answer prose must be backed by the cited claims'
    evidence; paragraphs may only link claims that exist."""
    claims = {c.get("claim_id"): c for c in final.get("claims") or []}
    problems = []
    for key, p in _paragraphs(final):
        ids = p.get("claim_ids") or []
        missing = [i for i in ids if i not in claims]
        if missing:
            problems.append(f"paragraph in '{key}' links unknown claim ids {missing}")
        values = [v for i in ids if i in claims for e in claims[i].get("evidence_ids") or []
                  for v in (ledger.get(e).values if ledger.get(e) else [])]
        for stated, pct in stated_numbers(p.get("text", "")):
            if not _matches(stated, pct, values):
                problems.append(f"paragraph in '{key}' states {stated:g}{'%' if pct else ''} but no linked claim's evidence contains it")
    return problems


def make_chat_gate(intent, scope_tickers: list[str], ledger):
    def gate(final: dict, run) -> list[str]:
        problems = []
        for tool in intent.required_tools:
            if tool in PER_TICKER_REQUIRED:
                for t in scope_tickers:
                    if not run.called(tool, t):
                        problems.append(f"required check not done: {tool} for {t}")
            elif not run.called(tool):
                problems.append(f"required check not done: {tool}")
        if not any(p.get("text", "").strip() for _, p in _paragraphs(final)):
            problems.append("answer has no text")
        problems += paragraph_problems(final, ledger)
        texts = [p.get("text", "") for _, p in _paragraphs(final)] + [final.get("scope_note") or ""]
        problems += check_answer_text(texts)
        return problems
    return gate


def sanitize(final: dict, verification: list[dict], ledger) -> tuple[dict, list[str]]:
    """Used only when the gate's rejection budget ran out: unverified claims
    are downgraded to NOT_ESTABLISHED and paragraphs that still break a rule
    are withheld, so nothing unverified is shown as fact."""
    removed = []
    bad = {v["claim_id"] for v in verification if not v["verified"]}
    for c in final.get("claims") or []:
        if c.get("claim_id") in bad and c.get("status") != "NOT_ESTABLISHED":
            c["status"], c["downgraded"] = "NOT_ESTABLISHED", True
    for s in final.get("sections") or []:
        kept = []
        for p in s.get("paragraphs") or []:
            single = {"sections": [{"key": s.get("key"), "paragraphs": [p]}], "claims": final.get("claims") or []}
            issues = paragraph_problems(single, ledger) + check_answer_text([p.get("text", "")])
            if issues or set(p.get("claim_ids") or []) & bad:
                removed.append(p.get("text", "")[:200])
            else:
                kept.append(p)
        s["paragraphs"] = kept
    final["sections"] = [s for s in final.get("sections") or [] if s.get("paragraphs")]
    return final, removed


def system_notes(trace: dict, lang: str, stop_reason: str | None) -> list[str]:
    """Deterministic facts read from tool outputs (never from the model)."""
    th = lang == "th"
    notes = []
    same = [c["input"].get("ticker") for c in trace["tool_calls"] if c["name"] == "compare_financial_periods" and not c.get("error")
            and (c["output"].get("comparisons") or []) and all(x.get("same_reporting_period") for x in c["output"]["comparisons"] if "then" in x)]
    if same:
        notes.append((f"งบการเงินล่าสุดของ {', '.join(sorted(set(same)))} ยังเป็นงวดเดียวกับตอนที่คุณซื้อ จึงยังไม่มีข้อมูลงวดใหม่ให้เปรียบเทียบการเปลี่ยนแปลง"
                      if th else f"The latest financial statements for {', '.join(sorted(set(same)))} are the same reporting period as at purchase, so there is no newer period to compare yet."))
    portfolio = next((c["output"] for c in trace["tool_calls"] if c["name"] == "get_user_portfolio" and not c.get("error")), None)
    if portfolio and portfolio.get("holdings") and not portfolio.get("prices_complete"):
        notes.append("ไม่แสดงมูลค่าตลาดหรือกำไร/ขาดทุนของบางตัว เพราะไม่มีราคาที่ตรวจสอบได้ในขณะนี้" if th
                     else "Market value / P&L is not shown for some holdings because no verified price was available.")
    if stop_reason == "BUDGET_EXHAUSTED":
        notes.append("การตรวจสอบรอบนี้หยุดเพราะครบงบการค้นหาที่กำหนด บางประเด็นจึงยังไม่ได้ตรวจ" if th
                     else "This investigation stopped at its search budget, so some points were not checked.")
    if stop_reason == "GATE_REJECTIONS_EXHAUSTED":
        notes.append("บางข้อความถูกตัดออกหรือลดระดับเป็น 'ยังไม่ยืนยัน' เพราะตรวจหลักฐานรองรับไม่ผ่าน" if th
                     else "Some statements were removed or marked unconfirmed because their evidence did not verify.")
    return notes


def render_text(answer: dict, lang: str) -> str:
    titles = SECTION_TITLES["th" if lang == "th" else "en"]
    parts = []
    for s in answer["sections"]:
        body = "\n\n".join(p["text"] for p in s["paragraphs"])
        parts.append(f"**{s['title'] or titles.get(s['key'], s['key'])}**\n\n{body}")
    if answer.get("system_notes"):
        parts.append("\n".join(f"> {n}" for n in answer["system_notes"]))
    if answer.get("scope_note"):
        parts.append(f"_{answer['scope_note']}_")
    return "\n\n".join(parts)


def answer_portfolio_question_v2(user_id: int, question: str, history: list[dict] | None = None, language: str | None = None,
                                 investor_profile_context: str | None = None, analysis_date: str | None = None, llm=None,
                                 ctx: ToolContext | None = None, focus_ticker: str | None = None, on_event=None) -> dict:
    lang = "th" if language == "th" else "en"
    analysis_date = analysis_date or (ctx.analysis_date if ctx else datetime.now(timezone.utc).date().isoformat())
    ctx = ctx or ToolContext(analysis_date=analysis_date, user_id=user_id)
    held = ctx.held_tickers()
    intent = classify(question, held)
    if focus_ticker and not intent.tickers:  # asked from one company's page
        intent = classify(f"{question} {focus_ticker}", held)
    scope = [t for t in intent.tickers if t in held] or (held if not intent.tickers else [])

    reason_keys = sorted({r["reason_key"] for p in ctx.purchases() for r in p.get("reasons") or []}
                         | ({r["reason_key"] for r in db.list_reasons(user_id=user_id)} if user_id is not None else set()))
    system = CHAT_SYSTEM_PROMPT + language_line(language)
    config = EngineConfig(mode="chat", system_prompt=system, tool_names=CHAT_TOOLS, finalize_tool=FINALIZE_ANSWER_TOOL,
                          budget=CHAT_BUDGET, require_assessment=True, verify=True, reason_keys=reason_keys or None,
                          gate=make_chat_gate(intent, scope, ctx.ledger))
    brief = (f"Analysis date: {analysis_date}\nHoldings (tickers): {held or 'none'}\n"
             f"Intent: {intent.intent} (task scope {intent.task_scope}); tickers asked about: {intent.tickers or 'all holdings'}\n"
             f"REQUIRED checks before answering: {', '.join(intent.required_tools) or 'none'}"
             + (f" (per ticker for {', '.join(PER_TICKER_REQUIRED & set(intent.required_tools))}: {scope})" if scope else "")
             + (f"\nInvestor profile (context only; never turn it into a trade recommendation):\n{investor_profile_context}" if investor_profile_context else "")
             + f"\n\nUser question: {question}")
    messages = [*(history or []), {"role": "user", "content": brief}]

    if on_event:
        on_event({"type": "intent", "intent": intent.intent, "tickers": intent.tickers, "scope": scope,
                  "required_tools": intent.required_tools, "task_scope": intent.task_scope})
    engine = InvestigationEngine(config, ctx, llm=llm, on_event=on_event)
    result = engine.run(messages)
    final = result["final"] or {"sections": [], "claims": [], "scope_note": ""}
    removed = []
    if result["stop_reason"] != "FINALIZED":
        final, removed = sanitize(final, result["verification"]["claims"], ctx.ledger)

    verified = {v["claim_id"]: v for v in result["verification"]["claims"]}
    claims = []
    for c in final.get("claims") or []:
        v = verified.get(c.get("claim_id"), {})
        claims.append({**c, "verified": v.get("verified", False), "verification_issues": v.get("issues", []),
                       "evidence": [ctx.ledger.get(e).public() for e in c.get("evidence_ids") or [] if ctx.ledger.get(e)]})
    titles = SECTION_TITLES[lang]
    sections = [{"key": s["key"], "title": (titles["summary"] if s["key"] == "summary" and intent.intent == "portfolio_review"
                                            else ("สรุป" if lang == "th" else "Summary") if s["key"] == "summary" else titles[s["key"]]),
                 "paragraphs": s["paragraphs"]}
                for k in SECTION_KEYS for s in final.get("sections") or [] if s.get("key") == k and s.get("paragraphs")]
    answer = {
        "intent": intent.as_dict(), "sections": sections, "claims": claims, "scope_note": final.get("scope_note") or "",
        "system_notes": system_notes(result["trace"], lang, result["stop_reason"]), "stop_reason": result["stop_reason"],
        "analysis_date": analysis_date,
    }
    if not sections:
        answer["sections"] = [{"key": "summary", "title": titles["summary"] if intent.intent == "portfolio_review" else ("สรุป" if lang == "th" else "Summary"),
                               "paragraphs": [{"text": ("ระบบยังไม่สามารถสรุปคำตอบที่มีหลักฐานรองรับได้ในรอบนี้ กรุณาลองถามให้เจาะจงขึ้น"
                                                        if lang == "th" else "No evidence-backed answer could be produced this time; try a more specific question."),
                                               "claim_ids": []}]}]
    trace = {**result["trace"], "question": question, "intent": intent.as_dict(), "final": final,
             "verification": result["verification"], "unresolved_problems": result["unresolved_problems"], "removed_paragraphs": removed}
    return {"answer": answer, "answer_text": render_text(answer, lang), "trace": trace,
            "cost_usd": trace["cost_usd"], "tool_calls": [{"name": c["name"], "arguments": c["input"], "error": c.get("error"),
                                                            "evidence_ids": c["evidence_ids"], "latency_ms": c["latency_ms"]}
                                                           for c in trace["tool_calls"]]}
