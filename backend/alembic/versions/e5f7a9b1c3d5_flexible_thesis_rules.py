"""Add versioned directional rules without changing legacy definitions/snapshots."""
from alembic import op
import sqlalchemy as sa
revision = 'e5f7a9b1c3d5'
down_revision = 'd4e6f8a0b2c4'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('reasons', sa.Column('rule_definition', sa.JSON(), nullable=True))
    op.add_column('reasons', sa.Column('original_text', sa.String(), nullable=False, server_default=''))
    op.alter_column('reasons', 'threshold', existing_type=sa.Float(), nullable=True)

def downgrade():
    # Refuse destructive loss of definitions created by the new application.
    count = op.get_bind().execute(sa.text('SELECT count(*) FROM reasons WHERE rule_definition IS NOT NULL')).scalar()
    if count:
        raise RuntimeError('Cannot downgrade while versioned thesis definitions exist; export/migrate them first')
    op.alter_column('reasons', 'threshold', existing_type=sa.Float(), nullable=False)
    op.drop_column('reasons', 'original_text')
    op.drop_column('reasons', 'rule_definition')
