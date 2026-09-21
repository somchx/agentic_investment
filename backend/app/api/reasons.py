from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from app.security import current_user_id
from sec_client import get_company_facts
from tools import check_reason_status
from xbrl_extract import list_available_tags

router = APIRouter(prefix="/api", tags=["reasons"])


@router.get("/xbrl-tags/{ticker}")
def api_xbrl_tags(ticker: str, user_id: int = Depends(current_user_id)):
    """Every XBRL tag this specific company has actually reported -- the
    picker for defining a custom reason draws from this, never free text,
    so a custom reason can never reference a tag that doesn't exist for
    the company."""
    try:
        facts_json = get_company_facts(ticker.upper())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
    return list_available_tags(facts_json)


@router.get("/reasons")
def api_list_all_reasons(ticker: str | None = None, user_id: int = Depends(current_user_id)):
    """No ticker: every reason (built-in + this user's own custom ones)
    across any company, for pickers that aren't scoped to one company (the
    Screener's condition dropdown, Record Purchase's reason dropdown).
    With ?ticker=: this user's own custom (non-built-in) reasons for that
    ticker, for a management list in the UI."""
    if ticker:
        rows = [r for r in db.list_reasons(ticker=ticker.upper(), user_id=user_id) if not r["is_builtin"]]
        return rows
    return db.list_reasons(user_id=user_id)


class ReasonIn(BaseModel):
    ticker: str
    metric: str
    comparison: str
    threshold: float
    kind: str
    description: str
    denominator_metric: str = ""
    instant: bool = False
    reason_key: str


@router.post("/reasons")
def api_create_reason(body: ReasonIn, user_id: int = Depends(current_user_id)):
    if body.reason_key in ("revenue_growth", "operating_margin", "debt_growth"):
        raise HTTPException(status_code=400, detail="reason_key collides with a built-in reason")
    try:
        db.save_reason(
            reason_key=body.reason_key, user_id=user_id, ticker=body.ticker.upper(),
            metric=body.metric, comparison=body.comparison, threshold=body.threshold,
            kind=body.kind, description=body.description,
            denominator_metric=body.denominator_metric, instant=body.instant,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Confirm it actually computes something before telling the caller it
    # succeeded -- a tag picked from list_available_tags should always work,
    # but a margin reason's denominator could still turn out empty for this
    # specific ticker even though the tag exists company-wide in general.
    check = check_reason_status(body.ticker.upper(), body.reason_key)
    return {"ok": True, "preview": check}


@router.delete("/reasons/{reason_key}")
def api_delete_reason(reason_key: str, user_id: int = Depends(current_user_id)):
    db.delete_reason(reason_key, user_id)
    return {"ok": True}
