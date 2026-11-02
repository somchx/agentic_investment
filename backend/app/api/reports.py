import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent import answer_portfolio_question, answer_question, run_with_llm
from app.api.language import ui_language
from app.rate_limit import limiter
from app.security import current_user_id
from personalization import investigate_and_personalize
from portfolio_report import STATUS_ICON, build_company_reasons, evaluate
from sec_client import SecDataUnavailableError, UnsupportedTickerError, get_data_freshness
from tools import check_reason_status, evaluate_frozen_reason

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reports"])


HISTORY_POINTS = 8


def _rule_fields(reason) -> dict:
    # The rule itself, so the UI can draw the threshold line on the chart.
    return {"comparison": reason.comparison, "threshold": reason.threshold, "kind": reason.kind}


def _status_history(reason, facts, denom_facts, reason_dates: list[str], latest) -> list[dict]:
    """The same mechanical evaluation re-run at each of the last few filing
    dates (oldest first), for the reason's trend chart. Free -- no LLM."""
    points = []
    for as_of in reason_dates[-HISTORY_POINTS:-1]:
        ev = evaluate(reason, facts, denom_facts, as_of)
        if ev.computed_value is not None:
            points.append({"as_of": as_of, "value": ev.computed_value, "status": ev.status})
    if latest.computed_value is not None:
        points.append({"as_of": reason_dates[-1], "value": latest.computed_value, "status": latest.status})
    return points


