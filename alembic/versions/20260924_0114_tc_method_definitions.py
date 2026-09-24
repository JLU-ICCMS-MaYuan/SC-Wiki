"""补齐 #114 直接领域提取所需的已有 Tc 方法定义，不覆盖已发布版本。"""
from copy import deepcopy
import hashlib
import json

from alembic import op
import sqlalchemy as sa

revision = "20260924_0114"
down_revision = "20260923_0114"
branch_labels = None
depends_on = None


def upgrade():
    table = sa.Table("form_definitions", sa.MetaData(), autoload_with=op.get_bind())
    connection = op.get_bind()
    groups = {
        "predicted_tc": ("calculation_conditions", ["mcmillan", "allen_dynes", "isotropic_eliashberg",
            "anisotropic_eliashberg", "scdft", "other", "unknown"]),
        "measured_tc": ("experimental_conditions", ["resistivity", "magnetic_susceptibility", "specific_heat", "other", "unknown"]),
    }
    for kind, (condition, methods) in groups.items():
        for method in methods:
            key = f"record.superconductive_properties.{kind}.{method}"
            if connection.scalar(sa.select(table.c.id).where(table.c.definition_key == key, table.c.version == 1)):
                continue
            properties = {condition: {"type": "object"}}
            if kind == "predicted_tc":
                properties["parameters"] = {"type": "object"}
            data = dict(definition_key=key, version=1, target_kind="property_record",
                module_code="superconductive_properties", record_type=kind, method_code=method,
                property_code="tc", core_schema={"type": "object"},
                json_schema={"type": "object", "properties": properties, "required": [condition], "additionalProperties": True},
                ui_schema={})
            checksum = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            connection.execute(table.insert().values(**deepcopy(data), checksum=checksum, status="published"))


def downgrade():
    # 已发布目录可能已有用户数据引用；回退应用保留新增定义，禁止删掉历史记录的契约。
    pass
