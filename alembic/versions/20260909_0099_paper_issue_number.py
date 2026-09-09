"""为论文新增独立期号，兼容历史空值。"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0099"
down_revision = "issue90_data_integrity_repair_v1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("papers", sa.Column("issue_number", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("papers", "issue_number")
