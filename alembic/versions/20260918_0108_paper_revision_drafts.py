"""上传者的持久返修草稿，不改变正式论文的审核状态。"""
from alembic import op
import sqlalchemy as sa

revision = '20260918_0108'
down_revision = '20260917_0107'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('paper_revision_drafts',
        sa.Column('paper_id', sa.Integer(), sa.ForeignKey('papers.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('revision_id', sa.String(32), nullable=False),
        sa.Column('base_revision', sa.Integer(), nullable=False),
        sa.Column('base_fingerprint', sa.String(64), nullable=False),
        sa.Column('draft_version', sa.Integer(), nullable=False),
        sa.Column('draft', sa.JSON()),
        sa.Column('submitted_revision', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('revision_id', name='uq_paper_revision_draft_id'))


def downgrade():
    op.drop_table('paper_revision_drafts')
