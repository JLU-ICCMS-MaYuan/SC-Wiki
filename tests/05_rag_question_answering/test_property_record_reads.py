"""RAG 必须在旧物性表不存在时读取当前已批准记录。"""

import asyncio
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import insert, inspect, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models import (
    ChemicalSystem, FormDefinition, MaterialState, Paper, PaperChunk,
    PropertyModule, PropertyRecord, Superconductor,
)
from backend.rag.tools import mysql as properties
from backend.rag.search import sql_search


@pytest_asyncio.fixture
async def records_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'records.db'}")
    tables = [Paper, ChemicalSystem, Superconductor, MaterialState,
              FormDefinition, PropertyModule, PropertyRecord, PaperChunk]
    async with engine.begin() as conn:
        for model in tables:
            await conn.run_sync(model.__table__.create)
        names = await conn.run_sync(lambda connection: inspect(connection).get_table_names())
        assert "superconductor_properties" not in names
        assert "key_properties" not in names
        for pid, status, revision, approved in [
            (1, "approved", 2, 2), (2, "pending", 1, None),
            (3, "pending", 2, None), (4, "approved", 1, 1),
        ]:
            await conn.execute(insert(Paper).values(
                id=pid, title=f"论文 {pid}", year=2026,
                review_status=status, content_revision=revision, approved_revision=approved,
            ))
            await conn.execute(insert(ChemicalSystem).values(
                id=pid, paper_id=pid, paper_revision=revision, system_key="H-La",
                elements_list=["H", "La"], element_count=2,
            ))
            await conn.execute(insert(Superconductor).values(
                id=pid, paper_id=pid, paper_revision=revision, chemical_system_id=pid,
                chemical_formula="LaH10", formula_normalized="H10La", composition_key=f"c{pid}",
                display_name="LaH10", elements_list=["H", "La"],
                composition={"H": 10, "La": 1}, element_ratio={"H": 10, "La": 1},
            ))
            await conn.execute(insert(MaterialState).values(
                id=pid, state_key=f"s{pid}", paper_id=pid, paper_revision=revision,
                superconductor_id=pid, pressure_value_gpa=150, temperature_value_k=20,
                state_kind="theoretical",
            ))
            await conn.execute(insert(PropertyModule).values(
                id=pid, module_key=f"m{pid}", paper_id=pid, paper_revision=revision,
                material_state_id=pid, module_code="superconductive_properties",
            ))
        await conn.execute(insert(FormDefinition).values(
            id=1, definition_key="test", version=1, target_kind="property_record",
            module_code="superconductive_properties", checksum="test",
        ))

        async def record(rid, pid=1, **overrides):
            revision = 2 if pid in (1, 3) else 1
            values = dict(
                id=rid, record_key=f"r{rid}", paper_id=pid, paper_revision=revision,
                material_state_id=pid, module_id=pid, record_type="predicted_tc",
                property_code="tc", definition_id=1, definition_key="test", definition_version=1,
                name_raw="临界温度", value_kind="number", value_raw="250", value_number=250,
                unit_raw="K", canonical_unit="K", method_code="allen_dynes",
                payload_json={"calculation_conditions": {"software": "QE"},
                              "parameters": {"lambda": 2.2}},
                source_fingerprint=f"f{rid}", record_checksum=f"c{rid}",
            )
            values.update(overrides)
            await conn.execute(insert(PropertyRecord).values(**values))

        await record(1)
        await record(2, value_kind="range", value_number=None,
                     value_min=180, value_max=220, value_raw="180–220")
        for rid, pid in [(3, 2), (4, 3), (5, 4)]:
            await record(rid, pid=pid, value_number=300, value_raw="300")
        await record(6, paper_revision=1, value_number=999)
        await record(7, record_type="property", property_code="electron_phonon_coupling",
                     name_raw="电声耦合", value_number=2.5, value_raw="2.5", unit_raw=None,
                     canonical_unit=None, method_code=None, payload_json={})
        await record(8, record_type="property", property_code="custom", custom_property_key="note",
                     name_raw="样品外观", value_kind="text", value_number=None, value_text="黑色",
                     value_raw="黑色", unit_raw=None, canonical_unit=None, payload_json={}, method_code=None)
        await record(9, record_type="property", property_code="custom", custom_property_key="flag",
                     name_raw="磁性", value_kind="boolean", value_number=None, value_boolean=False,
                     value_raw="false", unit_raw=None, canonical_unit=None, payload_json={}, method_code=None)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(properties, "async_session_factory", factory)
    import backend.rag.database as rag_database
    monkeypatch.setattr(rag_database, "async_session_factory", factory)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_existing_property_query_uses_current_schema(records_db):
    rows = await properties.search_property_records("Tc", operator=">", value="200")
    assert {row["id"] for row in rows} == {1, 2, 5}
    assert all(row["paper_id"] in (1, 4) for row in rows)
    first = next(row for row in rows if row["id"] == 1)
    assert first["pressure_gpa"] == 150
    assert first["payload"]["parameters"]["lambda"] == 2.2
    assert first["paper_revision"] == 2


