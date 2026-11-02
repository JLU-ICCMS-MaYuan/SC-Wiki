"""#203：固定字段契约，显式转换当前数据并退役压力辅助列。"""
from alembic import op
import sqlalchemy as sa

revision = '20261102_0203'
down_revision = '20261102_0203_merge'
branch_labels = None
depends_on = None


def upgrade():
    from backend.services.form_contract_migration import require_explicit_migration
    from alembic import op as migration_op
    require_explicit_migration(migration_op.get_bind())
    from backend.services.form_contract_migration import prepare_changes, apply_changes, publish_definitions
    bind = op.get_bind()
    changes = prepare_changes(bind)
    columns = {item['name'] for item in sa.inspect(bind).get_columns('material_states')}
    constraints = {item['name'] for item in sa.inspect(bind).get_check_constraints('material_states')}
    rows = bind.execute(sa.text('SELECT pressure_value_gpa,pressure_min_gpa,pressure_max_gpa FROM material_states')).all() if 'pressure_min_gpa' in columns else []
    for value, lower, upper in rows:
        if (lower is not None or upper is not None) and (value is None or lower is not None and value < lower or upper is not None and value > upper):
            raise ValueError('存在不能无损迁移的压力范围，迁移中止')
    # 所有内容冲突在DDL之前预检；MySQL DDL恢复依靠事前备份。
    publish_definitions(bind)
    apply_changes(bind, changes)
    with op.batch_alter_table('material_states') as batch:
        if 'ck_material_states_pressure_range' in constraints:
            batch.drop_constraint('ck_material_states_pressure_range', type_='check')
        if 'ck_material_states_nonnegative' in constraints:
            batch.drop_constraint('ck_material_states_nonnegative', type_='check')
        for key in ('pressure_min_gpa', 'pressure_max_gpa', 'pressure_raw', 'pressure_unit_raw'):
            if key in columns:
                batch.drop_column(key)
        batch.create_check_constraint('ck_material_states_nonnegative',
            '(pressure_value_gpa IS NULL OR pressure_value_gpa >= 0) AND '
            '(temperature_value_k IS NULL OR temperature_value_k >= 0) AND '
            '(magnetic_field_t IS NULL OR magnetic_field_t >= 0)')


def downgrade():
    raise RuntimeError('退役字段不能凭空恢复；请按已验证的迁移前备份恢复')
