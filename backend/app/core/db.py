"""PostgreSQL-backed persistence layer -- same function names and return
shapes (plain dicts) as the old src/db.py (SQLite), so tools.py and
portfolio_report.py (copied unmodified into this package) keep working
without changes: they only ever do dict-style access (`row["metric"]`),
never touch the ORM directly.

Deliberately additive, not a replacement of tools.REASON_DEFS -- see that
module's own docstring: the 3 built-in reasons are seeded into the
`reasons` table (user_id NULL, shared by everyone) on first init, but
existing code keeps reading REASON_DEFS unchanged for those.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db.models import (
    ChatConversation,
    ChatMessage,
    InvestigationRun,
    InvestorProfile,
    Notification,
    Purchase,
    Reason,
    User,
)
from app.db.session import Base, SessionLocal, engine


def _row_to_dict(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def init_db() -> None:
    """Create tables if missing, and seed the 3 built-in reasons + built-in
    investor profiles (user_id NULL -- shared) on first run (idempotent).
    """
    Base.metadata.create_all(bind=engine)

    from tools import REASON_DEFS
    from investor_profile import ALL_PROFILES

    with SessionLocal() as session:
        for key, r in REASON_DEFS.items():
            if session.get(Reason, key):
                continue
            session.add(Reason(
                reason_key=key, user_id=None, ticker=None, metric=r.metric,
                comparison=r.comparison, threshold=r.threshold, kind=r.kind,
                denominator_metric=r.denominator_metric, description=r.description,
                instant=bool(r.instant), is_builtin=True,
            ))
        for p in ALL_PROFILES:
            exists = session.execute(
                select(InvestorProfile).where(
                    InvestorProfile.user_id.is_(None), InvestorProfile.name == p.name,
                )
            ).scalar_one_or_none()
            if exists:
                continue
            session.add(InvestorProfile(
                user_id=None, name=p.name, risk_tolerance=p.risk_tolerance,
                investment_horizon=p.investment_horizon, position_size_pct=p.position_size_pct,
                objective=p.objective, is_builtin=True,
            ))
        session.commit()

    _seed_dev_admin_user()


# Fixed dev/test login so a fresh DB (e.g. after `docker compose down -v`)
# always has something to log in with, without a separate manual step.
# Not meant for production use -- a real deployment should remove this or
# gate it behind an env var, but this project's scope is a local prototype.
DEV_ADMIN_EMAIL = "admin@example.com"
DEV_ADMIN_PASSWORD = "12345678"


def _seed_dev_admin_user() -> None:
    with SessionLocal() as session:
        exists = session.execute(
            select(User).where(User.email == DEV_ADMIN_EMAIL)
        ).scalar_one_or_none()
    if exists:
        return
    try:
        create_user(DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD)
    except IntegrityError:
        pass  # created by a concurrent startup (e.g. another worker) -- fine


# ---------------------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------------------

def create_user(email: str, password: str) -> int:
    """Raises ValueError for bad input, or a plain Exception (IntegrityError)
    on duplicate email -- callers should catch that and return a friendly
    "already registered" rather than a 500."""
    if not email or "@" not in email:
        raise ValueError("a valid email is required")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    with SessionLocal() as session:
        user = User(
            email=email.lower().strip(), password_hash=generate_password_hash(password),
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise
        session.refresh(user)
        return user.id


def verify_user(email: str, password: str) -> dict | None:
    """Returns {id, email} on success, None on bad email/password."""
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == email.lower().strip())
        ).scalar_one_or_none()
    if not user or not check_password_hash(user.password_hash, password):
        return None
    return {"id": user.id, "email": user.email}


def get_user_by_id(user_id: int) -> dict | None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
    if not user:
        return None
    return {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()}


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------

def save_reason(reason_key: str, user_id: int, ticker: str | None, metric: str, comparison: str,
                threshold: float, kind: str, description: str, denominator_metric: str = "",
                instant: bool = False) -> None:
    """Persist a user-entered custom reason (upsert by reason_key). `metric`
    (and `denominator_metric`) must be a raw XBRL tag a company has actually
    reported -- sourced from xbrl_extract.list_available_tags(), never free
    text."""
    if comparison not in (">", ">=", "<", "<="):
        raise ValueError(f"comparison must be one of '>','>=','<','<=', got {comparison!r}")
    if kind not in ("yoy_growth", "margin_level"):
        raise ValueError(f"kind must be 'yoy_growth' or 'margin_level', got {kind!r}")
    with SessionLocal() as session:
        existing = session.get(Reason, reason_key)
        if existing:
            existing.ticker = ticker
            existing.metric = metric
            existing.comparison = comparison
            existing.threshold = threshold
            existing.kind = kind
            existing.denominator_metric = denominator_metric
            existing.description = description
            existing.instant = instant
        else:
            session.add(Reason(
                reason_key=reason_key, user_id=user_id, ticker=ticker, metric=metric,
                comparison=comparison, threshold=threshold, kind=kind,
                denominator_metric=denominator_metric, description=description,
                instant=instant, is_builtin=False,
            ))
        session.commit()


def delete_reason(reason_key: str, user_id: int) -> None:
    """Scoped to user_id so one user can't delete another's (or a built-in,
    which has user_id NULL and never matches)."""
    with SessionLocal() as session:
        row = session.get(Reason, reason_key)
        if row and row.user_id == user_id:
            session.delete(row)
            session.commit()


def list_reasons(ticker: str | None = None, user_id: int | None = None) -> list[dict]:
    """Built-in reasons (user_id IS NULL) plus this user's own custom
    reasons -- global ones (ticker IS NULL) and any scoped to `ticker` if
    given. Pass user_id=None to see only built-ins."""
    with SessionLocal() as session:
        stmt = select(Reason)
        if user_id is not None:
            if ticker:
                stmt = stmt.where(
                    (Reason.is_builtin.is_(True))
                    | ((Reason.user_id == user_id) & ((Reason.ticker.is_(None)) | (Reason.ticker == ticker)))
                )
            else:
                stmt = stmt.where((Reason.is_builtin.is_(True)) | (Reason.user_id == user_id))
        else:
            stmt = stmt.where(Reason.is_builtin.is_(True))
        stmt = stmt.order_by(Reason.is_builtin.desc(), Reason.reason_key)
        rows = session.execute(stmt).scalars().all()
        return [_row_to_dict(r) for r in rows]


def get_reason_by_key(reason_key: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(Reason, reason_key)
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
# Investor profiles
# ---------------------------------------------------------------------------

def save_profile(user_id: int, name: str, risk_tolerance: str, investment_horizon: str,
                  position_size_pct: float, objective: str) -> int:
    if risk_tolerance not in ("low", "medium", "high"):
        raise ValueError(f"risk_tolerance must be low/medium/high, got {risk_tolerance!r}")
    if investment_horizon not in ("<1y", "1-5y", ">5y"):
        raise ValueError(f"investment_horizon must be <1y/1-5y/>5y, got {investment_horizon!r}")
    if objective not in ("growth", "income", "preservation"):
        raise ValueError(f"objective must be growth/income/preservation, got {objective!r}")
    with SessionLocal() as session:
        existing = session.execute(
            select(InvestorProfile).where(InvestorProfile.user_id == user_id, InvestorProfile.name == name)
        ).scalar_one_or_none()
        if existing:
            existing.risk_tolerance = risk_tolerance
            existing.investment_horizon = investment_horizon
            existing.position_size_pct = position_size_pct
            existing.objective = objective
            session.commit()
            return existing.id
        profile = InvestorProfile(
            user_id=user_id, name=name, risk_tolerance=risk_tolerance,
            investment_horizon=investment_horizon, position_size_pct=position_size_pct,
            objective=objective, is_builtin=False,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile.id


def delete_profile(profile_id: int, user_id: int) -> None:
    """Scoped to user_id -- a built-in profile (user_id NULL) never matches
    and can't be deleted through here."""
    with SessionLocal() as session:
        row = session.get(InvestorProfile, profile_id)
        if row and row.user_id == user_id:
            session.delete(row)
            session.commit()