@pytest.mark.asyncio
async def test_all_search_modes_and_detail_share_records(records_db, monkeypatch):
    from backend.rag import service
    monkeypatch.setattr(service, "_ensure_data_available", lambda: None)
    async with records_db() as session:
        modes = [
            await sql_search.search_by_formula(session, "LaH10"),
            await sql_search.search_by_elements_exact(session, ["La", "H"]),
            await sql_search.search_by_elements_combination(session, ["La", "H"]),
            await sql_search.search_by_elements_contained(session, ["La"]),
        ]
    for rows in modes:
        assert {row["id"] for row in rows} == {1, 4}
        one = next(row for row in rows if row["id"] == 1)
        assert {p["id"] for p in one["properties"]} == {1, 2, 7, 8, 9}
        assert one["composition"] == {"H": 10, "La": 1}
    detail = await service.superconductor_detail(1)
    assert detail["properties"] == next(row for row in modes[0] if row["id"] == 1)["properties"]
    for hidden in (2, 3):
        with pytest.raises(service.RagNotFoundError):
            await service.superconductor_detail(hidden)


@pytest.mark.asyncio
async def test_property_types_pressure_and_invalid_filters(records_db):
    search = properties.search_property_records
    rows = await search("压力", operator="=", value="150")
    assert {row["id"] for row in rows} == {1, 2, 5, 7, 8, 9}
    assert len(await search("lambda", operator=">", value="2")) == 1
    assert (await search("样品外观"))[0]["value"] == "黑色"
    assert (await search("磁性"))[0]["value"] is False
    assert not await search("样品外观", operator=">", value="0")
    for operator, value in [("!=", "1"), (">", "nan"), (">", "bad")]:
        with pytest.raises(ValueError):
            await search("tc", operator=operator, value=value)


@pytest.mark.asyncio
async def test_real_agent_tool_and_material_tool(records_db):
    from backend.rag.agent.tools import query_properties, material_info
    result = await query_properties.ainvoke({"predicate": "Tc", "condition": ">=200", "material": "LaH10"})
    assert {row["id"] for row in json.loads(result)} == {1, 2, 5}
    invalid = await query_properties.ainvoke({"predicate": "Tc", "condition": "nonsense"})
    assert "条件" in invalid and "失败" in invalid
    material = json.loads(await material_info.ainvoke({"formula": "LaH10"}))
    assert {row["id"] for row in material["properties"]} == {1, 2, 5, 7, 8, 9}


@pytest.mark.asyncio
async def test_stats_without_legacy_tables(records_db, monkeypatch):
    from backend.rag import service, vectordb
    monkeypatch.setattr(service, "_ensure_data_available", lambda: None)
    monkeypatch.setattr(vectordb, "collection_stats", lambda: {"count": 0})
    counts = await service.stats()
    assert counts["records"] == 6
    assert counts["papers"] == 2
    assert counts["superconductors"] == 2


@pytest.mark.asyncio
async def test_named_material_without_formula_and_zero_value(records_db):
    async with records_db.begin() as session:
        # 兼容主干仍要求材料行，以及工作区后续迁移允许状态独立命名的两种结构。
        material_id = None if MaterialState.__table__.c.superconductor_id.nullable else 1
        await session.execute(update(MaterialState).where(MaterialState.id == 1).values(
            superconductor_id=material_id, material_name="未知样品", pressure_value_gpa=0,
        ))
        await session.execute(update(Superconductor).where(Superconductor.id == 1).values(chemical_formula=""))
        await session.execute(update(PropertyRecord).where(PropertyRecord.id == 7).values(value_number=0))
    rows = await properties.search_property_records(material="未知样品")
    assert {row["id"] for row in rows} == {1, 2, 7, 8, 9}
    assert all(row["material"] == "未知样品" and not row["chemical_formula"] for row in rows)
    assert (await properties.search_property_records("lambda", "=", "0"))[0]["id"] == 7


