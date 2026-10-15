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

import json
import os
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy.exc import ProgrammingError

from app.db.models import (
    AiSummary,
    ChatConversation,
    ChatMessage,
    InvestigationRun,
    HiddenReason,
    InvestorProfile,
    InvestorProfileSettings,
    Notification,
    Purchase,
    PurchaseReason,
    Reason,
    ThesisDebate,
    ThesisReview,
    User,
    XbrlTagTranslation,
)
from app.db.session import Base, SessionLocal, engine


def _row_to_dict(obj) -> dict:
    result = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    if isinstance(obj, Reason):
        # Reserved keys identify personal versions of curated built-in rules.
        source = next((key for key in ("revenue_growth", "operating_margin", "debt_growth")
                       if obj.reason_key == f"personal_builtin_{obj.user_id}_{key}"), None)
        result["source_reason_key"] = source
        result["is_custom"] = not obj.is_builtin and source is None
    return result


def _assert_schema_migrated() -> None:
    """Fail loudly and clearly if Alembic migrations haven't been run,
    instead of silently calling Base.metadata.create_all() to paper over
    it (Code Audit Session 5, item 2).

    create_all() was removed here on purpose: verified against a genuinely
    fresh Postgres container that `alembic upgrade head` alone already
    creates every table Base.metadata declares (compared table-for-table,
    zero missing/extra) -- so create_all() was pure redundancy in the
    working case. In the *broken* case it was actively harmful: this
    project hit the same bug three times (notifications, chat_*,
    xbrl_tag_translations) where a new table was added to models.py, a
    migration was forgotten or wrong, and create_all() silently created
    the table anyway on every dev/staging startup -- masking the missing
    migration until someone finally deployed against a truly empty DB
    (Code Audit Session 2, item 5). Schema drift belongs to Alembic alone
    now; a missing migration must be a startup failure, not a silent
    auto-create.
    """
    try:
        with engine.connect() as conn:
            conn.execute(select(Reason.reason_key).limit(1))
    except ProgrammingError as e:
        raise RuntimeError(
            "Database schema is missing or out of date (Alembic migrations have not "
            "been run against this database). This app no longer auto-creates tables "
            "-- run `alembic upgrade head` from backend/ before starting the server."
        ) from e


def init_db() -> None:
    """Verify the schema is migrated, and seed the 3 built-in reasons +
    built-in investor profiles (user_id NULL -- shared) on first run
    (idempotent). Does NOT create tables -- see _assert_schema_migrated.
    """
    _assert_schema_migrated()

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

    if os.environ.get("SEED_DEV_ADMIN", "false").lower() == "true":
        _seed_dev_admin_user()


# Fixed dev/test login so a fresh DB (e.g. after `docker compose down -v`)
# always has something to log in with, without a separate manual step.
# Only enabled explicitly with SEED_DEV_ADMIN=true for local development.
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

def create_user(email: str, password: str, full_name: str = "") -> int:
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
            full_name=full_name.strip(),
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
    return {"id": user.id, "email": user.email, "full_name": user.full_name,
            "token_version": user.token_version}


def get_user_by_id(user_id: int) -> dict | None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
    if not user:
        return None
    return {"id": user.id, "email": user.email, "full_name": user.full_name,
            "token_version": user.token_version, "created_at": user.created_at.isoformat()}


def update_user_profile(user_id: int, full_name: str, email: str) -> dict | None:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        user.full_name = full_name.strip()
        user.email = email.lower().strip()
        session.commit()
        return {"id": user.id, "email": user.email, "full_name": user.full_name}


