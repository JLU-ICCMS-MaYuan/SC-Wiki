"""全科学数据持久核对及正式来源；不回填历史数据。"""
from alembic import op
import sqlalchemy as sa

revision = '20260915_0103'
down_revision = '20260911_0103'
branch_labels = ('scientific_evidence',)
depends_on = None


def upgrade():
    op.create_table('scientific_evidence_checks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('target', sa.String(16), nullable=False),
        sa.Column('target_id', sa.String(64), nullable=False),
        sa.Column('item_key', sa.String(64), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('rule_version', sa.String(64), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('resolutions', sa.JSON(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('target','target_id','item_key','content_hash','source_hash','rule_version', name='uq_scientific_check_version'))
    op.create_table('scientific_evidence_sources',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('paper_id', sa.Integer(), sa.ForeignKey('papers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('paper_revision', sa.Integer(), nullable=False),
        sa.Column('item_key', sa.String(64), nullable=False),
        sa.Column('field_path', sa.String(500), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('rule_version', sa.String(64), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('paper_id','paper_revision','item_key', name='uq_scientific_source_item'))
    op.create_table('scientific_structure_origins',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('target', sa.String(16), nullable=False),
        sa.Column('target_id', sa.String(64), nullable=False),
        sa.Column('structure_hash', sa.String(64), nullable=False),
        sa.Column('provenance', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('target','target_id','structure_hash', name='uq_scientific_structure_origin'))


def downgrade():
    for name in ('scientific_structure_origins', 'scientific_evidence_sources', 'scientific_evidence_checks'):
        op.drop_table(name)
