"""add investor_profile_settings table

Revision ID: e4b1c6a7d9f2
Revises: b7e2a4f91c3d
Create Date: 2026-10-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4b1c6a7d9f2'
down_revision: Union[str, None] = 'b7e2a4f91c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'investor_profile_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('budget_usd', sa.Float(), nullable=True),
        sa.Column('target_growth_pct', sa.Float(), nullable=True),
        sa.Column('investment_horizon', sa.String(), nullable=True),
        sa.Column('risk_tolerance', sa.String(), nullable=True),
        sa.Column('goals', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_investor_profile_settings_user_id'),
    )


def downgrade() -> None:
    op.drop_table('investor_profile_settings')
