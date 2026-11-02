"""Notification detail fields and per-purchase last-checked filing tracking.

Revision ID: b8e4f2a6c1d3
Revises: a8b9c0d1e2f3
"""
from alembic import op
import sqlalchemy as sa

revision = "b8e4f2a6c1d3"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None

NOTIFICATION_COLUMNS = [
    ("kind", sa.String()),
    ("reason_description", sa.String()),
    ("computed_value", sa.Float()),
    ("previous_value", sa.Float()),
    ("comparison", sa.String()),
    ("threshold", sa.Float()),
    ("as_of", sa.String()),
    ("previous_as_of", sa.String()),
]


def upgrade() -> None:
    op.add_column("purchases", sa.Column("last_checked_as_of", sa.String(), nullable=True))
    op.add_column("purchases", sa.Column("last_checked_value", sa.Float(), nullable=True))
    for name, type_ in NOTIFICATION_COLUMNS:
        op.add_column("notifications", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(NOTIFICATION_COLUMNS):
        op.drop_column("notifications", name)
    op.drop_column("purchases", "last_checked_value")
    op.drop_column("purchases", "last_checked_as_of")
