"""Continuous Monitoring -- the free, deterministic background pass that
periodically re-checks every held position and surfaces a notification
when a reason's status changed since the last pass (the "anomaly" this
detects: Supported -> Weakened, Weakened -> Broken, Broken -> Supported,
etc.). Never calls the LLM -- this is the same check_reason_status()
already used everywhere else in the app, just run on a schedule instead of
on page load. Flagging something is the cue for the user to open the
(paid, on-demand) Investigation Agent themselves, never an automatic
trigger for it.
"""

from tools import check_reason_status, evaluate_frozen_reason


def run_continuous_monitoring(user_id: int | None = None) -> list[dict]:
    """Re-check every reason attached to any purchase (across all
    users, unless `user_id` narrows it to one -- used by the manual
    "check now" endpoint so a user can re-check just their own holdings on
    demand without waiting for the scheduled pass). Returns the list of
    notifications created this pass (empty list is the common case -- most
    reasons don't change most of the time).

    Re-evaluates from each purchase's own frozen rule snapshot
    (evaluate_frozen_reason), not a live reason_key lookup -- otherwise
    editing or deleting the reason after purchase would silently change
    what monitoring is watching for (Code Audit Session 3, item 2).
    """
    import db

    reasons = db.list_all_purchase_reasons()
    if user_id is not None:
        reasons = [r for r in reasons if r["user_id"] == user_id]

    created = []
    # One row per reason attached to a purchase -- a purchase with several
    # reasons is watched (and notifies) per reason.
    for r in reasons:
        snapshot = r.get("reason_snapshot_json")
        if snapshot and "metric" in snapshot:
            result = evaluate_frozen_reason(r["ticker"], snapshot)
        else:
            # Legacy purchase with no frozen rule captured -- best available
            # fallback, same caveat as portfolio.py's.
            result = check_reason_status(r["ticker"], r["reason_key"])
        if "error" in result:
            continue  # data temporarily unavailable -- try again next pass, don't alarm on it
        current_status = result["status"]
        previous_status = r["last_notified_status"]
        current_as_of = result.get("as_of")
        previous_as_of = r.get("last_checked_as_of")

        # Only a status change notifies -- in practice that happens when a new
        # filing moves the number across the threshold.
        if previous_status is not None and previous_status != current_status:
            message = f"{r['ticker']}: \"{result['reason']}\" changed from {previous_status} to {current_status}."
            details = {
                "kind": "STATUS_CHANGED",
                "reason_description": result["reason"],
                "computed_value": result.get("computed_value"),
                "previous_value": r.get("last_checked_value"),
                "comparison": (snapshot or {}).get("comparison"),
                "threshold": (snapshot or {}).get("threshold"),
                "as_of": current_as_of,
                "previous_as_of": previous_as_of,
            }
            notification_id = db.create_notification(
                user_id=r["user_id"], ticker=r["ticker"], reason_key=r["reason_key"],
                message=message, previous_status=previous_status, current_status=current_status,
                **details,
            )
            created.append({
                "id": notification_id, "ticker": r["ticker"], "message": message,
                "previous_status": previous_status, "current_status": current_status, **details,
            })

        if (previous_status, previous_as_of, r.get("last_checked_value")) != (
            current_status, current_as_of, result.get("computed_value")
        ):
            db.update_last_notified_status(r["id"], current_status, current_as_of, result.get("computed_value"))

    return created
