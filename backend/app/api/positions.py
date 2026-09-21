from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from app.security import current_user_id
from tools import check_reason_status

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
def list_positions(ticker: str | None = None, user_id: int = Depends(current_user_id)):
    return db.list_purchases(user_id, ticker=ticker)


class PositionIn(BaseModel):
    ticker: str
    quantity: float
    purchase_price: float
    purchase_date: str
    reason_key: str | None = None


@router.post("")
def record_position(body: PositionIn, user_id: int = Depends(current_user_id)):
    ticker = body.ticker.upper()
    snapshot = None
    if body.reason_key:
        check = check_reason_status(ticker, body.reason_key)
        if "error" in check:
            raise HTTPException(status_code=400, detail=f"could not evaluate reason_key for snapshot: {check['error']}")
        snapshot = {
            "description": check["reason"],
            "status_at_purchase": check["status"],
            "computed_value_at_purchase": check["computed_value"],
            "explanation_at_purchase": check["explanation"],
        }
    pid = db.record_purchase(
        user_id=user_id, ticker=ticker, quantity=body.quantity, purchase_price=body.purchase_price,
        purchase_date=body.purchase_date, reason_key=body.reason_key, reason_snapshot=snapshot,
    )
    return {"ok": True, "id": pid, "reason_snapshot": snapshot}


@router.delete("/{position_id}")
def delete_position(position_id: int, user_id: int = Depends(current_user_id)):
    db.delete_purchase(position_id, user_id)
    return {"ok": True}
