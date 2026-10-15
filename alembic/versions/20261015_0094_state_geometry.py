"""#94：材料状态核处理、退役 mixed 和单份规范几何，合并既有双头。"""
from alembic import op
import sqlalchemy as sa
import json

revision = "20261015_0094"
down_revision = ("20260914_0052", "20261014_0137")
branch_labels = None
depends_on = None


def preflight(bind):
    mixed = bind.scalar(sa.text("SELECT COUNT(*) FROM material_states WHERE state_kind NOT IN ('theoretical','experimental','unknown')"))
    multiple = bind.scalar(sa.text("SELECT COUNT(*) FROM (SELECT material_state_id FROM structure_models GROUP BY material_state_id HAVING COUNT(*) > 1) conflicts"))
    treatment = bind.scalar(sa.text("SELECT COUNT(*) FROM structure_models WHERE nuclear_treatment <> 'unknown'"))
    drafts = 0
    tables = set(sa.inspect(bind).get_table_names())
    for table in ("scientific_upload_drafts", "paper_revision_drafts"):
        if table not in tables:
            continue
        for raw in bind.execute(sa.text(f"SELECT draft FROM {table} WHERE draft IS NOT NULL")).scalars():
            draft = json.loads(raw) if isinstance(raw, str) else raw
            from backend.ingest.material_state_contract import state_metadata, validate_single_geometries
            try:
                for state in draft.get("material_states") or []:
                    state_metadata(state)
                validate_single_geometries(draft)
            except ValueError:
                drafts += 1
    if mixed or multiple or drafts or treatment:
        raise RuntimeError(f"#94 迁移中止：非法状态={mixed}，多几何状态={multiple}，待处理草稿={drafts}，待明确结构核处理={treatment}；请先明确处理这些数据，不自动删除或映射")


def upgrade():
    preflight(op.get_bind())
    with op.batch_alter_table("material_states") as batch:
        batch.add_column(sa.Column("structure_optimization", sa.String(32), nullable=False, server_default="unknown"))
        batch.drop_constraint("ck_material_states_kind", type_="check")
        batch.create_check_constraint("ck_material_states_kind", "state_kind IN ('theoretical','experimental','unknown')")
        batch.create_check_constraint("ck_material_states_structure_optimization", "structure_optimization IN ('unknown','classical_static','sscha') AND (state_kind = 'theoretical' OR structure_optimization = 'unknown')")
    with op.batch_alter_table("structure_models") as batch:
        batch.create_unique_constraint("uq_structure_models_single_geometry", ["material_state_id"])


def downgrade():
    with op.batch_alter_table("structure_models") as batch:
        batch.drop_constraint("uq_structure_models_single_geometry", type_="unique")
    with op.batch_alter_table("material_states") as batch:
        batch.drop_constraint("ck_material_states_structure_optimization", type_="check")
        batch.drop_constraint("ck_material_states_kind", type_="check")
        batch.create_check_constraint("ck_material_states_kind", "state_kind IN ('theoretical','experimental','mixed','unknown')")
        batch.drop_column("structure_optimization")
