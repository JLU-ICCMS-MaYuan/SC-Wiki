"""浅度论文直接收录状态；保留原审核状态语义。"""
from alembic import op
import sqlalchemy as sa

revision = '20261112_0241'
down_revision = '20261106_0225'
branch_labels = None
depends_on = None


def constraint(extra):
    return ("content_revision >= 1 AND ((review_status = 'approved' "
            "AND approved_revision = content_revision) OR "
            "(review_status IN ('pending', 'rejected'" + extra + ") AND approved_revision IS NULL))")


def upgrade():
    with op.batch_alter_table('papers') as batch:
        batch.drop_constraint('ck_papers_review_revision', type_='check')
        batch.create_check_constraint('ck_papers_review_revision', constraint(", 'published'"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM papers WHERE review_status='published'")).scalar():
        raise RuntimeError('存在浅度直接收录论文，拒绝降级丢失公开状态；请先明确数据回退方案')
    with op.batch_alter_table('papers') as batch:
        batch.drop_constraint('ck_papers_review_revision', type_='check')
        batch.create_check_constraint('ck_papers_review_revision', constraint(''))
