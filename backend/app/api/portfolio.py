from fastapi import APIRouter, Depends

import db
from app.api.reports import get_company_report
from app.security import current_user_id
from market_data import MarketDataUnavailableError, get_quote
from tools import check_reason_status, evaluate_frozen_reason

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _evaluate_purchase_reason(ticker: str, r: dict) -> None:
    """Fill one purchase reason's current status/value in place."""
    snapshot = r.get("reason_snapshot")
    if not snapshot:
        r["still_true"] = None
        return
    if "metric" in snapshot:
        # Frozen rule captured at purchase time (Session 3 fix) --
        # re-evaluate from that, independent of the live reason.
        current = evaluate_frozen_reason(ticker, snapshot)
    else:
        # Legacy purchase recorded before the frozen-rule fix: no
        # rule definition was ever captured, only the description
        # and computed status. Falling back to a live reason_key
        # lookup is the best available option for these old rows,
        # but it carries the exact risk this fix exists to close --
        # if the reason has since been edited or deleted, this will
        # silently compare against a different (or missing) rule.
        current = check_reason_status(ticker, r["reason_key"])
        r["frozen_rule_missing"] = True
    r["current_status"] = current.get("status")
    r["current_computed_value"] = current.get("computed_value")
    r["current_as_of"] = current.get("as_of")
    r["still_true"] = (
        current.get("status") == snapshot["status_at_purchase"]
        if "error" not in current else None
    )


@router.get("/summary")
def portfolio_summary(user_id: int = Depends(current_user_id)):
    """Aggregates the free, already-built per-company report across every
    ticker this user has a purchase record for. For each held ticker, also
    reports whether every purchase's reason is still holding (the point of
    the feature): compares each purchase's frozen status_at_purchase
    against the reason's CURRENT status -- evaluated from the purchase's
    own frozen rule definition (evaluate_frozen_reason), NOT by looking
    in-key reason_key up again. Editing or deleting the live `reasons` row
    for that key must never change what a past purchase is tracked
    against (Code Audit Session 3, item 2).

    A purchase can carry several reasons (`positions[].reasons`), each
    evaluated on its own; the first is also copied to the position's
    top-level fields for older readers."""
    held = db.list_held_tickers(user_id)
    companies = []
    for ticker in held:
        try:
            report = get_company_report(ticker, user_id)
        except Exception as e:  # noqa: BLE001
            companies.append({"ticker": ticker, "error": str(e)})
            continue

        # Live price, for display and unrealized P&L only -- never fed
        # into any reason's Supported/Weakened/Broken status (that must
        # stay point-in-time SEC data; see market_data.py's docstring).
        # Best-effort: a quote failure degrades to `current_price: None`
        # rather than failing the whole portfolio summary.
        try:
            current_price = get_quote(ticker)["price"]
        except MarketDataUnavailableError:
            current_price = None

        positions = db.list_purchases(user_id, ticker=ticker)
        for p in positions:
            if current_price is not None:
                p["current_price"] = current_price
                p["unrealized_pnl"] = (current_price - p["purchase_price"]) * p["quantity"]
                p["unrealized_pnl_pct"] = (
                    (current_price - p["purchase_price"]) / p["purchase_price"] * 100
                    if p["purchase_price"] else None
                )
            else:
                p["current_price"] = None
                p["unrealized_pnl"] = None
                p["unrealized_pnl_pct"] = None

            for r in p["reasons"]:
                _evaluate_purchase_reason(ticker, r)
            first = p["reasons"][0] if p["reasons"] else None
            if first is None:
                p["still_true"] = None
                continue
            for field in ("current_status", "current_computed_value", "current_as_of", "still_true", "frozen_rule_missing"):
                if field in first:
                    p[field] = first[field]

        companies.append({
            "ticker": ticker, "company_name": report["company_name"], "positions": positions,
        })
    return companies
