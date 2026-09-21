"""SQLAlchemy ORM models -- the PostgreSQL replacement for the old
src/db.py SQLite schema. Table/column names are kept identical to the
already-tested SQLite version (see src/db.py's own docstring) rather than
renamed to the reviewer's suggested screening_rules/positions terminology,
since the shipped feature (register -> screen -> record purchase -> track
whether the reason still holds) was already built and end-to-end tested
against these exact names; renaming now would be churn with no functional
benefit. `reasons` here *is* the "screening_rules" concept from that
review, and `purchases` *is* "positions" -- same relationships, same
point-in-time snapshot discipline, just the names already in place.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    reasons = relationship("Reason", back_populates="user")
    investor_profiles = relationship("InvestorProfile", back_populates="user")
    purchases = relationship("Purchase", back_populates="user")


class Reason(Base):
    """A screening rule: built-in (user_id NULL, shared by everyone) or a
    user's own custom condition, optionally scoped to one ticker."""

    __tablename__ = "reasons"

    reason_key = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker = Column(String, nullable=True)
    metric = Column(String, nullable=False)
    comparison = Column(String, nullable=False)  # '>' | '>=' | '<' | '<='
    threshold = Column(Float, nullable=False)
    kind = Column(String, nullable=False)  # 'yoy_growth' | 'margin_level'
    denominator_metric = Column(String, nullable=False, default="")
    description = Column(String, nullable=False)
    instant = Column(Boolean, nullable=False, default=False)
    is_builtin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="reasons")


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_investor_profiles_user_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    risk_tolerance = Column(String, nullable=False)  # 'low' | 'medium' | 'high'
    investment_horizon = Column(String, nullable=False)  # '<1y' | '1-5y' | '>5y'
    position_size_pct = Column(Float, nullable=False)
    objective = Column(String, nullable=False)  # 'growth' | 'income' | 'preservation'
    is_builtin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="investor_profiles")


class InvestigationRun(Base):
    """One reason's result from an agent.run_with_llm /
    personalization.investigate_and_personalize call -- a paid-LLM audit
    trail, kept for the run-to-run consistency and cost-tracking work."""

    __tablename__ = "investigation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    reason_key = Column(String, nullable=False)
    status = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    human_review_recommended = Column(Boolean, nullable=True)
    rationale = Column(String, nullable=True)
    escalated = Column(Boolean, nullable=False, default=False)
    escalation_reason = Column(String, nullable=True)
    profile_name = Column(String, nullable=True)
    rule_based_tier = Column(String, nullable=True)
    llm_tier = Column(String, nullable=True)
    integrity_ok = Column(Boolean, nullable=True)
    trace_json = Column(JSONB, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)


class Purchase(Base):
    """The real position record: what was bought, how much, when, and a
    frozen snapshot of the reason that justified the buy plus its status
    AT THAT MOMENT -- so "is the reason I bought this for still true" is
    answered by comparing the snapshot to the reason's current live
    status, never by silently re-grading the past against today's rule.
    """

    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    purchase_price = Column(Float, nullable=False)
    purchase_date = Column(String, nullable=False)  # ISO date the user says they bought
    reason_key = Column(String, nullable=True)
    reason_snapshot_json = Column(JSONB, nullable=True)
    # The reason's status as of the last continuous-monitoring pass (see
    # app/core/monitor.py) -- NULL until the first pass runs. Compared
    # against a fresh check_reason_status() each pass; a change creates a
    # Notification. Deliberately separate from reason_snapshot_json's
    # frozen status_at_purchase, which must never change once written.
    last_notified_status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="purchases")


class ChatConversation(Base):
    """One agent-chat conversation thread (the portfolio-wide "Ask the
    agent" page). Kept as a real, permanent record -- same reasoning as
    InvestigationRun: every message in it is a paid LLM call, so a
    conversation is an audit trail, not disposable client-side state.
    "New chat" never deletes the old thread, it just starts a new row."""

    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Auto-derived from the first user message (truncated) -- there is no
    # separate "rename conversation" feature yet.
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    messages = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(String, nullable=False)
    # Only ever set on assistant messages -- what that one reply cost/used.
    cost_usd = Column(Float, nullable=True)
    tool_calls_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    conversation = relationship("ChatConversation", back_populates="messages")


class Notification(Base):
    """A free, mechanical alert from continuous monitoring (app/core/
    monitor.py) that one position's reason status changed since the last
    check -- e.g. Supported -> Weakened. Never created by the paid
    Investigation Agent; surfacing this is the cue for the user to open
    that (on-demand, paid) agent themselves if they want more detail."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False)
    reason_key = Column(String, nullable=True)
    message = Column(String, nullable=False)
    previous_status = Column(String, nullable=True)
    current_status = Column(String, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
