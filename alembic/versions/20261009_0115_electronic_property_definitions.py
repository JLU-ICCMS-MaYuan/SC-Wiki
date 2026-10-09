"""为 #114 发布首批电子性质定义，不改写已有物性记录。"""
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = "20261009_0115"
down_revision = "20260924_0114"
branch_labels = None
depends_on = None


def upgrade():
    table = sa.Table("form_definitions", sa.MetaData(), autoload_with=op.get_bind())
    connection = op.get_bind()
    for code in ("band_gap", "dos_fermi"):
        key = f"record.electronic_properties.{code}"
        if connection.scalar(sa.select(table.c.id).where(table.c.definition_key == key, table.c.version == 1)):
            continue
        data = dict(definition_key=key, version=1, target_kind="property_record",
                    module_code="electronic_properties", record_type="property", method_code=None,
                    property_code=code, core_schema={"type": "object"},
                    json_schema={"type": "object", "additionalProperties": True}, ui_schema={})
        checksum = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        connection.execute(table.insert().values(**data, checksum=checksum, status="published"))


def downgrade():
    # 发布后可能已被论文引用；应用回退不能删除定义。
    pass
