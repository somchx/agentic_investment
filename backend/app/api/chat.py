from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import db
from agent import answer_portfolio_question
from app.api.reports import _build_portfolio_context
from app.rate_limit import limiter
from app.security import current_user_id

router = APIRouter(prefix="/api/conversations", tags=["chat"])


@router.get("")
def list_conversations(user_id: int = Depends(current_user_id)):
    """Sidebar list -- id, title, updated_at, no message bodies."""
    return db.list_conversations(user_id)


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


@router.post("/messages")
@limiter.limit("10/minute")
def send_message(request: Request, body: SendMessageBody, user_id: int = Depends(current_user_id)):
    """Sends one question to the portfolio-wide agent and persists both
    sides of the exchange -- creates a new conversation on the first
    message (conversation_id=None) or appends to an existing one. Costs
    real LLM API budget -- only ever called when the user explicitly sends
    a message, never automatically. Rate-limited, same reasoning as
    /api/ask-agent."""
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

    try:
        context = _build_portfolio_context(user_id)
        result = answer_portfolio_question(context, question, history=history)
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        raise HTTPException(status_code=500, detail=str(e))

    db.append_message(
        conversation_id, "assistant", result["answer"],
        cost_usd=result["cost_usd"], tool_calls=result["tool_calls"],
    )

    return {
        "conversation_id": conversation_id,
        "answer": result["answer"],
        "tool_calls": result["tool_calls"],
        "cost_usd": result["cost_usd"],
    }