def change_user_password(user_id: int, current_password: str, new_password: str) -> dict | None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
        if not user:
            return None
        if not check_password_hash(user.password_hash, current_password):
            raise ValueError("Current password is incorrect")
        if check_password_hash(user.password_hash, new_password):
            raise ValueError("New password must be different from current password")
        user.password_hash = generate_password_hash(new_password)
        user.token_version += 1
        session.commit()
        return {"id": user.id, "email": user.email, "full_name": user.full_name,
                "token_version": user.token_version}


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
        if existing and existing.user_id != user_id:
            # reason_key is client-generated (ticker + metric + timestamp
            # slug) and this was upserting by that key alone with no
            # ownership check -- a second user submitting a colliding key
            # (or a built-in's key, though api_create_reason blocks those
            # three specifically) could silently overwrite someone else's
            # reason. Confirmed as a real gap in an external code audit.
            raise ValueError(f"reason_key {reason_key!r} already exists and belongs to a different user")
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
    """Remove from this account's lists while preserving historical references."""
    with SessionLocal() as session:
        row = session.get(Reason, reason_key)
        if row is None or (not row.is_builtin and row.user_id != user_id):
            raise ValueError("Reason not found")
        keys = [reason_key]
        source = _row_to_dict(row).get("source_reason_key")
        if source:
            keys.append(source)
        for key in keys:
            if session.get(HiddenReason, (user_id, key)) is None:
                session.add(HiddenReason(user_id=user_id, reason_key=key))
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
        results = [_row_to_dict(r) for r in rows]
        replaced = {r["source_reason_key"] for r in results if r.get("source_reason_key")}
        hidden = set(session.scalars(select(HiddenReason.reason_key).where(HiddenReason.user_id == user_id))) if user_id is not None else set()
        return [r for r in results if r["reason_key"] not in replaced | hidden]


