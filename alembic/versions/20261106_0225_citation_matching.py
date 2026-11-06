"""#225：持久引用匹配快照、决定依据和按输入签名复用的模型缓存。"""
from alembic import op
import sqlalchemy as sa

revision = '20261106_0225'
down_revision = '20261102_0204'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('paper_reference_extractions', sa.Column('matching_snapshot', sa.JSON(), nullable=True))
    op.add_column('paper_references', sa.Column('match_evidence', sa.JSON(), nullable=True))
    with op.batch_alter_table('paper_references') as batch:
        batch.drop_constraint('ck_paper_references_match_method', type_='check')
        batch.create_check_constraint('ck_paper_references_match_method',
            "match_method IS NULL OR match_method IN ('doi', 'title_year', 'manual', 'llm2')")
    op.create_table('citation_match_cache',
        sa.Column('cache_key', sa.String(64), primary_key=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    bind = op.get_bind()
    counts = [
        "SELECT COUNT(*) FROM paper_references WHERE match_method = 'llm2' OR match_evidence IS NOT NULL",
        "SELECT COUNT(*) FROM paper_reference_extractions WHERE matching_snapshot IS NOT NULL",
        "SELECT COUNT(*) FROM citation_match_cache",
    ]
    if any(bind.execute(sa.text(query)).scalar() for query in counts):
        raise RuntimeError('存在引用匹配结果或失败回执，拒绝降级丢失依据；请先制定明确的数据回退方案')
    op.drop_table('citation_match_cache')
    with op.batch_alter_table('paper_references') as batch:
        batch.drop_constraint('ck_paper_references_match_method', type_='check')
        batch.create_check_constraint('ck_paper_references_match_method',
            "match_method IS NULL OR match_method IN ('doi', 'title_year', 'manual')")
        batch.drop_column('match_evidence')
    op.drop_column('paper_reference_extractions', 'matching_snapshot')
