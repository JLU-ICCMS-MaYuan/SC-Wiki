"""结构优化物理目标和实际几何自由度；不改写历史科学值。"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_0181"
down_revision = "20261022_0153"
branch_labels = None
depends_on = None
NAME = "ck_material_states_structure_optimization"
OLD = "structure_optimization IN ('unknown','classical_static','sscha') AND (state_kind = 'theoretical' OR structure_optimization = 'unknown')"
NEW = "structure_optimization IN ('unknown','classical_static','quasi_harmonic','anharmonic_quantum','sscha') AND (state_kind = 'theoretical' OR structure_optimization = 'unknown')"


def upgrade():
    with op.batch_alter_table("material_states") as batch:
        batch.add_column(sa.Column("structure_optimization_details", sa.JSON(), nullable=True))
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, NEW)


def downgrade():
    # 不以回退为由删除新科学详情或改写目标；存在新数据时必须先显式处理。
    if op.get_context().as_sql:
        raise RuntimeError("结构优化详情回退必须在线核对，离线模式不能保证数据安全")
    connection = op.get_bind()
    count = connection.execute(sa.text("SELECT COUNT(*) FROM material_states WHERE structure_optimization IN ('quasi_harmonic','anharmonic_quantum') OR structure_optimization_details IS NOT NULL")).scalar()
    if count:
        raise RuntimeError("存在新结构优化目标或详情，拒绝有损回退")
    with op.batch_alter_table("material_states") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, OLD)
        batch.drop_column("structure_optimization_details")
