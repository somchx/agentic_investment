"""Durable clarification drafts without modifying existing versions or purchases."""
from alembic import op
import sqlalchemy as sa
revision='a9c1e3f5b7d9'
down_revision='f6a8b0c2d4e6'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('thesis_clarifications',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('company',sa.String(),nullable=False),sa.Column('original_text',sa.String(),nullable=False),
        sa.Column('state',sa.String(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_thesis_clarifications_user_id','thesis_clarifications',['user_id'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM thesis_clarifications')).scalar():
        raise RuntimeError('Export clarification history before downgrade')
    op.drop_table('thesis_clarifications')
