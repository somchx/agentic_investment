"""Add user full name and password session version.

Revision ID: f2c4d6e8a901
Revises: e4b1c6a7d9f2
"""
from alembic import op
import sqlalchemy as sa

revision = "f2c4d6e8a901"
down_revision = "e4b1c6a7d9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing accounts retain their credentials and can fill in their name.
    op.add_column("users", sa.Column("full_name", sa.String(200), nullable=False, server_default=""))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("users", "full_name")
