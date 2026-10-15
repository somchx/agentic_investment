"""add thesis to purchases and thesis_reviews table

Revision ID: a1f3c9d02b77
Revises: 737a2a8582d9
Create Date: 2026-10-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1f3c9d02b77'
down_revision: Union[str, None] = '737a2a8582d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchases', sa.Column('thesis', sa.String(), nullable=True))
    op.create_table(
        'thesis_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('purchase_id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('reason_key', sa.String(), nullable=False),
        sa.Column('thesis', sa.String(), nullable=False),
        sa.Column('thesis_status', sa.String(), nullable=True),
        sa.Column('counter_evidence', sa.String(), nullable=True),
        sa.Column('supporting_evidence', sa.String(), nullable=True),
        sa.Column('confidence', sa.String(), nullable=True),
        sa.Column('human_review_recommended', sa.Boolean(), nullable=True),
        sa.Column('rationale', sa.String(), nullable=True),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.Column('escalation_reason', sa.String(), nullable=True),
        sa.Column('trace_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_thesis_reviews_purchase_id'), 'thesis_reviews', ['purchase_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_thesis_reviews_purchase_id'), table_name='thesis_reviews')
    op.drop_table('thesis_reviews')
    op.drop_column('purchases', 'thesis')
