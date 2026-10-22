"""为自动资讯增加独立分类结果和已有材料家族关联。"""
from alembic import op
import sqlalchemy as sa

revision = "20261022_0153"
down_revision = "20261022_0147b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "news_feed_classifications",
        sa.Column("item_id", sa.String(32), sa.ForeignKey("news_feed_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("paper_type", sa.String(20), nullable=True),
        sa.Column("theoretical_subtype", sa.String(20), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("catalog_hash", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("attempt_token", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(20), nullable=False),
        sa.CheckConstraint("paper_type IS NULL OR paper_type IN ('experimental','theoretical','review')", name="ck_news_classification_type"),
        sa.CheckConstraint("theoretical_subtype IS NULL OR (paper_type IS NOT NULL AND paper_type = 'theoretical' AND theoretical_subtype IN ('calculation','method','theory'))", name="ck_news_classification_subtype"),
        sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_news_classification_status"),
    )
    op.create_table(
        "news_feed_material_families",
        sa.Column("item_id", sa.String(32), sa.ForeignKey("news_feed_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("material_family_id", sa.Integer(), sa.ForeignKey("material_families.id", ondelete="RESTRICT"), primary_key=True),
    )


def downgrade():
    op.drop_table("news_feed_material_families")
    op.drop_table("news_feed_classifications")
