"""Tc/μ* 参数经过生产校验、SQLite 保存重读及导出的往返验证。"""
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


def record():
    return dict(record_key="tc-pairs", module_code="superconductive_properties", record_type="predicted_tc", property_code="tc",
                definition_key="record.superconductive_properties.predicted_tc.allen_dynes", definition_version=1,
                method_code="allen_dynes", name_raw="critical temperature", value_kind="range", value_min=281, value_max=311,
                canonical_unit="K", payload=dict(calculation_conditions=dict(calculation_code="QE"), parameters=dict(
                    lambda_ep=2.1, omega_log=1200, extensions=[dict(key="mu_star", value_kind="range", value_min=0.1, value_max=0.13, unit_raw="1")])) )


@pytest.mark.parametrize("value", [0, None, {"value_number": 0, "source": "table"}])
def test_optional_parameters_accept_zero_empty_and_wrapped(value):
    source = record()
    source["payload"]["parameters"]["lambda_ep"] = value
    checked = validate_record(source)
    assert checked["payload"] == source["payload"]


@pytest.mark.parametrize("value", [-1, "1e-", float("inf"), float("nan"), True])
def test_invalid_optional_parameter_is_rejected(value):
    source = record()
    source["payload"]["parameters"]["extensions"][0]["value_max"] = value
    with pytest.raises(PropertyValidationError) as error:
        validate_record(source)
    assert any(issue.field.endswith("payload.parameters.extensions.0.value_max") for issue in error.value.issues)


def test_conflicting_mu_representations_and_reversed_mu_are_rejected():
    source = record()
    source["payload"]["parameters"]["mu_star"] = 0.1
    with pytest.raises(PropertyValidationError):
        validate_record(source)
    del source["payload"]["parameters"]["mu_star"]
    source["payload"]["parameters"]["extensions"][0]["value_max"] = 0.05
    with pytest.raises(PropertyValidationError):
        validate_record(source)


def test_one_unknown_mu_endpoint_stays_unknown():
    source = record()
    source["payload"]["parameters"]["extensions"][0]["value_max"] = None
    assert validate_record(source)["payload"] == source["payload"]


def test_paired_payload_persists_reloads_and_exports():
    source = json.loads(Path(os.environ["TC_PAIRED_PAYLOAD"]).read_text()) if os.environ.get("TC_PAIRED_PAYLOAD") else record()
    original = deepcopy(source)
    seeds = json.loads((Path(__file__).parents[1] / "data/form_definitions.v1.json").read_text())

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as session:
                session.add_all([models.FormDefinition(**seed, checksum=definition_checksum(seed)) for seed in seeds])
                session.add(models.Paper(id=1, title="Tc paired fixture", year=2026, review_status="pending", content_revision=1))
                session.add(models.ChemicalSystem(id=1, paper_id=1, paper_revision=1, system_key="Sn", elements_list=["Sn"], element_count=1))
                session.add(models.Superconductor(id=1, paper_id=1, paper_revision=1, chemical_system_id=1, chemical_formula="Sn", formula_normalized="Sn", composition_key="Sn:1", display_name="Sn", elements_list=["Sn"], composition={"Sn": 1}, element_ratio={"Sn": 1}))
                session.add(models.MaterialState(id=1, state_key="paired", paper_id=1, paper_revision=1, superconductor_id=1, state_kind="theoretical", crystal_system="unknown", material_dimensionality="unknown"))
                for evidence_id in (81, 82):
                    session.add(models.PaperEvidence(id=evidence_id, paper_id=1, paper_revision=1, paper_chunk_id=1, field_path=f"parameter-{evidence_id}", quote="Tc and mu were reported together."))
                await session.flush()
                await persist_property_modules(session, paper_id=1, paper_revision=1, material_state_id=1, modules=[dict(
                    module_key="paired-module", module_code="superconductive_properties", definition_key="module.superconductive_properties", definition_version=1, records=[source])])
                await session.commit()
            async with sessions() as session:
                stored = (await session.execute(select(models.PropertyRecord))).scalar_one()
                assert stored.payload_json == original["payload"]
                exported = await session.run_sync(lambda db: build_material_state_export(db, paper_id=1, state_key="paired", user=models.User(role="admin")))
                actual = exported["property_modules"][0]["records"][0]
                assert actual["payload"] == original["payload"]
                assert (actual["value_min"], actual["value_max"]) == (original["value_min"], original["value_max"])
                assert actual["record_key"] == original["record_key"]
        finally:
            await engine.dispose()
    asyncio.run(run())
