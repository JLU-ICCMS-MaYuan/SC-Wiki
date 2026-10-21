"""结构核对身份独立于几何摘要和重建后的数据库ID。"""
from alembic import op
import sqlalchemy as sa

revision = '20261022_0147b'
down_revision = '20261021_0147'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('structure_models', sa.Column('review_key', sa.String(64), nullable=True))


def downgrade():
    op.drop_column('structure_models', 'review_key')
