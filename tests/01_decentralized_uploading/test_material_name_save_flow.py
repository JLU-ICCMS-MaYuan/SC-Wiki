"""只填材料名与科学状态编辑的公共保存链路回归。"""
import asyncio
import copy
from contextlib import asynccontextmanager
import os
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend import models
from backend.api.rag import _validate_draft, rewrite_paper_scientific_draft
from backend.database import DATABASE_URL
from backend.ingest import property_evidence as evidence, scientific_evidence as science
from backend.rag import database


def draft(state):
    return {'paper': {'title': 'test', 'year': 2026, 'paper_type': 'experimental',
        'superconductor_kind': 'conventional', 'material_families': [{'name': 'test', 'status': 'pending'}]},
        'material_states': [state]}


@pytest.mark.parametrize('name,formula', [('Tin', ''), ('', 'Sn'), ('Tin', 'Sn')])
def test_name_or_formula_is_valid(name, formula):
    _validate_draft(draft({'material_name': name, 'material': formula}))


@pytest.mark.parametrize('state,field', [
    ({'material_name': '', 'material': ''}, 'material_name'),
    ({'material_name': 'Tin', 'material': '???'}, 'material'),
    ({'material_name': 'x' * 256, 'material': 'Sn'}, 'material_name'),
])
def test_bad_identity_has_field_error(state, field):
    value = draft(state)
    value['paper']['research_materials'] = ['test']
    with pytest.raises(HTTPException) as error:
        _validate_draft(value)
    assert error.value.status_code == 400
    assert error.value.detail['field'] == f'material_states[0].{field}'


def test_name_changes_state_context_without_changing_identity():
    state = dict(state_key='tin', material_name='Tin', material='Sn', element_count=1, pressure_value_gpa=0.1)
    before = science.state_records(state, 0)
    after = science.state_records({**state, 'material_name': 'Pure tin'}, 1)
    assert any(r['field'].endswith('.material_name') for r in before)
    assert [r['item_key'] for r in before] == [r['item_key'] for r in after]
    assert all(a['claim'] != b['claim'] for a, b in zip(before, after))


def test_upload_normalization_keeps_name_without_formula():
    from backend.ingest.upload_jobs import _normalize_draft
    normalized = _normalize_draft(draft({'material_name': 'Tin sample', 'material': '', 'state_key': 'tin'}))
    assert normalized['material_states'][0]['material_name'] == 'Tin sample'
    assert normalized['material_states'][0]['material'] == ''
    _validate_draft(normalized)


def test_optional_formula_migration_keeps_rows_and_refuses_lossy_downgrade(monkeypatch):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260916_0106_optional_state_formula.py'
    spec = importlib.util.spec_from_file_location('optional_state_formula', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE material_states (id INTEGER PRIMARY KEY, superconductor_id INTEGER NOT NULL)'))
            connection.execute(text('INSERT INTO material_states VALUES (1, 7)'))
            monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            assert tuple(connection.execute(text('SELECT * FROM material_states')).one()) == (1, 7)
            assert next(c for c in inspect(connection).get_columns('material_states') if c['name'] == 'superconductor_id')['nullable']
            connection.execute(text('INSERT INTO material_states VALUES (2, NULL)'))
            with pytest.raises(RuntimeError, match='无化学式'):
                migration.downgrade()
            assert connection.execute(text('SELECT COUNT(*) FROM material_states')).scalar() == 2
    finally:
        engine.dispose()


@asynccontextmanager
async def isolated_paper(monkeypatch):
    engine = create_async_engine(DATABASE_URL.replace('mysql+pymysql://', 'mysql+asyncmy://'))
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                def factory():
                    return AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
                monkeypatch.setattr(database, 'async_session_factory', factory)
                async with factory() as session, session.begin():
                    users = list((await session.scalars(select(models.User).where(models.User.account_status == 'active'))).all())
                    reviewer = next(u for u in users if u.role in {'admin', 'superadmin'})
                    uploader = next(u for u in users if u.id != reviewer.id)
                    family = await session.scalar(select(models.MaterialFamily).limit(1))
                    paper = models.Paper(title='材料名回滚 ' + uuid.uuid4().hex, year=2026, paper_type='experimental',
                        review_status='pending', content_revision=1, uploaded_by_user_id=uploader.id,
                        authors=['test'], journal='test', abstract='test', summary='test', superconductor_kind='conventional')
                    session.add(paper)
                    await session.flush()
                    pid = paper.id
                    payload = dict(paper_type='experimental', superconductor_kind='conventional',
                        material_families=[dict(id=family.id, name=family.name_zh, status='confirmed')],
                        material_states=[dict(state_key='tin', material='Sn', material_name='Tin',
                            element_count=1, state_kind='experimental', crystal_system='tetragonal',
                            pressure_value_gpa=0.000101, property_modules=[], structure_families=[])])
                yield factory, reviewer, pid, payload
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


mysql = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='显式选择 MySQL 回滚验证')


