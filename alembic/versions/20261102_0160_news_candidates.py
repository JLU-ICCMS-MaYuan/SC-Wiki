"""持久化收录前的期刊候选，不修改已有公开资讯或科研数据。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision = "20261102_0160"
# 已提交基线有两个分支头；本次只合并版本图，业务变更仍只有候选表。
down_revision = ("20261020_0049", "20261101_0198")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "news_feed_candidates",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("record_json", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("attempt_token", sa.String(32), nullable=False),
        sa.Column("first_seen_at", sa.String(20), nullable=False),
        sa.Column("last_seen_at", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.String(20), nullable=False),
        sa.CheckConstraint("status IN ('pending','running','related','unrelated','insufficient','failed')", name="ck_news_candidate_status"),
    )
    op.create_index("ix_news_candidate_status_updated", "news_feed_candidates", ["status", "updated_at"])


def downgrade():
    op.drop_table("news_feed_candidates")
