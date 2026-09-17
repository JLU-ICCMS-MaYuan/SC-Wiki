"""将浏览器真实保存请求送入现有校验、SQLite 持久化及导出通路。"""
import asyncio
import json
import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.api.material_state_export import build_material_state_export
from backend.database import Base
from backend.ingest.form_definitions import definition_checksum
from backend.ingest.property_modules import persist_property_modules


@pytest.mark.skipif(not os.environ.get("TC_BROWSER_PAYLOADS"), reason="先运行 tc-record-browser.mjs 生成隔离请求")
def test_browser_tc_payloads_persist_and_export():
    payloads = json.loads(Path(os.environ["TC_BROWSER_PAYLOADS"]).read_text())
    assert len(payloads) >= 9
    values = [body["material_states"][1]["property_modules"][0]["records"][0] for body in payloads]
    assert any(record.get("value_number") == 0 for record in values)
    assert any(record["value_kind"] == "range" for record in values)
    seeds = json.loads((Path(__file__).parents[2] / "backend/data/form_definitions.v1.json").read_text())

    async def roundtrip():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as session:
                session.add_all([models.FormDefinition(**seed, checksum=definition_checksum(seed)) for seed in seeds])
                session.add_all([
                    models.Paper(id=1, title="隔离 Tc 布局验收", year=2026, review_status="pending", content_revision=1),
                    models.ChemicalSystem(id=1, paper_id=1, paper_revision=1, system_key="Sn", elements_list=["Sn"], element_count=1),
                    models.Superconductor(id=1, paper_id=1, paper_revision=1, chemical_system_id=1, chemical_formula="Sn", formula_normalized="Sn", composition_key="Sn:1", display_name="Sn", elements_list=["Sn"], composition={"Sn": 1}, element_ratio={"Sn": 1}),
                ])
                await session.flush()
                for index, body in enumerate(payloads):
                    for state_index, state in enumerate(body["material_states"]):
                        state_id = index * 2 + state_index + 1
                        session.add(models.MaterialState(id=state_id, state_key=f"fixture-{state_id}", paper_id=1, paper_revision=1, superconductor_id=1, state_kind="experimental", crystal_system="unknown", material_dimensionality="unknown"))
                        await session.flush()
                        # 每份请求的键在所属材料状态内唯一；完整调用现有生产持久化与校验。
                        modules = json.loads(json.dumps(state["property_modules"]))
                        for module in modules:
                            module["module_key"] += f"-{state_id}"
                            for record in module["records"]:
                                record["record_key"] += f"-{state_id}"
                        await persist_property_modules(session, paper_id=1, paper_revision=1, material_state_id=state_id, modules=modules)
                await session.commit()
            async with sessions() as session:
                for index, body in enumerate(payloads):
                    for state_index, state in enumerate(body["material_states"]):
                        state_key = f"fixture-{index * 2 + state_index + 1}"
                        output = await session.run_sync(lambda db: build_material_state_export(db, paper_id=1, state_key=state_key, user=models.User(role="admin")))
                        actual = output["property_modules"][0]["records"][0]
                        expected = state["property_modules"][0]["records"][0]
                        for field in ("value_kind", "value_number", "value_min", "value_max", "value_raw", "unit_raw", "canonical_unit"):
                            assert actual.get(field) == expected.get(field), (index, field)
                        assert actual["value_raw"] == ("2–5" if actual["value_kind"] == "range" else str(actual["value_number"]).removesuffix(".0"))
                        assert bool(actual["is_representative"]) == bool(expected.get("is_representative"))
        finally:
            await engine.dispose()

    asyncio.run(roundtrip())
