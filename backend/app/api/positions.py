import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import db
from agent import run_bull_bear_debate, run_thesis_attack
from app.api.language import ui_language
from app.rate_limit import limiter
from app.security import current_user_id
from sec_client import SecDataUnavailableError, UnsupportedTickerError
from revalidation import build_reason_revalidation
from tools import evaluate_frozen_reason

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
def list_positions(ticker: str | None = None, user_id: int = Depends(current_user_id)):
    return db.list_purchases(user_id, ticker=ticker)


class PositionIn(BaseModel):
    ticker: str
    quantity: float
    purchase_price: float
    purchase_date: str
    # Every reason this purchase was made for, in the order picked.
    # `reason_key` is the older single-reason form, still accepted.
    reason_keys: list[str] = []
    reason_key: str | None = None
    # Decision Journal: the investor's own free-text WHY, frozen alongside
    # the WHAT in reason_snapshot -- optional, same as reason_key.
    thesis: str | None = None


def _freeze_reason(ticker: str, reason_key: str, purchase_date: str, user_id: int) -> dict:
    """Evaluate one reason as of the purchase date and freeze its whole rule
    plus that status -- the snapshot each PurchaseReason row stores."""
    # Ownership check (Code Audit Session 3, item 3) -- reject before
    # ever evaluating it, and reply the same way as "doesn't exist" so
    # this can't be used to probe which reason_keys other users have.
    reason_def = db.get_reason_if_accessible(reason_key, user_id)
    if reason_def is None:
        raise HTTPException(status_code=400, detail=f"unknown reason_key '{reason_key}'")

    # as_of=purchase_date, not "today" -- the whole point of a purchase
    # snapshot is what the reason's status was AT THE TIME OF PURCHASE,
    # per this project's point-in-time discipline (see xbrl_extract.
    # facts_as_of). Omitting as_of here silently broke that for any
    # backdated purchase entry (Code Audit Session 2, item 4).
    check = evaluate_frozen_reason(ticker, reason_def, as_of=purchase_date)
    if "error" in check:
        raise HTTPException(status_code=400, detail=f"could not evaluate reason_key for snapshot: {check['error']}")

    # Freeze the WHOLE rule (metric/comparison/threshold/kind/
    # denominator/instant), not just its computed status -- otherwise
    # editing or deleting the live `reasons` row later silently changes
    # what this purchase is tracked against (Code Audit Session 3, item
    # 2: reproduced by buying under "margin >= 20%", editing the rule to
    # "margin >= 25%", and watching the old code re-grade the purchase
    # against 25%). Portfolio tracking and Continuous Monitoring must
    # re-evaluate from this frozen definition via evaluate_frozen_reason,
    # never by looking reason_key up again.
    snapshot = {
        "description": check["reason"],
        "status_at_purchase": check["status"],
        "computed_value_at_purchase": check["computed_value"],
        "explanation_at_purchase": check["explanation"],
        "metric": reason_def["metric"],
        "comparison": reason_def["comparison"],
        "threshold": reason_def["threshold"],
        "kind": reason_def["kind"],
        "denominator_metric": reason_def["denominator_metric"],
        "instant": reason_def["instant"],
        # Required by evaluate_frozen_reason to pick the right tag
        # lookup -- a built-in reason's `metric` is a curated friendly
        # name (multi-tag migration list), a custom reason's is one
        # exact raw XBRL tag. Omitting this silently broke every
        # frozen snapshot of a built-in reason (see tools.py docstring).
        # The `reasons` table only stores `is_builtin`; "custom" is
        # just its negation (same convention as get_reason_def in
        # tools.py).
        "is_custom": reason_def.get("is_custom", not reason_def["is_builtin"]),
    }
    return snapshot


@router.post("")
def record_position(body: PositionIn, user_id: int = Depends(current_user_id)):
    ticker = body.ticker.upper()
    keys = list(dict.fromkeys([*body.reason_keys, *([body.reason_key] if body.reason_key else [])]))
    # Tracking whether the reasons for buying still hold is the point of the
    # system, so a purchase must carry at least one.
    if not keys:
        raise HTTPException(status_code=400, detail="at least one reason_key is required")
    reasons = [(key, _freeze_reason(ticker, key, body.purchase_date, user_id)) for key in keys]
    pid = db.record_purchase(
        user_id=user_id, ticker=ticker, quantity=body.quantity, purchase_price=body.purchase_price,
        purchase_date=body.purchase_date, reasons=reasons, thesis=body.thesis,
    )
    return {
        "ok": True, "id": pid,
        "reasons": [{"reason_key": k, "reason_snapshot": snap} for k, snap in reasons],
        # First reason, for callers of the older single-reason response.
        "reason_snapshot": reasons[0][1] if reasons else None,
    }


@router.get("/{position_id}/revalidation")
def get_revalidation(position_id: int, user_id: int = Depends(current_user_id)):
    """Thesis Revalidation for every reason of one purchase: point-in-time
    timeline since the purchase (plus a little pre-purchase context), raw
    amounts behind the latest number, and what the next filing must show.
    Free and mechanical -- the same frozen-rule evaluation as everywhere
    else, re-run per filing date; no LLM."""
    purchase = db.get_purchase_if_accessible(position_id, user_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="unknown position")
    reasons = []
    for r in purchase.get("reasons") or []:
        snapshot = r.get("reason_snapshot") or {}
        if "metric" not in snapshot:
            reasons.append({"reason_key": r["reason_key"], "error": "no frozen rule captured for this reason"})
            continue
        try:
            reasons.append(build_reason_revalidation(
                purchase["ticker"], {**snapshot, "reason_key": r["reason_key"]}, purchase["purchase_date"],
            ))
        except SecDataUnavailableError:
            reasons.append({"reason_key": r["reason_key"], "error": "SEC data source unavailable"})
    return {"ticker": purchase["ticker"], "purchase_date": purchase["purchase_date"], "reasons": reasons}


