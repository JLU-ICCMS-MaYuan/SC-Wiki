"""#127：退役迁移必须只删除材料关系及其独立证据。"""

import hashlib
import importlib.util
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


MIGRATION = Path(__file__).resolve().parents[2] / "alembic/versions/20261010_0127_retire_material_relations.py"


def _migration():
    spec = importlib.util.spec_from_file_location("retire_material_relations_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retirement_scrubs_only_material_relation_values():
    metadata = sa.MetaData()
    papers = sa.Table("papers", metadata, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("title", sa.String), sa.Column("material_relations", sa.JSON))
    uploads = sa.Table("scientific_upload_drafts", metadata, sa.Column("task_id", sa.String, primary_key=True),
                       sa.Column("draft", sa.JSON), sa.Column("state", sa.JSON))
    histories = sa.Table("paper_history_events", metadata, sa.Column("id", sa.Integer, primary_key=True),
                         sa.Column("classification_snapshot", sa.JSON))
    checks = sa.Table("scientific_evidence_checks", metadata, sa.Column("id", sa.Integer, primary_key=True),
                      sa.Column("item_key", sa.String), sa.Column("result", sa.JSON), sa.Column("resolutions", sa.JSON))
    sources = sa.Table("scientific_evidence_sources", metadata, sa.Column("id", sa.Integer, primary_key=True),
                       sa.Column("item_key", sa.String), sa.Column("field_path", sa.String), sa.Column("result", sa.JSON))
    manual = sa.Table("scientific_manual_evidence", metadata, sa.Column("id", sa.String, primary_key=True),
                      sa.Column("item_key", sa.String), sa.Column("before_value", sa.JSON),
                      sa.Column("after_value", sa.JSON), sa.Column("items", sa.JSON))
    evidence = sa.Table("paper_evidences", metadata, sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("field_path", sa.String))
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    retired_key = hashlib.sha256(json.dumps(["paper", "material_relations"], ensure_ascii=False,
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with engine.begin() as connection:
        connection.execute(papers.insert(), {"id": 1, "title": "kept", "material_relations": [
            {"material": "(H2S)2H2", "relation": "investigates"},
            {"material": "(H2S)2H2", "relation": "predicts"}]})
        connection.execute(uploads.insert(), {"task_id": "a", "draft": {"paper": {
            "title": "kept", "material_relations": [{"material": "Sn"}]}}, "state": {"status": "ready"}})
        connection.execute(histories.insert(), {"id": 1, "classification_snapshot": {
            "revision_submission": {"paper": {"title": "kept", "material_relations": ["Sn"]}},
            "manual_edit_baseline": {"paper.material_relations": ["Sn"], "paper.title": "kept"}}})
        connection.execute(checks.insert(), [
            {"id": 1, "item_key": retired_key, "result": {"field": "paper.material_relations"}, "resolutions": {}},
            {"id": 2, "item_key": "other", "result": {"field": "paper.title", "current_value": "kept"}, "resolutions": {}},
        ])
        connection.execute(sources.insert(), [
            {"id": 1, "item_key": retired_key, "field_path": "paper.material_relations", "result": {}},
            {"id": 2, "item_key": "other", "field_path": "paper.title", "result": {"quote": "kept"}},
        ])
        connection.execute(manual.insert(), [
            {"id": "retired", "item_key": retired_key, "before_value": ["Sn"], "after_value": [], "items": []},
            {"id": "other", "item_key": "other", "before_value": "old", "after_value": "kept", "items": []},
        ])
        connection.execute(evidence.insert(), [
            {"id": 1, "field_path": "paper.material_relations[0]"},
            {"id": 2, "field_path": "paper.title"},
        ])
        migration = _migration()
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert "material_relations" not in {column["name"] for column in sa.inspect(connection).get_columns("papers")}
        assert connection.execute(sa.select(uploads.c.draft)).scalar_one() == {"paper": {"title": "kept"}}
        history = connection.execute(sa.select(histories.c.classification_snapshot)).scalar_one()
        assert history["revision_submission"]["paper"] == {"title": "kept"}
        assert history["manual_edit_baseline"] == {"paper.title": "kept"}
        for table in (checks, sources, manual, evidence):
            assert connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() == 1
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert "material_relations" in {column["name"] for column in sa.inspect(connection).get_columns("papers")}
        assert connection.execute(sa.text("SELECT material_relations FROM papers WHERE id=1")).scalar_one() is None