def list_profiles(user_id: int | None = None) -> list[dict]:
    """Built-in profiles (shared) plus this user's own."""
    with SessionLocal() as session:
        stmt = select(InvestorProfile)
        if user_id is not None:
            stmt = stmt.where((InvestorProfile.is_builtin.is_(True)) | (InvestorProfile.user_id == user_id))
        else:
            stmt = stmt.where(InvestorProfile.is_builtin.is_(True))
        stmt = stmt.order_by(InvestorProfile.is_builtin.desc(), InvestorProfile.name)
        rows = session.execute(stmt).scalars().all()
        return [_row_to_dict(r) for r in rows]


def get_profile_by_name(name: str, user_id: int | None = None):
    """Returns an investor_profile.InvestorProfile, or None if not found."""
    from investor_profile import InvestorProfile as InvestorProfileDomain
    with SessionLocal() as session:
        row = session.execute(
            select(InvestorProfile).where(
                InvestorProfile.name == name,
                (InvestorProfile.is_builtin.is_(True)) | (InvestorProfile.user_id == user_id),
            )
        ).scalar_one_or_none()
    if not row:
        return None
    return InvestorProfileDomain(
        name=row.name, risk_tolerance=row.risk_tolerance,
        investment_horizon=row.investment_horizon,
        position_size_pct=row.position_size_pct, objective=row.objective,
    )


