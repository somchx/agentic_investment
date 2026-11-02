"""Insert or remove MOCK notifications so the notification UI can be seen
without waiting for a real filing to flip a status. Dev-only: every row is
tagged "[MOCK]" in `message` and removed by `--remove`.

    docker compose exec backend python scripts/mock_notifications.py admin@example.com
    docker compose exec backend python scripts/mock_notifications.py admin@example.com --remove
"""

import sys
from datetime import datetime, timedelta, timezone

sys.path[:0] = ["app/core", "."]

from app.db.models import Notification, User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

MOCK_TAG = "[MOCK]"

# Illustrative values only -- not real company results. Use tickers the
# target account actually holds, so clicking a notification lands on a holding.
MOCKS = [
    {  # Supported -> Weakened: the headline case
        "ticker": "AMZN", "reason_key": "operating_margin",
        "reason_description": "Operating margin must stay at or above 20%",
        "previous_status": "Supported", "current_status": "Weakened",
        "previous_value": 0.221, "computed_value": 0.137,
        "comparison": ">=", "threshold": 0.20,
        "previous_as_of": "2026-04-30", "as_of": "2026-07-31",
        "hours_ago": 1, "is_read": False,
    },
    {  # Supported -> Broken: a negative value crossing a "<" rule
        "ticker": "NVDA", "reason_key": "debt_growth",
        "reason_description": "Long-term debt must not grow more than 15% YoY",
        "previous_status": "Supported", "current_status": "Broken",
        "previous_value": -0.04, "computed_value": 0.312,
        "comparison": "<", "threshold": 0.15,
        "previous_as_of": "2026-05-28", "as_of": "2026-08-27",
        "hours_ago": 5, "is_read": False,
    },
    {  # Weakened -> Broken
        "ticker": "JNJ", "reason_key": "revenue_growth",
        "reason_description": "Revenue growth must exceed 10% YoY",
        "previous_status": "Weakened", "current_status": "Broken",
        "previous_value": 0.081, "computed_value": 0.032,
        "comparison": ">", "threshold": 0.10,
        "previous_as_of": "2026-04-29", "as_of": "2026-07-29",
        "hours_ago": 30, "is_read": False,
    },
    {  # Broken -> Supported: recovery
        "ticker": "AAPL", "reason_key": "revenue_growth",
        "reason_description": "Revenue growth must exceed 10% YoY",
        "previous_status": "Broken", "current_status": "Supported",
        "previous_value": 0.021, "computed_value": 0.164,
        "comparison": ">", "threshold": 0.10,
        "previous_as_of": "2026-05-01", "as_of": "2026-07-31",
        "hours_ago": 72, "is_read": True,
    },
]


def find_user(session, email: str) -> User:
    user = session.query(User).filter_by(email=email).first()
    if user is None:
        sys.exit(f"no user with email {email}")
    return user


def add(email: str) -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        user = find_user(session, email)
        for m in MOCKS:
            session.add(Notification(
                user_id=user.id, ticker=m["ticker"], reason_key=m["reason_key"],
                message=f"{MOCK_TAG} {m['ticker']}: \"{m['reason_description']}\" changed from "
                        f"{m['previous_status']} to {m['current_status']}.",
                previous_status=m["previous_status"], current_status=m["current_status"],
                kind="STATUS_CHANGED", reason_description=m["reason_description"],
                computed_value=m["computed_value"], previous_value=m["previous_value"],
                comparison=m["comparison"], threshold=m["threshold"],
                as_of=m["as_of"], previous_as_of=m["previous_as_of"],
                is_read=m["is_read"], created_at=now - timedelta(hours=m["hours_ago"]),
            ))
        # One pre-detail notification, to show how older rows still render.
        session.add(Notification(
            user_id=user.id, ticker="NVDA", reason_key="revenue_growth",
            message=f"{MOCK_TAG} NVDA: \"Revenue growth must exceed 10% YoY\" changed from Supported to Weakened.",
            previous_status="Supported", current_status="Weakened", is_read=True,
            created_at=now - timedelta(days=10),
        ))
        session.commit()
    print(f"added {len(MOCKS) + 1} mock notifications for {email}")


def remove(email: str) -> None:
    with SessionLocal() as session:
        user = find_user(session, email)
        n = (
            session.query(Notification)
            .filter(Notification.user_id == user.id, Notification.message.startswith(MOCK_TAG))
            .delete(synchronize_session=False)
        )
        session.commit()
    print(f"removed {n} mock notifications for {email}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    (remove if "--remove" in sys.argv else add)(sys.argv[1])
