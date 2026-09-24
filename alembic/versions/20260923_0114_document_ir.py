"""Issue #114：当前论文 revision 的 Document IR 与区域 Evidence 定位。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260923_0114"
down_revision = "20260918_0108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_document_parser_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("paper_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("paper_file_id", sa.Integer(), nullable=False),
        sa.Column("parse_profile", sa.String(length=32), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reading_state", sa.String(length=32), nullable=True),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("document_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("ir_schema_version", sa.String(length=32), server_default="1", nullable=False),
        sa.Column("rule_version", sa.String(length=32), server_default="1", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(
            ["paper_file_id", "paper_id", "paper_revision"],
            ["paper_files.id", "paper_files.paper_id", "paper_files.paper_revision"],
            name="fk_document_parser_runs_file_revision", ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "paper_id", "paper_revision", "paper_file_id", name="uq_document_parser_runs_identity"),
    )
    op.create_index("ix_document_parser_runs_paper_id", "paper_document_parser_runs", ["paper_id"])
    op.create_index("ix_document_parser_runs_file_revision", "paper_document_parser_runs", ["paper_file_id", "paper_id", "paper_revision"])

    op.create_table(
        "paper_document_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("paper_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("paper_file_id", sa.Integer(), nullable=False),
        sa.Column("parser_run_id", sa.Integer(), nullable=False),
        sa.Column("block_id", sa.String(length=255), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("pdf_page", sa.Integer(), nullable=False),
        sa.Column("printed_page", sa.Integer(), nullable=True),
        sa.Column("reading_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
        sa.Column("bbox_json", sa.JSON(), nullable=True),
        sa.Column("polygon_json", sa.JSON(), nullable=True),
        sa.Column("table_id", sa.String(length=128), nullable=True),
        sa.Column("figure_id", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parser_run_id", "paper_id", "paper_revision", "paper_file_id"],
            ["paper_document_parser_runs.id", "paper_document_parser_runs.paper_id", "paper_document_parser_runs.paper_revision", "paper_document_parser_runs.paper_file_id"],
            name="fk_document_blocks_parser_run", ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "paper_revision", "paper_file_id", "parser_run_id", "block_id", name="uq_document_blocks_run_block"),
        sa.UniqueConstraint("id", "paper_id", "paper_file_id", "parser_run_id", name="uq_document_blocks_identity"),
    )
    op.create_index("ix_document_blocks_paper_id", "paper_document_blocks", ["paper_id"])
    op.create_index("ix_document_blocks_paper_file_id", "paper_document_blocks", ["paper_file_id"])
    op.create_index("ix_document_blocks_parser_run_id", "paper_document_blocks", ["parser_run_id"])
    op.create_index("ix_document_blocks_page", "paper_document_blocks", ["paper_file_id", "paper_revision", "pdf_page"])

    op.create_table(
        "paper_evidence_locators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("paper_evidence_id", sa.Integer(), nullable=False),
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("paper_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("paper_file_id", sa.Integer(), nullable=False),
        sa.Column("parser_run_id", sa.Integer(), nullable=False),
        sa.Column("document_block_id", sa.Integer(), nullable=False),
        sa.Column("pdf_page", sa.Integer(), nullable=False),
        sa.Column("printed_page", sa.Integer(), nullable=True),
        sa.Column("bbox_json", sa.JSON(), nullable=True),
        sa.Column("polygon_json", sa.JSON(), nullable=True),
        sa.Column("table_id", sa.String(length=128), nullable=True),
        sa.Column("figure_id", sa.String(length=128), nullable=True),
        sa.Column("quote", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
        sa.Column("source_kind", sa.String(length=32), server_default="text_layer", nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=128), nullable=False),
        sa.Column("source_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("locator_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(
            ["paper_evidence_id", "paper_id", "paper_revision"],
            ["paper_evidences.id", "paper_evidences.paper_id", "paper_evidences.paper_revision"],
            name="fk_paper_evidence_locators_evidence", ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_block_id", "paper_id", "paper_file_id", "parser_run_id"],
            ["paper_document_blocks.id", "paper_document_blocks.paper_id", "paper_document_blocks.paper_file_id", "paper_document_blocks.parser_run_id"],
            name="fk_paper_evidence_locators_block", ondelete="CASCADE", onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("locator_hash", name="uq_paper_evidence_locators_hash"),
    )
    op.create_index("ix_paper_evidence_locators_paper_evidence_id", "paper_evidence_locators", ["paper_evidence_id"])
    op.create_index("ix_paper_evidence_locators_paper_id", "paper_evidence_locators", ["paper_id"])
    op.create_index("ix_paper_evidence_locators_paper_file_id", "paper_evidence_locators", ["paper_file_id"])
    op.create_index("ix_paper_evidence_locators_parser_run_id", "paper_evidence_locators", ["parser_run_id"])
    op.create_index("ix_paper_evidence_locators_document_block_id", "paper_evidence_locators", ["document_block_id"])
    op.create_index("ix_paper_evidence_locators_page", "paper_evidence_locators", ["paper_file_id", "paper_revision", "pdf_page"])


def downgrade():
    # MySQL 外键依赖其索引；按依赖逆序删表时一并删除索引。
    op.drop_table("paper_evidence_locators")
    op.drop_table("paper_document_blocks")
    op.drop_table("paper_document_parser_runs")
