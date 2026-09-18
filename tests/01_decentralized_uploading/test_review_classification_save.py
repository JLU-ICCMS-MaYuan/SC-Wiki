"""#100：真实科学保存不能忽略仅论文级分类变化。"""
import asyncio
import copy

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from fastapi import HTTPException

from backend import models
from backend.api.rag import _rewrite_paper_scientific_draft_in_tx
from backend.database import Base


def sqlite_sessions(path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{path}')
    # SQLite 默认延迟 BEGIN 会让首个 SAVEPOINT 提前提交；显式事务才能验证回滚。
    @event.listens_for(engine.sync_engine, 'connect')
    def connect(dbapi, _):
        dbapi.isolation_level = None
        cursor = dbapi.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
    @event.listens_for(engine.sync_engine, 'begin')
    def begin(connection):
        connection.exec_driver_sql('BEGIN')
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.parametrize('changed', ['kind', 'family'])
@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_classification_only_save_persists_and_repeat_is_unchanged(tmp_path, changed, status):
    async def run():
        engine, sessions = sqlite_sessions(tmp_path / 'classification.db')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions.begin() as session:
                actor = models.User(id=7, email='reviewer@example.test', username='reviewer',
                    real_name='测试管理员', password_hash='unused', role='admin')
                session.add(actor)
                session.add(models.Paper(id=1, title='分类保存回归', year=2026, paper_type='review',
                    content_revision=1, review_status=status, approved_revision=1 if status == 'approved' else None,
                    superconductor_kind='conventional'))
                session.add_all([models.MaterialFamily(id=i, code=f'family_{i}', name_zh=f'家族{i}',
                    normalized_name=f'家族{i}') for i in (1, 2)])
                await session.flush()
                session.add(models.PaperMaterialFamily(paper_id=1, paper_revision=1, material_family_id=1))
            family_id = 2 if changed == 'family' else 1
            kind = 'unconventional' if changed == 'kind' else 'conventional'
            payload = dict(paper_type='review', superconductor_kind=kind,
                material_families=[dict(id=family_id, name=f'家族{family_id}', status='confirmed')],
                material_states=[], structure_candidates=[])
            async with sessions.begin() as session:
                result = await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), actor)
                assert result['data']['unchanged'] is False
            async with sessions.begin() as session:
                paper = await session.get(models.Paper, 1)
                assert paper.superconductor_kind == kind
                assert list(await session.scalars(select(models.PaperMaterialFamily.material_family_id)
                    .where(models.PaperMaterialFamily.paper_id == 1))) == [family_id]
                assert paper.content_revision == (2 if status == 'approved' else 1)
                assert paper.review_status == 'pending'
                repeated = await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), actor)
                assert repeated['data']['unchanged'] is True
        finally:
            await engine.dispose()
    asyncio.run(run())


@pytest.mark.parametrize('role', ['admin', 'superadmin'])
def test_new_families_save_reload_clear_and_rollback(tmp_path, role, monkeypatch):
    async def run():
        engine, sessions = sqlite_sessions(tmp_path / 'new-families.db')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions.begin() as session:
                actor = models.User(id=7, email='reviewer@example.test', username='reviewer',
                    real_name='测试管理员', password_hash='unused', role=role)
                session.add(actor)
                session.add(models.Paper(id=1, title='新分类保存', year=2026, paper_type='review',
                    content_revision=1, review_status='pending', superconductor_kind='unknown'))
            payload = dict(paper_type='review', superconductor_kind='unconventional',
                material_families=[dict(name='新材料家族', status='pending')],
                material_states=[dict(state_key='tin', material='Sn', material_name='Tin',
                    material_dimensionality='two_dimensional', property_modules=[],
                    structure_families=[dict(name='新结构家族', status='pending', is_primary=True)])])
            # 普通上传解析依旧不能创建目录。
            from backend.api.rag import _resolve_draft_classifications
            async with sessions.begin() as session:
                upload = dict(paper={'material_families': copy.deepcopy(payload['material_families'])},
                    material_states=copy.deepcopy(payload['material_states']))
                await _resolve_draft_classifications(session, upload)
                assert upload['paper']['material_families'][0]['id'] is None
                assert list(await session.scalars(select(models.MaterialFamily))) == []
            async with sessions.begin() as session:
                await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), actor)
            async with sessions.begin() as session:
                family = await session.scalar(select(models.MaterialFamily))
                structure = await session.scalar(select(models.StructureFamily))
                assert family is not None and structure is not None
                assert family.created_by_user_id == structure.created_by_user_id == actor.id
                assert await session.scalar(select(models.PaperMaterialFamily.material_family_id)) == family.id
                link = await session.scalar(select(models.MaterialStateStructureFamily))
                assert link.structure_family_id == structure.id and link.is_primary
                repeated = await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), actor)
                assert repeated['data']['unchanged'] is True
            payload['material_states'][0]['structure_families'] = []
            async with sessions.begin() as session:
                await _rewrite_paper_scientific_draft_in_tx(session, 1, copy.deepcopy(payload), actor)
            async with sessions() as session:
                assert list(await session.scalars(select(models.MaterialStateStructureFamily))) == []
            empty = {**payload, 'material_families': []}
            with pytest.raises(HTTPException) as error:
                async with sessions.begin() as session:
                    await _rewrite_paper_scientific_draft_in_tx(session, 1, empty, actor)
            assert error.value.detail['code'] == 'material_family_required'
            # 目录创建后的后段失败，整个事务应回滚。
            from backend.ingest import property_evidence
            async def fail(*args):
                raise ValueError('injected evidence failure')
            monkeypatch.setattr(property_evidence, 'persist_existing_paper_targets', fail)
            invalid = copy.deepcopy(payload)
            invalid['material_families'] = [dict(name='必须回滚', status='pending')]
            with pytest.raises(ValueError, match='injected'):
                async with sessions.begin() as session:
                    await _rewrite_paper_scientific_draft_in_tx(session, 1, invalid, actor)
            async with sessions() as session:
                assert list(await session.scalars(select(models.MaterialFamily.name_zh))) == ['新材料家族']
                assert await session.scalar(select(models.PaperMaterialFamily.material_family_id)) == family.id
        finally:
            await engine.dispose()
    asyncio.run(run())
