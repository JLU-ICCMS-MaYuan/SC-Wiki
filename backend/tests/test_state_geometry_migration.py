"""#94 迁移的拒绝边界和无损升级/降级。全部使用内存 SQLite。"""
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.operations import Operations
from alembic.migration import MigrationContext


def migration():
    path = Path(__file__).parents[2] / 'alembic/versions/20261015_0094_state_geometry.py'
    spec = importlib.util.spec_from_file_location('state_geometry_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def legacy(connection):
    connection.execute(text("CREATE TABLE material_states (id INTEGER PRIMARY KEY, state_kind VARCHAR(20) NOT NULL, CONSTRAINT ck_material_states_kind CHECK (state_kind IN ('theoretical','experimental','mixed','unknown')))"))
    connection.execute(text("CREATE TABLE structure_models (id INTEGER PRIMARY KEY, material_state_id INTEGER, nuclear_treatment VARCHAR(32) NOT NULL DEFAULT 'unknown')"))
    connection.execute(text("CREATE TABLE scientific_upload_drafts (draft TEXT)"))
    connection.execute(text("INSERT INTO material_states VALUES (1,'theoretical')"))


@pytest.mark.parametrize('conflict', ['mixed', 'multiple', 'draft', 'treatment'])
def test_preflight_rejects_before_any_schema_change(conflict):
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        legacy(conn)
        if conflict == 'mixed':
            conn.execute(text("UPDATE material_states SET state_kind='mixed'"))
        elif conflict == 'multiple':
            conn.execute(text("INSERT INTO structure_models(id,material_state_id) VALUES (1,1),(2,1)"))
        elif conflict == 'treatment':
            conn.execute(text("INSERT INTO structure_models VALUES (1,1,'anharmonic_quantum')"))
        else:
            conn.execute(text("INSERT INTO scientific_upload_drafts VALUES (:draft)"), {'draft': '{"material_states":[{"state_kind":"mixed"}]}'})
        module = migration()
        module.op = Operations(MigrationContext.configure(conn))
        with pytest.raises(RuntimeError, match='迁移中止'):
            module.upgrade()
        assert 'structure_optimization' not in {c['name'] for c in inspect(conn).get_columns('material_states')}
        assert conn.scalar(text('SELECT COUNT(*) FROM material_states')) == 1


def test_upgrade_and_downgrade_keep_rows_and_validate_constraints():
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        legacy(conn)
        module = migration()
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert conn.scalar(text('SELECT structure_optimization FROM material_states')) == 'unknown'
        conn.execute(text("UPDATE material_states SET structure_optimization='sscha'"))
        conn.execute(text("INSERT INTO structure_models(id,material_state_id) VALUES (1,1)"))
        assert 'uq_structure_models_single_geometry' in {c['name'] for c in inspect(conn).get_unique_constraints('structure_models')}
        module.downgrade()
        assert 'structure_optimization' not in {c['name'] for c in inspect(conn).get_columns('material_states')}
        assert conn.scalar(text('SELECT COUNT(*) FROM structure_models')) == 1
