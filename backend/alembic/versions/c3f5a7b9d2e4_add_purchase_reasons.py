"""Several reasons per purchase: purchase_reasons, backfilled from the
single reason_key / reason_snapshot_json each purchase had until now.

Revision ID: c3f5a7b9d2e4
Revises: b8e4f2a6c1d3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3f5a7b9d2e4"
down_revision = "b8e4f2a6c1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_reasons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason_key", sa.String(), nullable=False),
        sa.Column("reason_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_notified_status", sa.String(), nullable=True),
        sa.Column("last_checked_as_of", sa.String(), nullable=True),
        sa.Column("last_checked_value", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id", "reason_key", name="uq_purchase_reasons_purchase_reason"),
    )
    op.create_index(op.f("ix_purchase_reasons_purchase_id"), "purchase_reasons", ["purchase_id"], unique=False)
    # Every existing purchase keeps its one reason (and its monitoring state) as reason #0.
    op.execute(
        """
        INSERT INTO purchase_reasons
            (purchase_id, position, reason_key, reason_snapshot_json,
             last_notified_status, last_checked_as_of, last_checked_value)
        SELECT id, 0, reason_key, reason_snapshot_json,
               last_notified_status, last_checked_as_of, last_checked_value
        FROM purchases
        WHERE reason_key IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_reasons_purchase_id"), table_name="purchase_reasons")
    op.drop_table("purchase_reasons")
