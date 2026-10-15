"""稳定性判据隔离、服务器校验和真实数据库/导出往返。"""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.api.material_state_export import build_material_state_export
from backend.database import Base
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.property_modules import PropertyValidationError, persist_property_modules, validate_record


def case(**patch):
    return dict(stability="unknown", above_hull=None, unit="eV/atom", temperature_k=0, zpe="unspecified", decomposition_path="", source_description="", **patch)


def record():
    enthalpy = case()
    enthalpy.update(stability="unstable", above_hull=0.025, decomposition_path="A + B", source_description="Table 2")
    gibbs = case()
    gibbs.update(stability="unstable", temperature_k=500, above_hull=0, zpe="included")
    return dict(record_key="stability", module_code="thermodynamical_properties", record_type="property", property_code="custom", custom_property_key="hull-stability",
                definition_key="record.thermodynamical_properties.custom", definition_version=1, name_raw="thermodynamic stability", value_kind="text", value_raw="不稳定", value_text="不稳定",
                payload=dict(thermodynamic_stability=dict(version=1, basis="formation_enthalpy", cases=dict(formation_enthalpy=enthalpy, formation_gibbs=gibbs))))


@pytest.mark.parametrize("field,value", [("above_hull", -1), ("above_hull", float("nan")), ("above_hull", True), ("temperature_k", 300), ("temperature_k", False), ("zpe", "unknown"), ("unit", "eV"), ("stability", "yes"), ("source_description", 5)])
def test_rejects_invalid_case(field, value):
    item = record()
    item["payload"]["thermodynamic_stability"]["cases"]["formation_enthalpy"][field] = value
    with pytest.raises(PropertyValidationError) as error:
        validate_record(item)
    assert any(issue.field.endswith(field) for issue in error.value.issues)


def test_unknown_is_not_zero_and_summary_cannot_disagree():
    item = record()
    value = item["payload"]["thermodynamic_stability"]
    value["basis"] = "unspecified"
    value["cases"]["unspecified"] = case()
    value["cases"]["unspecified"]["temperature_k"] = None
    item.update(value_raw="未判定", value_text="未判定")
    assert validate_record(item)["payload"] == item["payload"]
    item["value_text"] = "稳定"
    with pytest.raises(PropertyValidationError):
        validate_record(item)


@pytest.mark.parametrize("field,value", [("basis", "other"), ("version", True), ("cases", []), ("cases", {"formation_enthalpy": []})])
def test_rejects_invalid_contract(field, value):
    item = record()
    item["payload"]["thermodynamic_stability"][field] = value
    with pytest.raises(PropertyValidationError):
        validate_record(item)


def test_extension_invalid_text_cannot_be_saved_as_unknown():
    item = record()
    item["payload"]["calculation_conditions"] = dict(extensions=[dict(name_raw="cutoff", value_kind="number", value_number=None, value_raw="1e-")])
    with pytest.raises(PropertyValidationError) as error:
        validate_record(item)
    assert error.value.issues[0].field.endswith("extensions.0.value_raw")


def test_cases_persist_reload_and_export_without_migration():
    original = record()
    if os.environ.get("PROPERTY_BROWSER_PAYLOADS"):
        requests = json.loads(Path(os.environ["PROPERTY_BROWSER_PAYLOADS"]).read_text())
        for request in requests:
            for state in request["material_states"]:
                for module in state["property_modules"]:
                    for item in module["records"]:
                        validate_record(item)
        original = next(item for module in requests[-1]["material_states"][0]["property_modules"] for item in module["records"] if "thermodynamic_stability" in item.get("payload", {}))
    seeds = json.loads((Path(__file__).parents[1] / "data/form_definitions.v1.json").read_text())

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as session:
                session.add_all([models.FormDefinition(**seed, checksum=definition_checksum(seed)) for seed in seeds])
                session.add(models.Paper(id=1, title="Stability fixture", year=2026, review_status="pending", content_revision=1))
                session.add(models.ChemicalSystem(id=1, paper_id=1, paper_revision=1, system_key="Sn", elements_list=["Sn"], element_count=1))
                session.add(models.Superconductor(id=1, paper_id=1, paper_revision=1, chemical_system_id=1, chemical_formula="Sn", formula_normalized="Sn", composition_key="Sn:1", display_name="Sn", elements_list=["Sn"], composition={"Sn": 1}, element_ratio={"Sn": 1}))
                session.add(models.MaterialState(id=1, state_key="hull", paper_id=1, paper_revision=1, superconductor_id=1, state_kind="theoretical", crystal_system="unknown", material_dimensionality="unknown", pressure_value_gpa=150))
                await session.flush()
                await persist_property_modules(session, paper_id=1, paper_revision=1, material_state_id=1, modules=[dict(module_key="thermo", module_code="thermodynamical_properties", definition_key="module.thermodynamical_properties", definition_version=1, records=[deepcopy(original)])])
                await session.commit()
            async with sessions() as session:
                stored = (await session.execute(select(models.PropertyRecord))).scalar_one()
                assert stored.payload_json == original["payload"]
                exported = await session.run_sync(lambda db: build_material_state_export(db, paper_id=1, state_key="hull", user=models.User(role="admin")))
                actual = exported["property_modules"][0]["records"][0]
                assert actual["payload"] == original["payload"]
                assert actual["value_text"] == "不稳定"
        finally:
            await engine.dispose()
    asyncio.run(run())
