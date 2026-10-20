"""#143：原子多模型提交的幂等组，不改动已有答案。"""
from alembic import op
import sqlalchemy as sa

revision = "20261020_0143b"
down_revision = "20261020_0143"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("community_answer_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_keys", sa.JSON(), nullable=False),
        sa.Column("item_ids", sa.JSON(), nullable=False),
        sa.Column("retry_of", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM community_answer_groups")):
        raise RuntimeError("已有多模型提交记录，拒绝清除幂等历史；请先备份并制定恢复方案")
    op.drop_table("community_answer_groups")