def get_reason_by_key(reason_key: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(Reason, reason_key)
    return _row_to_dict(row) if row else None


def get_reason_if_accessible(reason_key: str, user_id: int) -> dict | None:
    """Same lookup as get_reason_by_key, but returns None (indistinguishable
    from "doesn't exist") unless the reason is a shared built-in or actually
    belongs to `user_id`. Any endpoint that accepts a reason_key directly
    from an authenticated request (record a purchase, run the screener)
    must go through this instead of get_reason_by_key/check_reason_status
    directly -- those evaluate whatever reason_key they're given with no
    ownership check at all, so a user who knows or guesses another user's
    custom reason_key could otherwise attach it to their own purchase or
    screen with it (Code Audit Session 3, item 3)."""
    row = get_reason_by_key(reason_key)
    if row is None:
        return None
    if row["is_builtin"] or row["user_id"] == user_id:
        return row
    return None


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


_HORIZON_VALUES = ("<1y", "1-5y", ">5y")
_RISK_VALUES = ("low", "medium", "high")


def get_investor_profile_settings(user_id: int) -> dict | None:
    """The user's own single investor profile (budget/goals/risk
    tolerance), not the reusable named presets above. None if they've
    never filled it in."""
    with SessionLocal() as session:
        row = session.execute(
            select(InvestorProfileSettings).where(InvestorProfileSettings.user_id == user_id)
        ).scalar_one_or_none()
        return _row_to_dict(row) if row else None


def save_investor_profile_settings(
    user_id: int,
    budget_usd: float | None,
    target_growth_pct: float | None,
    investment_horizon: str | None,
    risk_tolerance: str | None,
    goals: str | None,
    notes: str | None,
) -> dict:
    """Upsert -- one row per user_id (enforced by a unique constraint)."""
    if investment_horizon is not None and investment_horizon not in _HORIZON_VALUES:
        raise ValueError(f"investment_horizon must be one of {_HORIZON_VALUES}, got {investment_horizon!r}")
    if risk_tolerance is not None and risk_tolerance not in _RISK_VALUES:
        raise ValueError(f"risk_tolerance must be one of {_RISK_VALUES}, got {risk_tolerance!r}")
    with SessionLocal() as session:
        row = session.execute(
            select(InvestorProfileSettings).where(InvestorProfileSettings.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            row = InvestorProfileSettings(user_id=user_id)
            session.add(row)
        row.budget_usd = budget_usd
        row.target_growth_pct = target_growth_pct
        row.investment_horizon = investment_horizon
        row.risk_tolerance = risk_tolerance
        row.goals = goals
        row.notes = notes
        session.commit()
        session.refresh(row)
        return _row_to_dict(row)


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
             profile_name: str | None = None, assessor_gaps: list[str] | None = None) -> int:
    with SessionLocal() as session:
        run = InvestigationRun(
            ticker=ticker, reason_key=reason.get("reason_key", ""), status=reason.get("status"),
            confidence=reason.get("confidence"),
            human_review_recommended=bool(reason.get("human_review_recommended", False)),
            rationale=reason.get("rationale"), escalated=escalated, escalation_reason=escalation_reason,
            profile_name=profile_name, rule_based_tier=reason.get("rule_based_tier"),
            llm_tier=reason.get("llm_tier"),
            integrity_ok=None if "integrity_ok" not in reason else bool(reason["integrity_ok"]),
            trace_json=trace, assessor_gaps_json=assessor_gaps or None,
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


def save_investigation_result(result: dict, profile_name: str | None = None) -> list[int]:
    """`result["assessor_gaps"]` (see investigation_state.assess_sufficiency)
    is one list for the whole run, with each problem string prefixed
    "{reason_key}: ..." -- split back out per reason here so each
    InvestigationRun row only carries the gaps that are actually about it,
    rather than every reason getting every gap from the whole run."""
    ticker = result["ticker"]
    all_gaps = result.get("assessor_gaps") or []
    if result.get("escalated"):
        return [save_run(
            ticker, {}, result["trace"], result["usage"],
            escalated=True, escalation_reason=result.get("escalation_reason"),
            profile_name=profile_name, assessor_gaps=all_gaps or None,
        )]
    return [
        save_run(
            ticker, r, result["trace"], result["usage"], profile_name=profile_name,
            assessor_gaps=[g for g in all_gaps if g.startswith(f"{r.get('reason_key')}:")] or None,
        )
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


def save_ai_summary(user_id: int, ticker: str, result: dict, data_as_of: str | None) -> dict:
    """Upsert: one stored AI Summary per (user, ticker), replaced on regenerate."""
    with SessionLocal() as session:
        row = session.execute(
            select(AiSummary).where(AiSummary.user_id == user_id, AiSummary.ticker == ticker)
        ).scalar_one_or_none()
        if row is None:
            row = AiSummary(user_id=user_id, ticker=ticker)
            session.add(row)
        # Round-trip through JSON: tool-call records may carry values JSONB
        # can't take directly (e.g. dates); store their string form instead.
        row.result_json = json.loads(json.dumps(result, default=str))
        row.data_as_of = data_as_of
        row.created_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return _ai_summary_to_dict(row)


def get_ai_summary(user_id: int, ticker: str) -> dict | None:
    with SessionLocal() as session:
        row = session.execute(
            select(AiSummary).where(AiSummary.user_id == user_id, AiSummary.ticker == ticker)
        ).scalar_one_or_none()
        return _ai_summary_to_dict(row) if row else None


def _ai_summary_to_dict(row: AiSummary) -> dict:
    return {**row.result_json, "data_as_of": row.data_as_of, "generated_at": row.created_at.isoformat()}


# ---------------------------------------------------------------------------
# Purchases (real position records, per user)
# ---------------------------------------------------------------------------

def record_purchase(user_id: int, ticker: str, quantity: float, purchase_price: float,
                     purchase_date: str, reasons: list[tuple[str, dict]] | None = None,
                     thesis: str | None = None) -> int:
    """`reason_snapshot` freezes what the reason said *at the moment of
    purchase* so that later edits to the reason -- or its current live
    status simply changing over time -- can never rewrite history.

    `thesis` is the Decision Journal entry -- the investor's own free-text
    WHY, frozen alongside the WHAT in `reason_snapshot`, so a later "Attack
    the Thesis" review (agent.run_thesis_attack) has something of the
    investor's own reasoning to actually attack, not just the rule.

    `reasons`: (reason_key, frozen snapshot) pairs in the order picked. The
    first is mirrored into the legacy single-reason columns.
    """
    reasons = reasons or []
    with SessionLocal() as session:
        first_key, first_snapshot = reasons[0] if reasons else (None, None)
        purchase = Purchase(
            user_id=user_id, ticker=ticker.upper(), quantity=quantity, purchase_price=purchase_price,
            purchase_date=purchase_date, reason_key=first_key, reason_snapshot_json=first_snapshot,
            thesis=thesis,
            reasons=[
                PurchaseReason(position=i, reason_key=key, reason_snapshot_json=snapshot)
                for i, (key, snapshot) in enumerate(reasons)
            ],
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


def get_purchase_if_accessible(purchase_id: int, user_id: int) -> dict | None:
    """Same ownership-check convention as get_reason_if_accessible (Code
    Audit Session 3, item 3) -- returns None indistinguishably for "doesn't
    exist" and "exists but isn't yours" so a purchase id can't be probed."""
    with SessionLocal() as session:
        row = session.get(Purchase, purchase_id)
        if row is None or row.user_id != user_id:
            return None
        return _purchase_to_dict(row)


def _purchase_to_dict(row: Purchase) -> dict:
    d = _row_to_dict(row)
    d["reason_snapshot"] = d.pop("reason_snapshot_json")
    d["created_at"] = d["created_at"].isoformat()
    d["reasons"] = [
        {"id": r.id, "reason_key": r.reason_key, "reason_snapshot": r.reason_snapshot_json}
        for r in row.reasons
    ]
    return d


def list_purchases(user_id: int, ticker: str | None = None) -> list[dict]:
    with SessionLocal() as session:
        stmt = select(Purchase).where(Purchase.user_id == user_id)
        if ticker:
            stmt = stmt.where(Purchase.ticker == ticker.upper())
        stmt = stmt.order_by(Purchase.purchase_date.desc())
        rows = session.execute(stmt).scalars().all()
        return [_purchase_to_dict(r) for r in rows]


def list_held_tickers(user_id: int) -> list[str]:
    """Distinct tickers this user has any purchase record for."""
    with SessionLocal() as session:
        rows = session.execute(
            select(Purchase.ticker).where(Purchase.user_id == user_id).distinct().order_by(Purchase.ticker)
        ).scalars().all()
        return list(rows)


def list_all_purchase_reasons() -> list[dict]:
    """Every reason attached to any purchase (any user) -- what continuous
    monitoring (app/core/monitor.py) iterates over, one row per reason, with
    the owning purchase's user_id/ticker. Free, read-only."""
    with SessionLocal() as session:
        rows = session.execute(
            select(PurchaseReason, Purchase.user_id, Purchase.ticker)
            .join(Purchase, PurchaseReason.purchase_id == Purchase.id)
        ).all()
        out = []
        for reason, uid, ticker in rows:
            d = _row_to_dict(reason)
            d["user_id"] = uid
            d["ticker"] = ticker
            out.append(d)
        return out


def update_last_notified_status(
    purchase_reason_id: int, status: str, as_of: str | None = None, value: float | None = None,
) -> None:
    """Record what monitoring last saw for one purchase reason: status plus
    the filing date/value it was computed from (so the next pass can report
    the before/after value)."""
    with SessionLocal() as session:
        row = session.get(PurchaseReason, purchase_reason_id)
        if row:
            row.last_notified_status = status
            row.last_checked_as_of = as_of
            row.last_checked_value = value
            session.commit()


# ---------------------------------------------------------------------------
# Thesis reviews (Decision Journal / "Attack the Thesis" -- agent.
# run_thesis_attack's audit trail for one purchase's stated reasoning)
# ---------------------------------------------------------------------------

def save_thesis_review(purchase_id: int, result: dict) -> int:
    """Persist one agent.run_thesis_attack result. `result` is escalated
    (no verdict fields) or a normal verdict -- both shapes handled since an
    escalation is itself a meaningful audit record, not a failure to hide."""
    with SessionLocal() as session:
        row = ThesisReview(
            purchase_id=purchase_id,
            ticker=result["ticker"],
            reason_key=result["reason_key"],
            thesis=result["thesis"],
            thesis_status=result.get("thesis_status"),
            counter_evidence=result.get("counter_evidence"),
            supporting_evidence=result.get("supporting_evidence"),
            confidence=result.get("confidence"),
            human_review_recommended=result.get("human_review_recommended"),
            rationale=result.get("rationale"),
            escalated=bool(result.get("escalated", False)),
            escalation_reason=result.get("escalation_reason"),
            trace_json=result.get("trace"),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def list_thesis_reviews(purchase_id: int) -> list[dict]:
    """Full Decision Journal history for one purchase, newest first."""
    with SessionLocal() as session:
        rows = session.execute(
            select(ThesisReview).where(ThesisReview.purchase_id == purchase_id).order_by(ThesisReview.created_at.desc())
        ).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


def save_thesis_debate(purchase_id: int, result: dict) -> int:
    """Persist one agent.run_bull_bear_debate result."""
    with SessionLocal() as session:
        row = ThesisDebate(
            purchase_id=purchase_id,
            ticker=result["ticker"],
            reason_key=result["reason_key"],
            thesis=result["thesis"],
            bull_case_json=result.get("bull_case"),
            bear_case_json=result.get("bear_case"),
            bull_rebuttal=result.get("bull_rebuttal"),
            bear_rebuttal=result.get("bear_rebuttal"),
            trace_json=result.get("trace"),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def list_thesis_debates(purchase_id: int) -> list[dict]:
    """Full Bull/Bear debate history for one purchase, newest first."""
    with SessionLocal() as session:
        rows = session.execute(
            select(ThesisDebate).where(ThesisDebate.purchase_id == purchase_id).order_by(ThesisDebate.created_at.desc())
        ).scalars().all()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["bull_case"] = d.pop("bull_case_json")
            d["bear_case"] = d.pop("bear_case_json")
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out


# ---------------------------------------------------------------------------
# Notifications (continuous monitoring alerts -- free, mechanical, never
# from the paid Investigation Agent)
# ---------------------------------------------------------------------------

def create_notification(
    user_id: int, ticker: str, reason_key: str | None, message: str,
    previous_status: str | None, current_status: str | None, **details,
) -> int:
    """`details`: optional structured fields (kind, reason_description,
    computed_value, previous_value, comparison, threshold, as_of,
    previous_as_of) the UI renders in the viewer's language."""
    with SessionLocal() as session:
        n = Notification(
            user_id=user_id, ticker=ticker, reason_key=reason_key, message=message,
            previous_status=previous_status, current_status=current_status, **details,
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


# ---------------------------------------------------------------------------
# XBRL tag Thai label cache -- see XbrlTagTranslation's own docstring.
# ---------------------------------------------------------------------------

def get_tag_translations(tags: list[str]) -> dict[str, str]:
    """tag -> label_th, for whichever of `tags` already have a cached
    translation (a fresh/never-seen tag just won't be in the result)."""
    if not tags:
        return {}
    with SessionLocal() as session:
        rows = session.execute(
            select(XbrlTagTranslation).where(XbrlTagTranslation.tag.in_(tags))
        ).scalars().all()
        return {r.tag: r.label_th for r in rows}


def save_tag_translations(entries: list[tuple[str, str, str]]) -> None:
    """`entries` is a list of (tag, label_en, label_th). Upserts so
    re-running the one-time batch translation is safe/idempotent."""
    with SessionLocal() as session:
        for tag, label_en, label_th in entries:
            existing = session.get(XbrlTagTranslation, tag)
            if existing:
                existing.label_en = label_en
                existing.label_th = label_th
            else:
                session.add(XbrlTagTranslation(tag=tag, label_en=label_en, label_th=label_th))
        session.commit()


if __name__ == "__main__":
    init_db()
    print("Initialized PostgreSQL schema")
    print(f"  {len(list_reasons())} built-in reason(s) seeded")
    print(f"  {len(list_profiles())} built-in investor profile(s) seeded")