@router.delete("/{position_id}")
def delete_position(position_id: int, user_id: int = Depends(current_user_id)):
    db.delete_purchase(position_id, user_id)
    return {"ok": True}


class ThesisRunIn(BaseModel):
    # Which of the purchase's reasons to challenge; defaults to the first.
    reason_key: str | None = None


def _require_thesis_position(position_id: int, user_id: int, reason_key: str | None = None) -> tuple[dict, dict]:
    """Shared validation for both Decision Journal endpoints below: the
    position must exist, belong to this user, have a stated thesis, and
    have a frozen rule snapshot (not a legacy purchase recorded before
    Code Audit Session 3's frozen-snapshot fix) to attack/debate.

    Returns the purchase and the chosen reason ({reason_key, reason_snapshot}):
    a run challenges one reason at a time, so the agent and its Evidence Gate
    stay exactly the single-reason design they were built and measured as."""
    purchase = db.get_purchase_if_accessible(position_id, user_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="unknown position")
    if not purchase.get("thesis"):
        raise HTTPException(status_code=400, detail="this position has no Decision Journal thesis")
    reasons = purchase.get("reasons") or []
    if reason_key is not None:
        reasons = [r for r in reasons if r["reason_key"] == reason_key]
        if not reasons:
            raise HTTPException(status_code=400, detail=f"reason_key '{reason_key}' is not attached to this position")
    reason = reasons[0] if reasons else None
    snapshot = reason and reason.get("reason_snapshot")
    if not snapshot or "metric" not in snapshot:
        raise HTTPException(
            status_code=400,
            detail="this position has no frozen rule snapshot (legacy purchase, or no reason_key was set)",
        )
    return purchase, reason


@router.get("/{position_id}/thesis-reviews")
def get_thesis_reviews(position_id: int, user_id: int = Depends(current_user_id)):
    purchase = db.get_purchase_if_accessible(position_id, user_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="unknown position")
    return db.list_thesis_reviews(position_id)


@router.post("/{position_id}/attack-thesis")
@limiter.limit("10/minute")
def attack_thesis(
    request: Request, position_id: int, body: ThesisRunIn | None = None, user_id: int = Depends(current_user_id),
):
    """Decision Journal / "Attack the Thesis" -- runs agent.run_thesis_attack
    against this purchase's frozen rule and stated reasoning, through the
    same Evidence Gate discipline as /api/investigate (assess_thesis_
    sufficiency, not the model's own unchecked judgment). Costs real LLM
    API budget -- only ever called when the user explicitly clicks it,
    same confirm-before-send treatment as /api/investigate.
    """
    purchase, reason = _require_thesis_position(position_id, user_id, body.reason_key if body else None)
    try:
        result = run_thesis_attack(
            purchase["ticker"], reason["reason_key"], reason["reason_snapshot"],
            purchase["purchase_date"], purchase["thesis"], language=ui_language(request),
        )
    except UnsupportedTickerError as e:
        raise HTTPException(status_code=400, detail=f"Unsupported ticker: {e}")
    except SecDataUnavailableError as e:
        logger.error("SEC data source unavailable attacking thesis for position %s: %s", position_id, e)
        raise HTTPException(
            status_code=503,
            detail="Data source unavailable: SEC EDGAR could not be reached. Please try again later.",
        )
    except Exception as e:  # noqa: BLE001 -- genuinely unexpected; full detail stays server-side
        logger.error("Unexpected failure attacking thesis for position %s: %s", position_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error during thesis review.")

    db.save_thesis_review(position_id, result)
    return result


@router.get("/{position_id}/thesis-debates")
def get_thesis_debates(position_id: int, user_id: int = Depends(current_user_id)):
    purchase = db.get_purchase_if_accessible(position_id, user_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="unknown position")
    return db.list_thesis_debates(position_id)


@router.post("/{position_id}/debate-thesis")
@limiter.limit("5/minute")
def debate_thesis(
    request: Request, position_id: int, body: ThesisRunIn | None = None, user_id: int = Depends(current_user_id),
):
    """Mr. Bull / Mr. Bear Cross-Debate -- runs agent.run_bull_bear_debate:
    two evidence-grounded cases (for and against the thesis) plus one
    rebuttal each. More expensive than /attack-thesis (roughly 2x the tool
    calls plus two rebuttal calls), hence the tighter rate limit; same
    cost-confirm-before-send treatment on the frontend.
    """
    purchase, reason = _require_thesis_position(position_id, user_id, body.reason_key if body else None)
    try:
        result = run_bull_bear_debate(
            purchase["ticker"], reason["reason_key"], reason["reason_snapshot"],
            purchase["purchase_date"], purchase["thesis"], language=ui_language(request),
        )
    except UnsupportedTickerError as e:
        raise HTTPException(status_code=400, detail=f"Unsupported ticker: {e}")
    except SecDataUnavailableError as e:
        logger.error("SEC data source unavailable debating thesis for position %s: %s", position_id, e)
        raise HTTPException(
            status_code=503,
            detail="Data source unavailable: SEC EDGAR could not be reached. Please try again later.",
        )
    except Exception as e:  # noqa: BLE001 -- genuinely unexpected; full detail stays server-side
        logger.error("Unexpected failure debating thesis for position %s: %s", position_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error during thesis debate.")

    db.save_thesis_debate(position_id, result)
    return result
