"""Add ai_summaries: the latest stored AI Summary per user and ticker.

Revision ID: a7d3e5f1b2c4
Revises: f2c4d6e8a901
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7d3e5f1b2c4"
down_revision = "f2c4d6e8a901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_as_of", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_ai_summaries_user_ticker"),
    )
    op.create_index(op.f("ix_ai_summaries_user_id"), "ai_summaries", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_summaries_user_id"), table_name="ai_summaries")
    op.drop_table("ai_summaries")
