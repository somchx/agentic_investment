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
    full_name = Column(String(200), nullable=False, default="", server_default="")
    password_hash = Column(String, nullable=False)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    reasons = relationship("Reason", back_populates="user")
    investor_profiles = relationship("InvestorProfile", back_populates="user")
    purchases = relationship("Purchase", back_populates="user")
    investor_profile_settings = relationship(
        "InvestorProfileSettings", back_populates="user", uselist=False,
    )


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


class InvestorProfileSettings(Base):
    """The user's own single investor profile -- budget/goals/risk
    tolerance for THEM, not a reusable named preset (see InvestorProfile
    above, used by the screener's /personalize pipeline). One row per user,
    referenced by the portfolio-wide chat agent so it can personalize its
    answers (and, once a profile is set, suggest candidate tickers from the
    tracked universe -- see answer_portfolio_question's docstring)."""

    __tablename__ = "investor_profile_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    budget_usd = Column(Float, nullable=True)
    target_growth_pct = Column(Float, nullable=True)
    investment_horizon = Column(String, nullable=True)  # '<1y' | '1-5y' | '>5y'
    risk_tolerance = Column(String, nullable=True)  # 'low' | 'medium' | 'high'
    goals = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="investor_profile_settings")


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
    # Unresolved Evidence Assessor complaints for this reason, if the loop
    # gave up after MAX_REJECTIONS and accepted the finalize call anyway
    # (see investigation_state.assess_sufficiency / agent.LoopController).
    # NULL/empty means the assessor was satisfied. Added in Code Audit
    # Session 2 (item 2) -- previously this information existed in memory
    # but was silently dropped on the way to the database.
    assessor_gaps_json = Column(JSONB, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)


class AiSummary(Base):
    """The latest "AI Summary" (a POST /investigate/{ticker} result) one user
    generated for one ticker, so reopening the company modal shows it again
    without paying for another LLM call. Regenerating overwrites it -- the
    full per-reason audit trail stays in investigation_runs."""

    __tablename__ = "ai_summaries"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_ai_summaries_user_ticker"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False)
    result_json = Column(JSONB, nullable=False)
    # Latest SEC filing date behind the reasons the run covered, so the UI
    # can say what point in time the summary describes.
    data_as_of = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


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
    # Legacy single-reason fields, kept as a mirror of the FIRST of
    # `reasons` for older readers. The source of truth for every reason
    # attached to a purchase is PurchaseReason (a purchase can have several).
    reason_key = Column(String, nullable=True)
    reason_snapshot_json = Column(JSONB, nullable=True)
    # Superseded by PurchaseReason's per-reason monitoring state.
    # The reason's status as of the last continuous-monitoring pass (see
    # app/core/monitor.py) -- NULL until the first pass runs. Compared
    # against a fresh check_reason_status() each pass; a change creates a
    # Notification. Deliberately separate from reason_snapshot_json's
    # frozen status_at_purchase, which must never change once written.
    last_notified_status = Column(String, nullable=True)
    # Latest filing date / value monitoring has already evaluated -- a later
    # as_of means a new filing landed since the last pass.
    last_checked_as_of = Column(String, nullable=True)
    last_checked_value = Column(Float, nullable=True)
    # Decision Journal (extends Contribution 2 to the investor's own
    # reasoning, not just the frozen rule): free-text WHY the investor
    # bought, frozen alongside the WHAT in reason_snapshot_json. Optional
    # -- a purchase can still be recorded without one, same as reason_key.
    thesis = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Pre-existing latent bug fixed in passing: User.purchases declared
    # back_populates="user" but Purchase never defined the reverse side --
    # dormant because SQLAlchemy only validates back_populates when mappers
    # are actually configured, which nothing had forced until ThesisReview's
    # own back_populates below triggered it.
    user = relationship("User", back_populates="purchases")
    thesis_reviews = relationship("ThesisReview", back_populates="purchase", cascade="all, delete-orphan")
    thesis_debates = relationship("ThesisDebate", back_populates="purchase", cascade="all, delete-orphan")
    reasons = relationship(
        "PurchaseReason", back_populates="purchase", cascade="all, delete-orphan",
        order_by="PurchaseReason.position",
    )


