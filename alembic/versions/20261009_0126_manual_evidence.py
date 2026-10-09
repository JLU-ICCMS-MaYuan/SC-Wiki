"""#109：人工修改理由和独立证据。"""

from alembic import op
import sqlalchemy as sa


revision = "20261009_0126"
down_revision = "20261009_0125"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scientific_manual_evidence",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("paper_id", sa.Integer()),
        sa.Column("paper_revision", sa.Integer()),
        sa.Column("item_key", sa.String(64), nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("before_value", sa.JSON()),
        sa.Column("after_value", sa.JSON()),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_name_snapshot", sa.String(100)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("no_evidence_reason", sa.Text(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("evidence_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_manual_evidence_target_field", "scientific_manual_evidence", ["target", "target_id", "item_key"])
    op.create_index("ix_manual_evidence_paper_revision", "scientific_manual_evidence", ["paper_id", "paper_revision"])


def downgrade():
    op.drop_index("ix_manual_evidence_paper_revision", table_name="scientific_manual_evidence")
    op.drop_index("ix_manual_evidence_target_field", table_name="scientific_manual_evidence")
    op.drop_table("scientific_manual_evidence")
