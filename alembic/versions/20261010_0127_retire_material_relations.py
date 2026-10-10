"""#127：清理材料关系并删除论文专列。

Revision ID: 20261010_0127
Revises: 20261009_0126
"""

import hashlib
import json

from alembic import op
import sqlalchemy as sa


revision = "20261010_0127"
down_revision = "20261009_0126"
branch_labels = None
depends_on = None

_FIELD = "paper.material_relations"
_ITEM_KEY = hashlib.sha256(json.dumps(["paper", "material_relations"], ensure_ascii=False,
                                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()
_JSON_COLUMNS = {
    "scientific_upload_drafts": ("draft", "state"),
    "paper_revision_drafts": ("draft",),
    "paper_history_events": ("classification_snapshot",),
    "scientific_evidence_checks": ("result", "resolutions"),
    "scientific_evidence_sources": ("result",),
    "scientific_manual_evidence": ("before_value", "after_value", "items"),
}


def _retired_item(value):
    if not isinstance(value, dict):
        return False
    for key in ("field", "field_path", "path"):
        path = value.get(key)
        if isinstance(path, str) and (path == _FIELD or path.startswith(_FIELD + "[")):
            return True
    fields = value.get("fields")
    return isinstance(fields, list) and any(
        isinstance(path, str) and (path == _FIELD or path.startswith(_FIELD + "[")) for path in fields
    )


def _strip(value):
    """只移除退役字段及其独立核对项，保留同一快照的其他内容。"""
    if isinstance(value, dict):
        return {key: _strip(item) for key, item in value.items()
                if key not in {"material_relations", _FIELD} and not key.startswith(_FIELD + "[")
                and not _retired_item(item)}
    if isinstance(value, list):
        return [_strip(item) for item in value if not _retired_item(item)]
    return value


def _scrub_json_columns(bind, inspector, table_name, columns):
    if not inspector.has_table(table_name):
        return
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    columns = [name for name in columns if name in existing]
    if not columns:
        return
    table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
    primary = list(table.primary_key.columns)
    if not primary:
        raise RuntimeError(f"{table_name} 缺少主键，拒绝执行有损清理")
    rows = bind.execute(sa.select(*primary, *(table.c[name] for name in columns))).mappings().all()
    for row in rows:
        updates = {}
        for name in columns:
            value = row[name]
            cleaned = _strip(value)
            if cleaned != value:
                updates[name] = cleaned
        if updates:
            where = sa.and_(*(column == row[column.name] for column in primary))
            bind.execute(sa.update(table).where(where).values(**updates))


def _delete_rows(bind, inspector, table_name, *, path_column=None, result_column=None):
    if not inspector.has_table(table_name):
        return
    table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
    if "item_key" in table.c:
        bind.execute(sa.delete(table).where(table.c.item_key == _ITEM_KEY))
    if path_column and path_column in table.c:
        bind.execute(sa.delete(table).where(sa.or_(table.c[path_column] == _FIELD,
            table.c[path_column].like(_FIELD + "[%"))))
    if result_column and result_column in table.c:
        keys = [row["id"] for row in bind.execute(sa.select(table.c.id, table.c[result_column])).mappings()
                if _retired_item(row[result_column])]
        if keys:
            bind.execute(sa.delete(table).where(table.c.id.in_(keys)))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("papers"):
        raise RuntimeError("papers 表不存在，拒绝执行材料关系退役迁移")
    _delete_rows(bind, inspector, "paper_evidences", path_column="field_path")
    _delete_rows(bind, inspector, "scientific_evidence_sources", path_column="field_path")
    _delete_rows(bind, inspector, "scientific_evidence_checks", result_column="result")
    _delete_rows(bind, inspector, "scientific_manual_evidence")
    for table_name, columns in _JSON_COLUMNS.items():
        _scrub_json_columns(bind, inspector, table_name, columns)
    if "material_relations" in {column["name"] for column in inspector.get_columns("papers")}:
        with op.batch_alter_table("papers") as batch:
            batch.drop_column("material_relations")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "material_relations" not in {column["name"] for column in inspector.get_columns("papers")}:
        with op.batch_alter_table("papers") as batch:
            batch.add_column(sa.Column("material_relations", sa.JSON(), nullable=True))