class PurchaseReason(Base):
    """One reason attached to a purchase, with its rule and status frozen at
    the purchase date (same discipline as the original single
    reason_snapshot_json) plus its own continuous-monitoring state."""

    __tablename__ = "purchase_reasons"
    __table_args__ = (UniqueConstraint("purchase_id", "reason_key", name="uq_purchase_reasons_purchase_reason"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)  # order the user picked them in
    reason_key = Column(String, nullable=False)
    reason_snapshot_json = Column(JSONB, nullable=True)
    last_notified_status = Column(String, nullable=True)
    last_checked_as_of = Column(String, nullable=True)
    last_checked_value = Column(Float, nullable=True)

    purchase = relationship("Purchase", back_populates="reasons")


class ThesisReview(Base):
    """One "Attack the Thesis" run (agent.run_thesis_attack) against a
    Purchase's Decision Journal entry -- an adversarial review that tries
    to find evidence AGAINST the investor's stated reason for buying,
    instead of only re-confirming the frozen rule's number. Kept as its
    own audit trail (not folded into InvestigationRun) since it reviews a
    specific purchase's thesis, not a ticker's reasons in general."""

    __tablename__ = "thesis_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False)
    reason_key = Column(String, nullable=False)
    thesis = Column(String, nullable=False)
    thesis_status = Column(String, nullable=True)  # "Still Holds" | "Weakened" | "Broken"
    counter_evidence = Column(String, nullable=True)
    supporting_evidence = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    human_review_recommended = Column(Boolean, nullable=True)
    rationale = Column(String, nullable=True)
    escalated = Column(Boolean, nullable=False, default=False)
    escalation_reason = Column(String, nullable=True)
    trace_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    purchase = relationship("Purchase", back_populates="thesis_reviews")


class ThesisDebate(Base):
    """One Mr. Bull / Mr. Bear Cross-Debate run (agent.run_bull_bear_debate)
    against a Purchase's Decision Journal entry -- two evidence-grounded
    cases (for and against the thesis holding) plus one rebuttal each,
    kept as its own audit trail distinct from ThesisReview's single-verdict
    Attack-the-Thesis (this one deliberately returns no verdict -- the
    investor weighs both cases themselves, see run_bull_bear_debate's
    docstring)."""

    __tablename__ = "thesis_debates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False, index=True)
    ticker = Column(String, nullable=False)
    reason_key = Column(String, nullable=False)
    thesis = Column(String, nullable=False)
    bull_case_json = Column(JSONB, nullable=True)
    bear_case_json = Column(JSONB, nullable=True)
    bull_rebuttal = Column(String, nullable=True)
    bear_rebuttal = Column(String, nullable=True)
    trace_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    purchase = relationship("Purchase", back_populates="thesis_debates")


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
    # Structured detail of the change (kind is STATUS_CHANGED), so the UI can
    # render it in the viewer's language instead of the stored English `message`.
    kind = Column(String, nullable=True)
    reason_description = Column(String, nullable=True)
    computed_value = Column(Float, nullable=True)
    previous_value = Column(Float, nullable=True)
    comparison = Column(String, nullable=True)
    threshold = Column(Float, nullable=True)
    as_of = Column(String, nullable=True)
    previous_as_of = Column(String, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)


class XbrlTagTranslation(Base):
    """Cached Thai translation of one SEC/XBRL tag's official English
    label -- translated once (via Claude, a real but tiny one-time batch
    cost, explicitly approved) and reused forever after, never
    re-translated on the fly. This is a display-label cache only: it never
    touches the tag name itself or any computed financial value, so a
    translation quirk can't affect evidence accuracy, only how a metric's
    name reads in the picker."""

    __tablename__ = "xbrl_tag_translations"

    tag = Column(String, primary_key=True)
    label_en = Column(String, nullable=False)
    label_th = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class HiddenReason(Base):
    """Per-account removal of shared rules without changing other accounts."""
    __tablename__ = 'hidden_reasons'
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    reason_key = Column(String, primary_key=True)
