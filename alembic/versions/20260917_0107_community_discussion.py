"""新增社区问答、评论、弹幕及治理通知表；不回填或改写原业务数据。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "20260917_0107"
down_revision = "20260916_0106"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("community_systems",
        sa.Column("system_key", sa.String(100), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("community_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("body", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE")),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE")),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE")),
        sa.Column("system_key", sa.String(100), sa.ForeignKey("community_systems.system_key")),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="SET NULL")),
        sa.Column("reply_to_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="visible"),
        *[sa.Column(n, sa.DateTime(), nullable=False, server_default=sa.func.now()) for n in ("created_at", "updated_at", "activity_at")])
    for name, columns in (
        ("question", ["kind", "status", "activity_at", "id"]),
        ("answer", ["question_id", "kind", "status", "id"]),
        ("answer_comments", ["answer_id", "kind", "id"]),
        ("paper", ["paper_id", "kind", "status", "id"]),
        ("system", ["system_key", "kind", "status", "id"]),
    ):
        op.create_index("ix_community_" + name, "community_entries", columns)
    op.create_table("community_votes",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("community_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.UniqueConstraint("entry_id", "reporter_id", name="uq_community_report"))
    op.create_index("ix_community_reports_status", "community_reports", ["status"])
    op.create_table("community_moderation_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_community_moderation_events_entry_id", "community_moderation_events", ["entry_id"])
    op.create_table("community_notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("read_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_community_notifications_recipient", "community_notifications", ["recipient_id", "read_at", "id"])


def downgrade():
    for table in ("community_notifications", "community_moderation_events", "community_reports", "community_votes", "community_entries", "community_systems"):
        op.drop_table(table)
