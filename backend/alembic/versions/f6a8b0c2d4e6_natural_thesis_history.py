"""Append-only qualitative thesis versions and evidence investigations."""
from alembic import op
import sqlalchemy as sa
revision='f6a8b0c2d4e6'
down_revision='e5f7a9b1c3d5'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('thesis_versions',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reason_key',sa.String(),nullable=False),sa.Column('version_no',sa.Integer(),nullable=False),
        sa.Column('company',sa.String(),nullable=False),sa.Column('original_text',sa.String(),nullable=False),
        sa.Column('definition',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('reason_key','version_no',name='uq_thesis_version'))
    op.create_table('thesis_investigations',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('reason_key',sa.String(),nullable=False),
        sa.Column('thesis_version_id',sa.String(),sa.ForeignKey('thesis_versions.id'),nullable=False),
        sa.Column('purchase_id',sa.Integer(),sa.ForeignKey('purchases.id'),nullable=True),
        sa.Column('evaluation_date',sa.String(),nullable=False),sa.Column('result',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    for table in ('thesis_versions','thesis_investigations'):
        for col in ('user_id','reason_key'):op.create_index(f'ix_{table}_{col}',table,[col])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM thesis_versions')).scalar():
        raise RuntimeError('Refusing to discard confirmed thesis history')
    op.drop_table('thesis_investigations')
    op.drop_table('thesis_versions')