# ---------------------------------------------------------------------------
# Investigation runs
# ---------------------------------------------------------------------------

def save_run(ticker: str, reason: dict, trace: list[str], usage: dict,
             escalated: bool = False, escalation_reason: str | None = None,
             profile_name: str | None = None) -> int:
    with SessionLocal() as session:
        run = InvestigationRun(
            ticker=ticker, reason_key=reason.get("reason_key", ""), status=reason.get("status"),
            confidence=reason.get("confidence"),
            human_review_recommended=bool(reason.get("human_review_recommended", False)),
            rationale=reason.get("rationale"), escalated=escalated, escalation_reason=escalation_reason,
            profile_name=profile_name, rule_based_tier=reason.get("rule_based_tier"),
            llm_tier=reason.get("llm_tier"),
            integrity_ok=None if "integrity_ok" not in reason else bool(reason["integrity_ok"]),
            trace_json=trace, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


def save_investigation_result(result: dict, profile_name: str | None = None) -> list[int]:
    ticker = result["ticker"]
    if result.get("escalated"):
        return [save_run(
            ticker, {}, result["trace"], result["usage"],
            escalated=True, escalation_reason=result.get("escalation_reason"),
            profile_name=profile_name,
        )]
    return [
        save_run(ticker, r, result["trace"], result["usage"], profile_name=profile_name)
        for r in result["reasons"]
    ]


def list_runs(ticker: str | None = None, limit: int = 50) -> list[dict]:
    with SessionLocal() as session:
        stmt = select(InvestigationRun)
        if ticker:
            stmt = stmt.where(InvestigationRun.ticker == ticker)
        stmt = stmt.order_by(InvestigationRun.created_at.desc()).limit(limit)
        rows = session.execute(stmt).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


# ---------------------------------------------------------------------------
# Purchases (real position records, per user)
# ---------------------------------------------------------------------------

def record_purchase(user_id: int, ticker: str, quantity: float, purchase_price: float,
                     purchase_date: str, reason_key: str | None = None,
                     reason_snapshot: dict | None = None) -> int:
    """`reason_snapshot` freezes what the reason said *at the moment of
    purchase* so that later edits to the reason -- or its current live
    status simply changing over time -- can never rewrite history."""
    with SessionLocal() as session:
        purchase = Purchase(
            user_id=user_id, ticker=ticker.upper(), quantity=quantity, purchase_price=purchase_price,
            purchase_date=purchase_date, reason_key=reason_key, reason_snapshot_json=reason_snapshot,
        )
        session.add(purchase)
        session.commit()
        session.refresh(purchase)
        return purchase.id


def delete_purchase(purchase_id: int, user_id: int) -> None:
    with SessionLocal() as session:
        row = session.get(Purchase, purchase_id)
        if row and row.user_id == user_id:
            session.delete(row)
            session.commit()


def list_purchases(user_id: int, ticker: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        stmt = select(Purchase).where(Purchase.user_id == user_id)
        if ticker:
            stmt = stmt.where(Purchase.ticker == ticker.upper())
        stmt = stmt.order_by(Purchase.purchase_date.desc())
        rows = session.execute(stmt).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["reason_snapshot"] = d.pop("reason_snapshot_json")
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


def list_held_tickers(user_id: int) -> list[str]:
    """Distinct tickers this user has any purchase record for."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Purchase.ticker).where(Purchase.user_id == user_id).distinct().order_by(Purchase.ticker)
        ).scalars().all()
        return list(rows)


def list_all_purchases_with_reason() -> list[dict]:
    """Every purchase (any user) that has a reason_key attached -- what
    continuous monitoring (app/core/monitor.py) iterates over. Free,
    read-only; monitoring never needs anything else about a user."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Purchase).where(Purchase.reason_key.is_not(None))
        ).scalars().all()
        return [_row_to_dict(r) for r in rows]


def update_last_notified_status(purchase_id: int, status: str) -> None:
    with SessionLocal() as session:
        row = session.get(Purchase, purchase_id)
        if row:
            row.last_notified_status = status
            session.commit()


# ---------------------------------------------------------------------------
# Notifications (continuous monitoring alerts -- free, mechanical, never
# from the paid Investigation Agent)
# ---------------------------------------------------------------------------

def create_notification(
    user_id: int, ticker: str, reason_key: str | None, message: str,
    previous_status: str | None, current_status: str | None,
) -> int:
    with SessionLocal() as session:
        n = Notification(
            user_id=user_id, ticker=ticker, reason_key=reason_key, message=message,
            previous_status=previous_status, current_status=current_status,
        )
        session.add(n)
        session.commit()
        session.refresh(n)
        return n.id


def list_notifications(user_id: int, limit: int = 50) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Notification).where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc()).limit(limit)
        ).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


