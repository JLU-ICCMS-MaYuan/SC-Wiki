"""允许只有材料名的状态不关联化学式实体。"""
from alembic import op
import sqlalchemy as sa

revision = '20260916_0106'
down_revision = '20260916_0105'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('material_states') as batch:
        batch.alter_column('superconductor_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM material_states WHERE superconductor_id IS NULL LIMIT 1')).first():
        raise RuntimeError('存在无化学式材料状态，不能恢复必填关联；请先显式处理这些记录')
    with op.batch_alter_table('material_states') as batch:
        batch.alter_column('superconductor_id', existing_type=sa.Integer(), nullable=False)
