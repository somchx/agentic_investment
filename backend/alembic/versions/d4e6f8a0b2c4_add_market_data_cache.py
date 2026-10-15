"""Persistent price cache and provider request budget."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = 'd4e6f8a0b2c4'
down_revision = 'c3f5a7b9d2e4'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('market_data_cache', sa.Column('key', sa.String(), primary_key=True),
                    sa.Column('payload', JSONB(), nullable=False), sa.Column('fetched_at',sa.Float(),nullable=False))
    op.create_table('market_data_usage', sa.Column('day',sa.String(10),primary_key=True),
                    sa.Column('requests',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('market_data_usage')
    op.drop_table('market_data_cache')
