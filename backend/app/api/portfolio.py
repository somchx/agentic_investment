from fastapi import APIRouter, Depends

import db
from app.api.reports import get_company_report
from app.security import current_user_id
from tools import check_reason_status

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary")
def portfolio_summary(user_id: int = Depends(current_user_id)):
    """Aggregates the free, already-built per-company report across every
    ticker this user has a purchase record for. For each held ticker, also
    reports whether every purchase's reason is still holding (the point of
    the feature): compares each purchase's frozen status_at_purchase
    against the reason's CURRENT status."""
    held = db.list_held_tickers(user_id)
    companies = []
    for ticker in held:
        try:
            report = get_company_report(ticker, user_id)
        except Exception as e:  # noqa: BLE001
            companies.append({"ticker": ticker, "error": str(e)})
            continue

        positions = db.list_purchases(user_id, ticker=ticker)
        for p in positions:
            if not p["reason_key"] or not p["reason_snapshot"]:
                p["still_true"] = None
                continue
            current = check_reason_status(ticker, p["reason_key"])
            p["current_status"] = current.get("status")
            p["current_computed_value"] = current.get("computed_value")
            p["current_as_of"] = current.get("as_of")
            p["still_true"] = (
                current.get("status") == p["reason_snapshot"]["status_at_purchase"]
                if "error" not in current else None
            )

        companies.append({
            "ticker": ticker, "company_name": report["company_name"], "positions": positions,
        })
    return companies
