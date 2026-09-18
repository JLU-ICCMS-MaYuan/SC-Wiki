"""补齐非超导模块的通用物性录入定义，不覆盖已有已发布版本。"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = '20260914_0052'
down_revision = '20260911_0103'
branch_labels = None
depends_on = None


def upgrade():
    table = sa.table('form_definitions',
        sa.column('definition_key', sa.String()), sa.column('version', sa.Integer()),
        sa.column('target_kind', sa.String()), sa.column('module_code', sa.String()),
        sa.column('record_type', sa.String()), sa.column('method_code', sa.String()),
        sa.column('property_code', sa.String()), sa.column('core_schema', sa.JSON()),
        sa.column('json_schema', sa.JSON()), sa.column('ui_schema', sa.JSON()),
        sa.column('status', sa.String()), sa.column('checksum', sa.String()))
    bind = op.get_bind()
    for module in ('dynamical_properties', 'thermodynamical_properties', 'electronic_properties'):
        key = f'record.{module}.custom'
        if bind.execute(sa.select(table.c.definition_key).where(table.c.definition_key == key, table.c.version == 1)).first():
            continue
        content = dict(definition_key=key, version=1, target_kind='property_record', module_code=module,
                       record_type='property', method_code=None, property_code='custom',
                       core_schema={'type': 'object'}, json_schema={'type': 'object', 'additionalProperties': True}, ui_schema={})
        checksum = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        bind.execute(table.insert().values(**content, status='published', checksum=checksum))


def downgrade():
    # 已发布定义可能已被科研记录引用，降级也保留兼容定义。
    pass
