"""#181：隔离数据库正式上传持久化、读取、导出与迁移。"""
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from alembic.operations import Operations
from alembic.migration import MigrationContext

from backend import models
from backend.database import Base
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.scientific_drafts import persist_scientific_draft
from backend.ingest.upload_jobs import _normalize_draft
from backend.services.paper_revisions import current_draft
from backend.api.material_state_export import build_material_state_export


@pytest.mark.parametrize("objective",["unknown","classical_static","quasi_harmonic","anharmonic_quantum","sscha"])
def test_real_persistence_read_and_export_keep_objective_constraints_and_electronic_record(objective):
    async def run():
        engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        details={"method":"Reported free-energy method","electronic_method":"HF","temperature_k":0,
                 "centroids":"optimized","volume":"fixed","cell_shape":"unknown"}
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            seeds=json.loads((Path(__file__).parents[2]/"backend/data/form_definitions.v1.json").read_text())
            seeds.append({"definition_key":"record.electronic_properties.band_gap","version":1,"target_kind":"property_record",
                "module_code":"electronic_properties","record_type":"property","property_code":"band_gap",
                "core_schema":{},"json_schema":{"type":"object","additionalProperties":True},"ui_schema":{},"status":"published"})
            draft=_normalize_draft({"paper":{"title":"Isolated method scope","paper_type":"theoretical"},
              "material_states":[{"state_key":"s","material":"CaH2","material_name":"CaH2","state_kind":"theoretical",
                "structure_optimization":objective,"structure_optimization_details":details,"pressure_value_gpa":150,
                "property_modules":[{"module_key":"m","module_code":"electronic_properties","definition_key":"module.electronic_properties","definition_version":1,
                  "records":[{"record_key":"r","record_type":"property","property_code":"band_gap",
                   "definition_key":"record.electronic_properties.band_gap","definition_version":1,"name_raw":"Band gap",
                   "value_kind":"number","value_number":.48,"value_raw":"0.48","unit_raw":"eV","canonical_unit":"eV",
                   "payload":{"calculation_conditions":{"electronic_method":"HF"}}}]}]}]})
            async with sessions() as session,session.begin():
                for seed in seeds:
                    session.add(models.FormDefinition(**seed,checksum=definition_checksum(seed)))
                paper=models.Paper(id=1,title="Isolated method scope",year=2026,paper_type="theoretical",review_status="pending",content_revision=1)
                session.add(paper);await session.flush()
                await persist_scientific_draft(session,paper,deepcopy(draft))
            async with sessions() as session:
                paper=await session.get(models.Paper,1)
                restored=await session.run_sync(lambda sync:current_draft(sync,paper))
                exported=await session.run_sync(lambda sync:build_material_state_export(sync,paper_id=1,state_key="s",user=SimpleNamespace(id=7,role="admin",is_approved=True)))
                state=restored["material_states"][0]
                assert state["structure_optimization"]==("unknown" if objective=="anharmonic_quantum" else objective)
                assert "structure_optimization_details" not in state
                r=state["property_modules"][0]["records"][0]
                assert float(r["value_number"])==.48 and r["property_code"]=="band_gap"
                assert r["payload"]["calculation_conditions"]["electronic_method"]=="HF"
                assert "structure_optimization_details" not in exported["material_state"]
        finally:
            await engine.dispose()
    asyncio.run(run())


def migration():
    p=Path(__file__).parents[2]/"alembic/versions/20261029_0181_physical_method_scope.py"
    spec=importlib.util.spec_from_file_location("methods181",p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_migration_keeps_legacy_and_refuses_lossy_downgrade():
    module=migration()
    engine=sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE material_states (id INTEGER PRIMARY KEY,state_kind VARCHAR(20),structure_optimization VARCHAR(32),CONSTRAINT ck_material_states_structure_optimization CHECK (structure_optimization IN ('unknown','classical_static','sscha') AND (state_kind='theoretical' OR structure_optimization='unknown')))")
            conn.exec_driver_sql("INSERT INTO material_states VALUES(1,'theoretical','sscha')")
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
                assert conn.execute(sa.text("SELECT structure_optimization FROM material_states")).scalar()=="sscha"
                conn.exec_driver_sql("INSERT INTO material_states VALUES(2,'theoretical','quasi_harmonic','{}')")
                with pytest.raises(RuntimeError,match="有损"):
                    module.downgrade()
                assert conn.execute(sa.text("SELECT COUNT(*) FROM material_states")).scalar()==2
    finally:
        engine.dispose()
