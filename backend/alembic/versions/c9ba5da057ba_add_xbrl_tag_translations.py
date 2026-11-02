"""add xbrl_tag_translations

Revision ID: c9ba5da057ba
Revises: 1b9ede227411
Create Date: 2026-09-21 17:46:22.156993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9ba5da057ba'
down_revision: Union[str, None] = '1b9ede227411'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Written by hand -- this dev DB's uvicorn --reload already ran
    # Base.metadata.create_all() for this table (same gotcha as prior
    # migrations in this project). Matches app/db/models.py exactly so a
    # fresh database still gets it from `alembic upgrade head` alone.
    op.create_table(
        'xbrl_tag_translations',
        sa.Column('tag', sa.String(), nullable=False),
        sa.Column('label_en', sa.String(), nullable=False),
        sa.Column('label_th', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('tag'),
    )


def downgrade() -> None:
    op.drop_table('xbrl_tag_translations')