@pytest.mark.asyncio
async def test_revision_change_and_database_errors_are_not_empty_results(records_db, monkeypatch):
    from backend.rag.agent.tools import query_properties
    async with records_db.begin() as session:
        await session.execute(update(Paper).where(Paper.id == 1).values(
            content_revision=3, approved_revision=None, review_status="pending",
        ))
    assert {r["paper_id"] for r in await properties.search_property_records("tc")} == {4}

    async def unavailable(*args, **kwargs):
        raise RuntimeError("database detail must not leak")
    monkeypatch.setattr(properties, "search_property_records", unavailable)
    result = await query_properties.ainvoke({"predicate": "Tc"})
    assert "查询失败" in result
    assert "未找到" not in result and "detail must not leak" not in result


@pytest.mark.asyncio
async def test_core_engine_retains_independent_conditions(records_db):
    from backend.rag.core import engine
    from backend.rag.core.prompts import build_fusion_prompt
    intent = {"intent": "property_query", "predicates": ["Tc"], "subjects": ["LaH10"]}
    rows = await engine._query_intent_records(intent)
    assert {row["id"] for row in rows} == {1, 2, 5}
    prompt = build_fusion_prompt("Tc 是多少？", kg_results=rows)
    assert "180.0–220.0" in prompt
    assert "calculation_conditions" in prompt and "lambda" in prompt
    assert "[PID_1]" in prompt and "[PID_4]" in prompt


@pytest.mark.asyncio
async def test_mentor_executes_real_tool_before_answer(records_db, monkeypatch):
    from langchain_core.messages import AIMessage, ToolMessage
    from backend.rag import service
    from backend.rag.agent import mentor
    tool_outputs = []

    class Model:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            outputs = [m for m in messages if isinstance(m, ToolMessage)]
            if outputs:
                tool_outputs.append(json.loads(outputs[-1].content))
                return AIMessage(content="done")
            return AIMessage(content="", tool_calls=[{
                "id": "properties", "name": "query_properties",
                "args": {"predicate": "Tc", "condition": ">200"},
            }])

    monkeypatch.setattr(mentor, "_build_llm", lambda: Model())
    monkeypatch.setattr(service, "_ensure_chat_available", lambda: None)
    monkeypatch.setattr(service, "get_llm_config", lambda: SimpleNamespace(provider="test", model="test"))
    result = await service.chat("哪些材料的 Tc 大于 200 K？")
    assert result["answer"] == "done"
    assert tool_outputs and all({r["id"] for r in rows} == {1, 2, 5} for rows in tool_outputs)


@pytest.mark.asyncio
async def test_graph_material_endpoint_uses_current_properties(records_db):
    from backend.api.kg import material_context
    result = await material_context("LaH10")
    assert {r["id"] for r in result["properties"]} == {1, 2, 5, 7, 8, 9}


@pytest.mark.asyncio
async def test_core_full_answer_and_stream_without_legacy_tables(records_db, monkeypatch):
    from backend.rag.core import engine
    prompts = []
    monkeypatch.setattr(engine, "async_session_factory", records_db)
    monkeypatch.setattr(engine, "_extract_intent", lambda question: {
        "intent": "numeric_compare", "question_type": "factual", "predicates": ["Tc"],
        "subjects": [], "operator": ">", "value": "200",
    })
    monkeypatch.setattr(engine, "get_llm_config", lambda: SimpleNamespace(api_key="test", model="test"))

    def complete(**kwargs):
        prompts.append(kwargs["messages"])
        if kwargs.get("stream"):
            return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="测试回答"))])]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="测试回答"))])

    monkeypatch.setattr(engine, "get_llm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=complete)),
    ))
    answer = await engine.ask("哪些 Tc 大于 200 K？")
    events = [event async for event in engine.ask_stream("哪些 Tc 大于 200 K？")]
    assert answer["answer"] == events[-1]["data"]["answer"] == "测试回答"
    assert len(answer["top10"]) == len(events[-1]["data"]["top10"]) == 3
    assert set(answer["papers"]) == {1, 4}
    assert all("parameters" in str(prompt) for prompt in prompts)


@pytest.mark.asyncio
async def test_sync_tool_wrapper_and_paper_visibility(records_db, monkeypatch):
    from backend.rag import service
    from backend.rag.agent.tools import query_properties
    monkeypatch.setattr(service, "_ensure_data_available", lambda: None)
    result = await asyncio.to_thread(query_properties.invoke, {"predicate": "Tc", "condition": ">200"})
    assert {r["id"] for r in json.loads(result)} == {1, 2, 5}
    assert {p["id"] for p in await service.list_papers()} == {1, 4}
    assert {p["id"] for p in await service.search_superconductors()} == {1, 4}
    assert (await service.paper_detail(1))["record_count"] == 5
    with pytest.raises(service.RagNotFoundError):
        await service.paper_detail(2)
