"""#137 独立谱集合与提取运行，不迁移既有论文数值。"""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0137"
down_revision = "20261010_0127"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("spectrum_collections",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE")),
        sa.Column("paper_revision", sa.Integer()),
        sa.Column("paper_file_id", sa.Integer(), sa.ForeignKey("paper_files.id", ondelete="SET NULL")),
        sa.Column("material_state_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                  sa.ForeignKey("material_states.id", ondelete="SET NULL")),
        sa.Column("state_key", sa.String(96)),
        sa.Column("state_signature", sa.String(64), nullable=False),
        sa.Column("source_key", sa.String(96), nullable=False),
        sa.Column("panel_key", sa.String(96), nullable=False),
        sa.Column("source_json", sa.JSON(), nullable=False),
        sa.Column("current_run_id", sa.String(32)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("review_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("target", "target_id", "source_key", "panel_key", name="uq_spectrum_collection_source"),
        sa.CheckConstraint("target IN ('upload','paper','revision')", name="ck_spectrum_target"))
    op.create_index("ix_spectrum_paper_revision", "spectrum_collections", ["paper_id", "paper_revision"])
    op.create_table("spectrum_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("collection_id", sa.String(32), sa.ForeignKey("spectrum_collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("calibration_json", sa.JSON()),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("collection_id", "input_hash", name="uq_spectrum_run_input"))
    op.create_index("ix_spectrum_run_collection", "spectrum_runs", ["collection_id", "created_at"])


def downgrade():
    op.drop_table("spectrum_runs")
    op.drop_table("spectrum_collections")