@mysql
def test_structure_families_survive_name_edit_and_can_be_cleared(monkeypatch):
    async def run():
        async with isolated_paper(monkeypatch) as (factory, user, pid, payload):
            async with factory() as session, session.begin():
                family = models.StructureFamily(code=uuid.uuid4().hex, name_zh='测试结构' + uuid.uuid4().hex, normalized_name=uuid.uuid4().hex)
                session.add(family)
                await session.flush()
                fid = family.id
                payload['material_states'][0]['structure_families'] = [dict(id=fid, name=family.name_zh, status='confirmed', is_primary=True)]
            for label in ('Tin', 'Pure tin'):
                payload['material_states'][0]['material_name'] = label
                await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user)
                async with factory() as session:
                    link = await session.scalar(select(models.MaterialStateStructureFamily).join(models.MaterialState).where(models.MaterialState.paper_id == pid))
                    assert link is not None and link.structure_family_id == fid and link.is_primary
            payload['material_states'][0]['structure_families'] = []
            assert not (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['data']['unchanged']
            async with factory() as session:
                assert await session.scalar(select(models.MaterialStateStructureFamily).join(models.MaterialState).where(models.MaterialState.paper_id == pid)) is None
    asyncio.run(run())


@mysql
def test_clear_formula_then_confirm_name_and_reload(monkeypatch):
    from backend.ingest import evidence_proposals as proposals
    from backend.api.material_state_export import build_material_state_export

    async def run():
        async with isolated_paper(monkeypatch) as (factory, user, pid, payload):
            assert (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['ok']
            async with factory() as session:
                old = await session.run_sync(lambda s: evidence.paper_snapshot(s, pid, user.id, user.role))
                formula = next(r for r in old['records'] if r['field'].endswith('.material'))
            payload['material_states'][0]['material'] = ''
            assert (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['ok']
            async with factory() as session, session.begin():
                state = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == pid))
                assert state.superconductor_id is None and state.material_name == 'Tin'
                snap = await session.run_sync(lambda s: evidence.paper_snapshot(s, pid, user.id, user.role))
                assert not any(r['item_key'] == formula['item_key'] for r in snap['records'])
                name = next(r for r in snap['records'] if r['field'].endswith('.material_name'))
                result = await session.run_sync(lambda s: proposals.save_draft(s, snap, user.id, name['key'], {}, True, '论文明确称该样品为 Tin，未提供化学式'))
                assert result['accepted']
                exported = await session.run_sync(lambda s: build_material_state_export(s, paper_id=pid, state_key='tin', user=user))
                assert exported['material_state']['material_name'] == 'Tin'
                assert exported['material_state']['material'] == ''
            unchanged = await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user)
            assert unchanged['data']['unchanged']
            async with factory() as session:
                snap = await session.run_sync(lambda s: evidence.paper_snapshot(s, pid, user.id, user.role))
                restored = await session.run_sync(lambda s: science.load_results(s, snap, user.id))
                assert evidence.public_snapshot(snap, restored)['records']
    asyncio.run(run())


@mysql
@pytest.mark.parametrize('changes', [
    {'material_name': 'Pure tin'}, {'material_name': None}, {'pressure_raw': '1 atm'},
    {'pressure_min_gpa': 0}, {'pressure_max_gpa': 1}, {'note': '人工条件说明'},
    {'crystal_system': 'cubic'}, {'reported_space_group_symbol': 'P1'},
    {'element_count': 2}, {'material_dimensionality': 'two_dimensional'},
])
def test_single_state_field_change_is_not_skipped(monkeypatch, changes):
    async def run():
        async with isolated_paper(monkeypatch) as (factory, user, pid, payload):
            await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user)
            payload['material_states'][0].update(changes)
            result = await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user)
            assert not result['data']['unchanged']
            async with factory() as session:
                saved = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == pid))
                assert all(getattr(saved, k) == v for k, v in changes.items())
            assert (await rewrite_paper_scientific_draft(pid, copy.deepcopy(payload), user))['data']['unchanged']
    asyncio.run(run())
