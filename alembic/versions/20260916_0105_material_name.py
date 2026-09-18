"""增加材料名字段。"""
from alembic import op
import sqlalchemy as sa

revision = '20260916_0105'
down_revision = '20260915_0104'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('material_states', sa.Column('material_name', sa.String(length=255), nullable=True))

def downgrade():
    op.drop_column('material_states', 'material_name')