def count_unread_notifications(user_id: int) -> int:
    with SessionLocal() as session:
        return session.execute(
            select(func.count()).select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        ).scalar_one()


def mark_notification_read(notification_id: int, user_id: int) -> None:
    with SessionLocal() as session:
        row = session.get(Notification, notification_id)
        if row and row.user_id == user_id:
            row.is_read = True
            session.commit()


def mark_all_notifications_read(user_id: int) -> None:
    with SessionLocal() as session:
        rows = session.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False))
        ).scalars().all()
        for row in rows:
            row.is_read = True
        session.commit()


# ---------------------------------------------------------------------------
# Agent chat conversations -- a permanent record, same reasoning as
# InvestigationRun above: every message here is a paid LLM call.
# ---------------------------------------------------------------------------

def _conversation_title_from(question: str) -> str:
    q = " ".join(question.split())  # collapse newlines/whitespace
    return q if len(q) <= 60 else q[:57] + "..."


def create_conversation(user_id: int, first_question: str) -> int:
    with SessionLocal() as session:
        c = ChatConversation(user_id=user_id, title=_conversation_title_from(first_question))
        session.add(c)
        session.commit()
        session.refresh(c)
        return c.id


def append_message(
    conversation_id: int, role: str, content: str,
    cost_usd: float | None = None, tool_calls: list | None = None,
) -> int:
    with SessionLocal() as session:
        m = ChatMessage(
            conversation_id=conversation_id, role=role, content=content,
            cost_usd=cost_usd, tool_calls_json=tool_calls,
        )
        session.add(m)
        conversation = session.get(ChatConversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(m)
        return m.id


def list_conversations(user_id: int, limit: int = 100) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ChatConversation).where(ChatConversation.user_id == user_id)
            .order_by(ChatConversation.updated_at.desc()).limit(limit)
        ).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["created_at"] = d["created_at"].isoformat()
            d["updated_at"] = d["updated_at"].isoformat()
            out.append(d)
        return out


def get_conversation(conversation_id: int, user_id: int) -> dict | None:
    """Returns the conversation with its messages (oldest first), or None
    if it doesn't exist or belongs to a different user."""
    with SessionLocal() as session:
        c = session.get(ChatConversation, conversation_id)
        if not c or c.user_id != user_id:
            return None
        d = _row_to_dict(c)
        d["created_at"] = d["created_at"].isoformat()
        d["updated_at"] = d["updated_at"].isoformat()
        d["messages"] = []
        for m in c.messages:
            md = _row_to_dict(m)
            md["created_at"] = md["created_at"].isoformat()
            d["messages"].append(md)
        return d


def delete_conversation(conversation_id: int, user_id: int) -> None:
    with SessionLocal() as session:
        c = session.get(ChatConversation, conversation_id)
        if c and c.user_id == user_id:
            session.delete(c)
            session.commit()


if __name__ == "__main__":
    init_db()
    print("Initialized PostgreSQL schema")
    print(f"  {len(list_reasons())} built-in reason(s) seeded")
    print(f"  {len(list_profiles())} built-in investor profile(s) seeded")
