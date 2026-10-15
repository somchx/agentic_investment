"""add thesis_debates table

Revision ID: b7e2a4f91c3d
Revises: a1f3c9d02b77
Create Date: 2026-10-12 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e2a4f91c3d'
down_revision: Union[str, None] = 'a1f3c9d02b77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'thesis_debates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('purchase_id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('reason_key', sa.String(), nullable=False),
        sa.Column('thesis', sa.String(), nullable=False),
        sa.Column('bull_case_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bear_case_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bull_rebuttal', sa.String(), nullable=True),
        sa.Column('bear_rebuttal', sa.String(), nullable=True),
        sa.Column('trace_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_thesis_debates_purchase_id'), 'thesis_debates', ['purchase_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_thesis_debates_purchase_id'), table_name='thesis_debates')
    op.drop_table('thesis_debates')
