"""#143：问题内排队和同模型追加；与其他功能分支独立。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "20261020_0143"
down_revision = "20261020_0142"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("community_model_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False, unique=True),
        sa.Column("first_sequence", sa.Integer(), nullable=False),
        sa.UniqueConstraint("question_id", "config_hash", name="uq_community_model_card"))
    op.create_table("community_answer_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False), sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model", sa.String(200), nullable=False), sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False), sa.Column("error", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(80), nullable=False),
        sa.Column("retry_of", sa.Integer(), sa.ForeignKey("community_answer_requests.id")),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("community_entries.id")), sa.Column("turn_id", sa.Integer()),
        sa.Column("context_snapshot", sa.JSON()), sa.Column("sources", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()),
        sa.UniqueConstraint("question_id", "sequence", name="uq_community_answer_sequence"))
    op.create_table("community_answer_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id"), nullable=False, index=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("community_answer_requests.id"), nullable=False, unique=True),
        sa.Column("body", sa.Text().with_variant(MEDIUMTEXT(),"mysql"), nullable=False),
        sa.Column("citations", sa.JSON()), sa.Column("replies", sa.JSON()),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("human_edited", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("community_answer_turn_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn_id", sa.Integer(), sa.ForeignKey("community_answer_turns.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text().with_variant(MEDIUMTEXT(),"mysql"), nullable=False),
        sa.Column("citations", sa.JSON()), sa.Column("replies", sa.JSON()),
        sa.Column("human_edited", sa.Boolean(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("turn_id", "revision", name="uq_community_turn_revision"))
    op.execute("""INSERT INTO community_model_answers(question_id,config_hash,entry_id,first_sequence)
        SELECT e.question_id,t.config_hash,e.id,ROW_NUMBER() OVER (PARTITION BY e.question_id ORDER BY e.id)
        FROM community_entries e JOIN community_ai_tasks t ON t.answer_id=e.id
        WHERE e.kind='answer' AND e.origin='ai'""")


def downgrade():
    bind=op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM community_answer_requests")) or bind.scalar(sa.text("SELECT COUNT(*) FROM community_answer_turns")):
        raise RuntimeError("存在连续回答，拒绝破坏性降级；请先备份并制定恢复方案")
    for table in ("community_answer_turn_revisions","community_answer_turns","community_answer_requests","community_model_answers"):
        op.drop_table(table)
