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

from tools import check_reason_status


def run_continuous_monitoring(user_id: int | None = None) -> list[dict]:
    """Re-check every purchase that has a reason_key attached (across all
    users, unless `user_id` narrows it to one -- used by the manual
    "check now" endpoint so a user can re-check just their own holdings on
    demand without waiting for the scheduled pass). Returns the list of
    notifications created this pass (empty list is the common case -- most
    reasons don't change most of the time).
    """
    import db

    purchases = db.list_all_purchases_with_reason()
    if user_id is not None:
        purchases = [p for p in purchases if p["user_id"] == user_id]

    created = []
    for p in purchases:
        result = check_reason_status(p["ticker"], p["reason_key"])
        if "error" in result:
            continue  # data temporarily unavailable -- try again next pass, don't alarm on it
        current_status = result["status"]
        previous_status = p["last_notified_status"]

        if previous_status is not None and previous_status != current_status:
            message = (
                f"{p['ticker']}: \"{result['reason']}\" changed from {previous_status} "
                f"to {current_status}."
            )
            notification_id = db.create_notification(
                user_id=p["user_id"], ticker=p["ticker"], reason_key=p["reason_key"],
                message=message, previous_status=previous_status, current_status=current_status,
            )
            created.append({
                "id": notification_id, "ticker": p["ticker"], "message": message,
                "previous_status": previous_status, "current_status": current_status,
            })

        if previous_status != current_status:
            db.update_last_notified_status(p["id"], current_status)

    return created
