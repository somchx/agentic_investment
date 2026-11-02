"""Agent traces (workflow 2.0) and structured chat answers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'b1d3f5a7c9e2'
down_revision = 'a9c1e3f5b7d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_traces',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('run_kind', sa.String(), nullable=False),
        sa.Column('question', sa.String(), nullable=True),
        sa.Column('tickers', JSONB(), nullable=True),
        sa.Column('intent_json', JSONB(), nullable=True),
        sa.Column('config_json', JSONB(), nullable=False),
        sa.Column('trace_json', JSONB(), nullable=False),
        sa.Column('stop_reason', sa.String(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_traces_user_id', 'agent_traces', ['user_id'])
    op.create_index('ix_agent_traces_created_at', 'agent_traces', ['created_at'])
    op.add_column('chat_messages', sa.Column('answer_json', JSONB(), nullable=True))
    op.add_column('chat_messages', sa.Column('trace_id', sa.Integer(), sa.ForeignKey('agent_traces.id'), nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM agent_traces')).scalar():
        raise RuntimeError('Export agent traces before downgrade: they are the audit trail of paid runs')
    op.drop_column('chat_messages', 'trace_id')
    op.drop_column('chat_messages', 'answer_json')
    op.drop_table('agent_traces')
