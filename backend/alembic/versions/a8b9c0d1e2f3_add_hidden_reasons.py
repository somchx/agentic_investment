"""Allow each account to remove shared screening rules."""
from alembic import op
import sqlalchemy as sa
revision = 'a8b9c0d1e2f3'
down_revision = 'a7d3e5f1b2c4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('hidden_reasons',
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('reason_key', sa.String(), primary_key=True))


def downgrade():
    op.drop_table('hidden_reasons')
