from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent import answer_portfolio_question, answer_question
from app.rate_limit import limiter
from app.security import current_user_id
from personalization import investigate_and_personalize
from portfolio_report import STATUS_ICON, build_company_reasons, evaluate
from tools import check_reason_status

router = APIRouter(prefix="/api", tags=["reports"])


def get_company_report(ticker: str, user_id: int | None) -> dict:
    company_name, reasons = build_company_reasons(ticker, user_id=user_id)

    out_reasons = []
    for reason, facts, denom_facts in reasons:
        reason_dates = sorted({f.filed for f in facts})
        if len(reason_dates) < 2:
            out_reasons.append({
                "reason_key": reason.reason_id,
                "description": reason.description,
                "status": "Not enough data",
                "icon": STATUS_ICON["Not enough data"],
                "computed_value": None,
                "as_of": None,
                "explanation": "Not enough filing history for this metric yet.",
                "evidence": [],
                "previous_status": None,
                "changed": False,
            })
            continue

        latest_as_of, previous_as_of = reason_dates[-1], reason_dates[-2]
        latest = evaluate(reason, facts, denom_facts, latest_as_of)
        previous = evaluate(reason, facts, denom_facts, previous_as_of)

        out_reasons.append({
            "reason_key": reason.reason_id,
            "description": reason.description,
            "status": latest.status,
            "icon": STATUS_ICON[latest.status],
            "computed_value": latest.computed_value,
            "as_of": latest_as_of,
            "explanation": latest.explanation,
            "evidence": [f.label() for f in latest.supporting_evidence],
            "conflicting_evidence": [f.label() for f in latest.conflicting_evidence],
            "previous_status": previous.status,
            "previous_as_of": previous_as_of,
            "changed": previous.status != latest.status,
        })

    return {"ticker": ticker, "company_name": company_name, "reasons": out_reasons}


@router.get("/report/{ticker}")
def api_report(ticker: str, user_id: int = Depends(current_user_id)):
    try:
        return get_company_report(ticker.upper(), user_id)
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        raise HTTPException(status_code=500, detail=str(e))


class ChatTurn(BaseModel):
    role: str
    content: str


class AskAgentBody(BaseModel):
    question: str
    history: list[ChatTurn] = []


@router.post("/ask-agent/{ticker}")
@limiter.limit("10/minute")
def api_ask_agent(request: Request, ticker: str, body: AskAgentBody, user_id: int = Depends(current_user_id)):
    """Costs real LLM API budget -- only ever called when the user
    explicitly clicks it in the frontend, never automatically. Free-form
    Q&A (agent.answer_question), not the structured full-report loop --
    `history` lets a chat-style UI carry context across turns without any
    server-side conversation storage.

    Rate-limited (10/minute/user) -- not an abuse defense (this is a
    single-investor prototype, not a public API), just a backstop against
    an accidental double-click or a runaway frontend retry burning API
    budget."""
    try:
        return answer_question(
            ticker.upper(), body.question, history=[h.model_dump() for h in body.history],
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


def _build_portfolio_context(user_id: int) -> str:
    """Plain-text summary of the user's current positions for the
    portfolio-wide chat prompt -- same underlying data as
    GET /api/portfolio/summary (db.list_purchases + check_reason_status),
    just formatted as prose Claude can read directly instead of JSON."""
    import db

    held = db.list_held_tickers(user_id)
    if not held:
        return "The user currently has no recorded positions."

    lines = []
    for ticker in held:
        for p in db.list_purchases(user_id, ticker=ticker):
            snapshot = p.get("reason_snapshot")
            if not p.get("reason_key") or not snapshot:
                lines.append(f"- {ticker}: {p['quantity']} sh @ ${p['purchase_price']} on {p['purchase_date']}, no reason attached.")
                continue
            current = check_reason_status(ticker, p["reason_key"])
            current_status = current.get("status", "unknown") if "error" not in current else "unknown (could not re-check)"
            still_true = current_status == snapshot["status_at_purchase"]
            lines.append(
                f"- {ticker}: {p['quantity']} sh @ ${p['purchase_price']} on {p['purchase_date']}, "
                f"bought because \"{snapshot['description']}\" (was {snapshot['status_at_purchase']} at purchase, "
                f"currently {current_status} -- {'still holds' if still_true else 'NO LONGER HOLDS'})."
            )
    return "\n".join(lines)


class PortfolioAskAgentBody(BaseModel):
    question: str
    history: list[ChatTurn] = []


@router.post("/ask-agent")
@limiter.limit("10/minute")
def api_ask_agent_portfolio(request: Request, body: PortfolioAskAgentBody, user_id: int = Depends(current_user_id)):
    """Portfolio-wide version of /ask-agent/{ticker} -- for questions that
    aren't scoped to one company ("how's my portfolio doing, anything I
    should worry about"). Costs real LLM API budget, same explicit-click-
    only rule as the per-ticker endpoint. Rate-limited, same reasoning as
    /ask-agent/{ticker} above."""
    try:
        context = _build_portfolio_context(user_id)
        return answer_portfolio_question(
            context, body.question, history=[h.model_dump() for h in body.history],
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


class PersonalizeBody(BaseModel):
    profile_id: int | None = None
    profile: str | None = None


@router.post("/personalize/{ticker}")
@limiter.limit("10/minute")
def api_personalize(request: Request, ticker: str, body: PersonalizeBody, user_id: int = Depends(current_user_id)):
    """Also costs real LLM API budget -- same explicit-click-only rule and
    rate limit as /ask-agent above."""
    import db
    if not body.profile:
        raise HTTPException(status_code=400, detail="missing 'profile' (profile name)")
    profile = db.get_profile_by_name(body.profile, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"no investor profile named {body.profile!r}")
    try:
        return investigate_and_personalize(ticker.upper(), profile)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
