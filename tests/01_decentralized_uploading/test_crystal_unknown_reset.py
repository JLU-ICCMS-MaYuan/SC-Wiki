"""Issue #105：空空间群的归一化、科学保存和核对上下文，全部使用隔离数据。"""
import asyncio
import copy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.api.rag import _rewrite_paper_scientific_draft_in_tx
from backend.database import Base
from backend.ingest import scientific_evidence as science
from backend.ingest.upload_jobs import _normalize_draft
from backend.ingest.scientific_drafts import persist_scientific_draft


CLEARED = dict(crystal_system="unknown", reported_space_group_symbol=None, reported_space_group_number=None)


def state(key="fixture-105-a"):
    return dict(state_key=key, material="Sn", element_count=1, material_dimensionality="three_dimensional",
                state_kind="experimental", crystal_system="cubic", reported_space_group_symbol="Fm-3m",
                reported_space_group_number=225, property_modules=[], structure_families=[])


def draft(states):
    return dict(paper=dict(title="隔离晶系验收", year=2026, paper_type="experimental",
                          superconductor_kind="conventional", material_families=[dict(name="fixture", status="pending")]),
                material_states=states, structure_candidates=[])


def test_normalization_keeps_explicit_clear_and_other_state():
    original = draft([{**state(), **CLEARED}, state("fixture-105-b")])
    normalized = _normalize_draft(copy.deepcopy(original))
    for _ in range(2):
        first, second = normalized["material_states"]
        assert {key: first[key] for key in CLEARED} == CLEARED
        assert second["reported_space_group_number"] == 225
        assert second["reported_space_group_symbol"] == "Fm-3m"
        assert second["crystal_system"] == "cubic"
        normalized = _normalize_draft(normalized)


def test_normalization_still_derives_crystal_from_explicit_valid_group():
    value = draft([{**state(), "crystal_system": "unknown"}])
    assert _normalize_draft(value)["material_states"][0]["crystal_system"] == "cubic"


def test_clear_removes_empty_review_items_and_changes_dependent_claim():
    before = state()
    after = {**before, **CLEARED}
    rows = science.state_records(after, 0)
    assert not any(row["field"].rsplit(".", 1)[-1] in CLEARED for row in rows)
    record = dict(record_type="measured_tc", property_code="tc", value_kind="number", value_number=3.8,
                  module_code="superconductive_properties", canonical_unit="K", payload={})
    assert science.record_claim(record, before) != science.record_claim(record, after)


def test_upload_persistence_and_admin_rewrite_roundtrip():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            # 上传和管理端使用同一持久化函数；先存已知值，再经管理端事务改为空值。
            initial = _normalize_draft(draft([state(), state("fixture-105-b")]))
            async with sessions() as session, session.begin():
                paper = models.Paper(id=1, title="隔离晶系验收", year=2026, paper_type="experimental",
                                     superconductor_kind="conventional", review_status="pending", content_revision=1)
                reviewer = models.User(id=1, username="fixture", real_name="Fixture", email="fixture@example.invalid", password_hash="test", role="admin")
                session.add_all([paper, reviewer])
                await session.flush()
                await persist_scientific_draft(session, paper, initial)

            payload = dict(paper_type="experimental", superconductor_kind="conventional",
                           material_families=[dict(name="fixture", status="pending")],
                           material_states=[{**initial["material_states"][0], **CLEARED}, initial["material_states"][1]],
                           structure_candidates=[])
            async with sessions() as session, session.begin():
                reviewer = await session.get(models.User, 1)
                saved = await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), reviewer)
                assert saved["ok"] and not saved["data"]["unchanged"]

            # 新会话重读，避免 ORM 缓存掩盖保存错误。
            async with sessions() as session:
                rows = list((await session.scalars(select(models.MaterialState).order_by(models.MaterialState.state_key))).all())
                assert len(rows) == 2
                assert {key: getattr(rows[0], key) for key in CLEARED} == CLEARED
                assert rows[1].reported_space_group_number == 225
                assert rows[1].reported_space_group_symbol == "Fm-3m"
                assert rows[1].crystal_system == "cubic"
                assert (await session.get(models.Paper, 1)).review_status == "pending"
                assert await session.scalar(select(models.PaperHistoryEvent.id)) is not None

            async with sessions() as session, session.begin():
                reviewer = await session.get(models.User, 1)
                again = await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), reviewer)
                assert again["data"]["unchanged"]

            # 新上传直接保存清空后的规范草稿，也必须落库为空。
            async with sessions() as session, session.begin():
                upload_paper = models.Paper(id=2, title="隔离上传晶系验收", year=2026, review_status="pending", content_revision=1)
                session.add(upload_paper)
                await session.flush()
                await persist_scientific_draft(session, upload_paper, _normalize_draft(draft(payload["material_states"])))
            async with sessions() as session:
                uploaded = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == 2,
                                                                                 models.MaterialState.state_key == "fixture-105-a"))
                assert {key: getattr(uploaded, key) for key in CLEARED} == CLEARED
        finally:
            await engine.dispose()

    asyncio.run(run())
