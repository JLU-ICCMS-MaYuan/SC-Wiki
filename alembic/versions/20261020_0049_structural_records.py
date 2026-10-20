"""#49：与材料状态独立的论文结构资料。"""

from alembic import op
import sqlalchemy as sa

revision = "20261020_0049"
down_revision = "20261020_0142"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_structural_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paper_revision", sa.Integer(), nullable=False),
        sa.Column("record_key", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("material", sa.String(255), nullable=False),
        sa.Column("system_key", sa.String(255), nullable=False),
        sa.Column("elements", sa.JSON(), nullable=False),
        sa.Column("pressure_gpa", sa.Numeric(20, 8)),
        sa.Column("space_group", sa.String(100)),
        sa.Column("state_key", sa.String(128)),
        sa.Column("retention", sa.String(16), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "paper_id", "paper_revision", "record_key", name="uq_paper_structure_record_revision"
        ),
        sa.CheckConstraint("kind IN ('model', 'lattice', 'issue')", name="ck_paper_structure_record_kind"),
        sa.CheckConstraint(
            "retention IN ('pending', 'retained', 'excluded')", name="ck_paper_structure_record_retention"
        ),
    )
    op.create_index(
        "ix_paper_structure_record_paper", "paper_structural_records", ["paper_id", "paper_revision"]
    )
    op.create_index(
        "ix_paper_structure_record_system", "paper_structural_records", ["system_key", "retention"]
    )


def downgrade():
    op.drop_table("paper_structural_records")
