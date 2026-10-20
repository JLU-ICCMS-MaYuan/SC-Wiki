"""#142：只读社区与多模型 AI 生成；保留历史内容。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "20261020_0142"
down_revision = "20261015_0094"
branch_labels = None
depends_on = None

FIELDS = [
    sa.Column("origin", sa.String(16), nullable=False, server_default="human"),
    sa.Column("category", sa.String(64), nullable=False, server_default=""),
    sa.Column("model_id", sa.String(64), nullable=False, server_default=""),
    sa.Column("model_name", sa.String(200), nullable=False, server_default=""),
    sa.Column("model", sa.String(200), nullable=False, server_default=""),
    sa.Column("model_order", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("citations", sa.JSON()),
    sa.Column("human_edited", sa.Boolean(), nullable=False, server_default="0"),
    sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("question_hash", sa.String(64)),
]

def upgrade():
    with op.batch_alter_table("community_entries") as batch:
        batch.alter_column("author_id", existing_type=sa.Integer(), nullable=True)
        for column in FIELDS:
            batch.add_column(column._copy())
        batch.create_unique_constraint("uq_community_question_hash", ["question_hash"])
    # 固定表结构在迁移中声明，避免历史迁移依赖未来 ORM 变化。
    op.create_table("community_ai_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("community_entries.id"), unique=True),
        sa.Column("state", sa.String(16), nullable=False), sa.Column("error", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False), sa.Column("question_model_id", sa.String(64), nullable=False),
        sa.Column("sources", sa.JSON()), sa.Column("job_id", sa.String(80), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()))
    op.create_table("community_ai_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("community_ai_batches.id"), nullable=False, index=True),
        sa.Column("model_id", sa.String(64), nullable=False), sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model", sa.String(200), nullable=False), sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("model_order", sa.Integer(), nullable=False),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("community_entries.id"), unique=True),
        sa.Column("state", sa.String(16), nullable=False), sa.Column("error", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(80), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("question_revision", sa.Integer(), nullable=False), sa.Column("answer_revision", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()),
        sa.UniqueConstraint("batch_id", "model_id", name="uq_community_ai_model"))
    op.create_table("community_entry_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("citations", sa.JSON()), sa.Column("human_edited", sa.Boolean(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entry_id", "revision", name="uq_community_revision"))

def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM community_ai_batches")) or bind.scalar(sa.text("SELECT COUNT(*) FROM community_entry_revisions")) or bind.scalar(sa.text("SELECT COUNT(*) FROM community_entries WHERE author_id IS NULL OR origin = 'ai'")):
        raise RuntimeError("已有 AI 内容或修订历史，拒绝破坏性降级；请先备份并制定恢复方案")
    for table in ("community_entry_revisions", "community_ai_tasks", "community_ai_batches"):
        op.drop_table(table)
    with op.batch_alter_table("community_entries") as batch:
        batch.drop_constraint("uq_community_question_hash", type_="unique")
        for column in reversed(FIELDS):
            batch.drop_column(column.name)
        batch.alter_column("author_id", existing_type=sa.Integer(), nullable=False)
