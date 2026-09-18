"""保存与物性内容、来源绑定的证据核对结果。"""
from alembic import op
import sqlalchemy as sa

revision = '20260911_0103'
down_revision = '20260909_0099'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('property_evidence_checks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('paper_revision', sa.Integer(), nullable=False),
        sa.Column('record_id', sa.BigInteger(), sa.ForeignKey('property_records.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('rule_version', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('model', sa.String(200), nullable=False),
        sa.Column('evidence_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('supported','uncertain','unsupported')", name='ck_evidence_check_status'),
    )
    op.create_index('ix_evidence_check_record_hash', 'property_evidence_checks', ['record_id', 'content_hash', 'source_hash', 'rule_version'])


def downgrade():
    op.drop_table('property_evidence_checks')