def get_company_report(ticker: str, user_id: int | None) -> dict:
    company_name, reasons = build_company_reasons(ticker, user_id=user_id)

    out_reasons = []
    for reason, facts, denom_facts in reasons:
        reason_dates = sorted({f.filed for f in facts})
        if len(reason_dates) < 2:
            out_reasons.append({
                "reason_key": reason.reason_id,
                "description": reason.description,
                **_rule_fields(reason),
                "history": [],
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
            **_rule_fields(reason),
            "history": _status_history(reason, facts, denom_facts, reason_dates, latest),
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

    # Provenance (Code Audit Session 3, item 4): when this company's SEC
    # cache was actually last fetched, so a viewer can tell whether "as of"
    # a reason's evidence date is trustworthy or possibly behind a filing
    # published since the last successful refresh.
    return {
        "ticker": ticker, "company_name": company_name, "reasons": out_reasons,
        "data_freshness": get_data_freshness(ticker),
    }


@router.get("/report/{ticker}")
def api_report(ticker: str, user_id: int = Depends(current_user_id)):
    try:
        return get_company_report(ticker.upper(), user_id)
    except Exception as e:  # noqa: BLE001 -- surface the real error to the frontend
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investigate/{ticker}")
@limiter.limit("10/minute")
def api_investigate(request: Request, ticker: str, user_id: int = Depends(current_user_id)):
    """The Structured Investigation path -- calls agent.run_with_llm
    directly, which is gated by the Evidence Assessor (assess_sufficiency)
    and can only return via finalize_report or an explicit escalation.
    This is deliberately a SEPARATE endpoint from /ask-agent: that one
    (_chat_loop) is free-form conversational Q&A with no schema and no
    Evidence Gate at all -- fine for "how's my portfolio doing" but not
    the audited investigation this project's research claims are actually
    measured against. Exposing this as its own button/endpoint answers a
    real external code-audit finding (Session 3, item 5: the web app had
    no user-facing path that actually exercised the Gate) -- previously
    run_with_llm was only reachable via personalization or CLI/experiment
    scripts, never from the web UI.

    Costs real LLM API budget -- only ever called when the user explicitly
    clicks it in the frontend, never automatically. Persists the result to
    investigation_runs (db.save_investigation_result), same as
    personalization's pipeline, so this shows up in the same audit trail.
    """
    import db

    ticker_upper = ticker.upper()
    try:
        result = run_with_llm(ticker_upper, language=ui_language(request))
    except UnsupportedTickerError as e:
        # Distinct from "valid company, no evidence found" -- this ticker
        # was never a real investigation to begin with, so it's a 400, not
        # a completed report (Code Audit Session 4 follow-up, item 1).
        raise HTTPException(status_code=400, detail=f"Unsupported ticker: {e}")
    except SecDataUnavailableError as e:
        # SEC itself is unreachable and nothing was cached -- this must
        # never be presented as a completed analysis (Code Audit Session 4
        # follow-up, item 1/3). Full detail stays server-side; the client
        # gets a plain "try again later" signal via 503.
        logger.error("SEC data source unavailable investigating %s: %s", ticker_upper, e)
        raise HTTPException(
            status_code=503,
            detail="Data source unavailable: SEC EDGAR could not be reached. Please try again later.",
        )
    except Exception as e:  # noqa: BLE001 -- genuinely unexpected; full detail stays server-side
        logger.error("Unexpected failure investigating %s: %s", ticker_upper, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error during investigation.")
    db.save_investigation_result(result)
    return db.save_ai_summary(user_id, ticker_upper, result, _summary_data_as_of(ticker_upper, user_id, result))


def _summary_data_as_of(ticker: str, user_id: int, result: dict) -> str | None:
    """Latest filing date behind the reasons this run covered -- a free,
    mechanical lookup (same report the reason cards use), so the UI can say
    "data as of <date>" next to the AI Summary."""
    try:
        reasons = get_company_report(ticker, user_id)["reasons"]
    except Exception:  # noqa: BLE001 -- the date is a nice-to-have; never fail a paid run over it
        logger.warning("Could not compute data_as_of for %s", ticker, exc_info=True)
        return None
    covered = {r.get("reason_key") for r in result.get("reasons") or []}
    dates = [r["as_of"] for r in reasons if r["as_of"] and (not covered or r["reason_key"] in covered)]
    return max(dates) if dates else None


@router.get("/investigate/{ticker}")
def api_latest_investigation(ticker: str, user_id: int = Depends(current_user_id)):
    """The last stored AI Summary for this user and ticker, or null. Free --
    reads the database only, never calls the LLM."""
    import db

    return db.get_ai_summary(user_id, ticker.upper())


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
            language=ui_language(request),
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
            head = f"- {ticker}: {p['quantity']} sh @ ${p['purchase_price']} on {p['purchase_date']}"
            reasons = [r for r in p.get("reasons") or [] if r.get("reason_snapshot")]
            if not reasons:
                lines.append(f"{head}, no reason attached.")
                continue
            lines.append(f"{head}, bought for {len(reasons)} reason(s):")
            for r in reasons:
                snapshot = r["reason_snapshot"]
                # Re-evaluate from the frozen rule captured at purchase time,
                # not a live reason_key lookup (Code Audit Session 3, item 2) --
                # same reasoning as portfolio.py's fix.
                if "metric" in snapshot:
                    current = evaluate_frozen_reason(ticker, snapshot)
                else:
                    current = check_reason_status(ticker, r["reason_key"])
                current_status = current.get("status", "unknown") if "error" not in current else "unknown (could not re-check)"
                # Whether the rule holds comes from the CURRENT status alone; a change since
                # purchase is reported separately (Weakened -> Supported is an improvement,
                # not "no longer holds").
                if current_status == "Supported":
                    verdict = "the rule currently holds"
                elif current_status in ("Weakened", "Broken"):
                    verdict = "the rule does NOT currently hold"
                else:
                    verdict = "the rule cannot currently be evaluated"
                changed = "" if current_status == snapshot["status_at_purchase"] else ", status changed since purchase"
                lines.append(
                    f"    * \"{snapshot['description']}\" (was {snapshot['status_at_purchase']} at purchase, "
                    f"currently {current_status} -- {verdict}{changed})."
                )
    return "\n".join(lines)


_HORIZON_LABELS = {"<1y": "under 1 year", "1-5y": "1-5 years", ">5y": "over 5 years"}


def _build_investor_profile_context(user_id: int) -> str:
    """Plain-text summary of the user's own investor profile (budget,
    target growth, horizon, risk tolerance, goals, notes) for the
    portfolio-wide chat prompt -- empty string if they've never filled it
    in, so answer_portfolio_question's system prompt can tell the two
    cases apart and only unlock new-ticker suggestions once a profile
    exists."""
    import db

    profile = db.get_investor_profile_settings(user_id)
    if not profile:
        return ""

    lines = []
    if profile.get("budget_usd") is not None:
        lines.append(f"- Investable budget: ${profile['budget_usd']:,.2f}")
    if profile.get("target_growth_pct") is not None:
        lines.append(f"- Target annual growth: {profile['target_growth_pct']}%")
    if profile.get("investment_horizon"):
        lines.append(f"- Investment horizon: {_HORIZON_LABELS.get(profile['investment_horizon'], profile['investment_horizon'])}")
    if profile.get("risk_tolerance"):
        lines.append(f"- Risk tolerance: {profile['risk_tolerance']}")
    if profile.get("goals"):
        lines.append(f"- Goals: {profile['goals']}")
    if profile.get("notes"):
        lines.append(f"- Additional notes: {profile['notes']}")
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
        profile_context = _build_investor_profile_context(user_id)
        return answer_portfolio_question(
            context, body.question, history=[h.model_dump() for h in body.history],
            investor_profile_context=profile_context, language=ui_language(request),
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
