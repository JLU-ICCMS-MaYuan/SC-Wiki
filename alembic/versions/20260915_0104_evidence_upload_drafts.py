"""保留已核对上传草稿，防止运行缓存丢失造成结果无法恢复。"""
from alembic import op
import sqlalchemy as sa

revision = '20260915_0104'
down_revision = '20260915_0103'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('scientific_upload_drafts',
        sa.Column('task_id', sa.String(64), primary_key=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('draft', sa.JSON(), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table('scientific_upload_drafts')
