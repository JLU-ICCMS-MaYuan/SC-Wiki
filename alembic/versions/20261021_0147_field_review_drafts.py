"""管理员逐字段编辑暂存，不改正式数据。"""
from alembic import op
import sqlalchemy as sa

revision = '20261021_0147'
down_revision = '20261020_0143b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('scientific_review_drafts',
        sa.Column('paper_id', sa.Integer(), sa.ForeignKey('papers.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('base_revision', sa.Integer(), nullable=False),
        sa.Column('base_fingerprint', sa.String(64), nullable=False),
        sa.Column('draft', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table('scientific_review_drafts')
