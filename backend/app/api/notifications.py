from fastapi import APIRouter, Depends

import db
from app.security import current_user_id
from monitor import run_continuous_monitoring

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user_id: int = Depends(current_user_id)):
    return db.list_notifications(user_id)


@router.get("/unread-count")
def unread_count(user_id: int = Depends(current_user_id)):
    return {"count": db.count_unread_notifications(user_id)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user_id: int = Depends(current_user_id)):
    db.mark_notification_read(notification_id, user_id)
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user_id: int = Depends(current_user_id)):
    db.mark_all_notifications_read(user_id)
    return {"ok": True}


@router.post("/check-now")
def check_now(user_id: int = Depends(current_user_id)):
    """Manually run continuous monitoring for just this user's own
    holdings, on demand -- free (same check_reason_status the rest of the
    app already uses), for a user who doesn't want to wait for the hourly
    scheduled pass. Returns any notifications created."""
    created = run_continuous_monitoring(user_id=user_id)
    return {"created": created}
