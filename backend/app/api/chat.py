import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
from app.api.language import ui_language
from app.api.reports import _build_investor_profile_context
from portfolio_assistant import answer_portfolio_question_v2
from app.rate_limit import limiter
from app.security import current_user_id

router = APIRouter(prefix="/api/conversations", tags=["chat"])


@router.get("")
def list_conversations(user_id: int = Depends(current_user_id)):
    """Sidebar list -- id, title, updated_at, no message bodies."""
    return db.list_conversations(user_id)


@router.get("/traces/{trace_id}")
def get_trace(trace_id: int, user_id: int = Depends(current_user_id)):
    """Full investigation trace behind one assistant answer (Advanced mode)."""
    trace = db.get_agent_trace(trace_id, user_id)
    if not trace:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, user_id: int = Depends(current_user_id)):
    conversation = db.get_conversation(conversation_id, user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, user_id: int = Depends(current_user_id)):
    db.delete_conversation(conversation_id, user_id)
    return {"ok": True}


class SendMessageBody(BaseModel):
    question: str
    conversation_id: int | None = None


def _start_turn(body: "SendMessageBody", user_id: int) -> tuple[str, int, list[dict]]:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    if body.conversation_id is not None:
        conversation = db.get_conversation(body.conversation_id, user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="conversation not found")
        conversation_id = body.conversation_id
        history = [{"role": m["role"], "content": m["content"]} for m in conversation["messages"]]
    else:
        conversation_id = db.create_conversation(user_id, question)
        history = []
    db.append_message(conversation_id, "user", question)
    return question, conversation_id, history


def _answer_and_store(request: Request, user_id: int, question: str, conversation_id: int, history: list[dict], on_event=None) -> dict:
    result = answer_portfolio_question_v2(
        user_id, question, history=history, language=ui_language(request),
        investor_profile_context=_build_investor_profile_context(user_id), on_event=on_event,
    )
    trace = result["trace"]
    trace_id = db.save_agent_trace(user_id, "chat", trace, question=question,
                                   tickers=result["answer"]["intent"]["tickers"] or None)
    db.append_message(
        conversation_id, "assistant", result["answer_text"], cost_usd=result["cost_usd"],
        tool_calls=result["tool_calls"], answer=result["answer"], trace_id=trace_id,
    )
    return {
        "conversation_id": conversation_id,
        "answer": result["answer_text"],
        "answer_structured": result["answer"],
        "trace_id": trace_id,
        "tool_calls": result["tool_calls"],
        "cost_usd": result["cost_usd"],
        "usage": trace["usage"],
        "latency_ms": trace["latency_ms"],
    }


@router.post("/messages")
@limiter.limit("10/minute")
def send_message(request: Request, body: SendMessageBody, user_id: int = Depends(current_user_id)):
    """Sends one question to the portfolio-wide agent and persists both
    sides of the exchange -- creates a new conversation on the first
    message (conversation_id=None) or appends to an existing one. Costs
    real LLM API budget -- only ever called when the user explicitly sends
    a message, never automatically. Rate-limited, same reasoning as
    /api/ask-agent."""
    question, conversation_id, history = _start_turn(body, user_id)
    try:
        return _answer_and_store(request, user_id, question, conversation_id, history)
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages/stream")
@limiter.limit("10/minute")
def send_message_stream(request: Request, body: SendMessageBody, user_id: int = Depends(current_user_id)):
    """Same paid call as POST /messages, but streams the investigation's
    progress as Server-Sent Events while it runs (intent, each LLM round,
    each tool call with its JSON input/output preview, gate decisions),
    ending with one `done` event carrying the normal response body, or an
    `error` event. Progress is display-only: it is built from the same
    events the stored trace records."""
    question, conversation_id, history = _start_turn(body, user_id)
    events: queue.Queue = queue.Queue()

    def work():
        try:
            events.put({"type": "done", "response": _answer_and_store(request, user_id, question, conversation_id, history, on_event=events.put)})
        except Exception as e:  # noqa: BLE001 -- reported to the client as an error event
            events.put({"type": "error", "detail": str(e), "conversation_id": conversation_id})

    threading.Thread(target=work, daemon=True).start()

    def stream():
        yield _sse({"type": "started", "conversation_id": conversation_id})
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            yield _sse(event)
            if event["type"] in ("done", "error"):
                return

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
