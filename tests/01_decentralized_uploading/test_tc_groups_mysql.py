"""将真实共享组件的四点／两方法载荷送入隔离 MySQL，验证重读、返修与导出。"""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend import models
from backend.ingest.property_modules import persist_property_modules, PropertyValidationError
from backend.ingest.form_definitions import definition_checksum
from backend.api.material_state_export import build_material_state_export
from backend.services.paper_revisions import current_draft

ROOT = Path(__file__).parents[2]
pytestmark = pytest.mark.skipif(not os.environ.get('TC_GROUP_TEST_DATABASE_URL'), reason='需要显式隔离 MySQL')


def test_browser_payload_mysql_reopen_revision_export_and_retained_records():
    url = make_url(os.environ['TC_GROUP_TEST_DATABASE_URL'])
    assert url.drivername.startswith('mysql') and (url.database or '').startswith('scwiki_issue139_test_')
    payload = json.loads((ROOT / 'docs/specs/94-property-record-editor/assets/tc-group-saved-browser-payload.json').read_text())
    fixture = json.loads((ROOT / 'docs/specs/94-property-record-editor/assets/tc-group-implemented-fixture.json').read_text())
    records = payload['modules'][0]['records']
    assert len(records) == 4 and all(r['value_kind'] == 'number' for r in records)
    assert sum(bool(r.get('is_representative')) for r in records) == 1
    assert {r['method_code'] for r in records} == {'isotropic_eliashberg', 'allen_dynes'}
    async def exercise():
        engine = create_async_engine(url.set(drivername='mysql+asyncmy'))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:12]
        async with sessions.begin() as session:
            seeds = json.loads((ROOT / 'backend/data/form_definitions.v1.json').read_text())
            module_seed = next(s for s in seeds if s['definition_key'] == payload['modules'][0]['definition_key'])
            for raw in [module_seed, *fixture['definitions']]:
                row = await session.scalar(select(models.FormDefinition).where(models.FormDefinition.definition_key == raw['definition_key'], models.FormDefinition.version == raw['version']))
                if row is None:
                    data = {k: v for k, v in raw.items() if k != 'checksum'}
                    session.add(models.FormDefinition(**data, checksum=raw.get('checksum') or definition_checksum(data)))
            user = models.User(username='tc'+suffix, real_name='隔离验证', email=suffix+'@tc-groups.invalid', password_hash='isolated-only', role='user', is_approved=True)
            session.add(user); await session.flush()
            paper = models.Paper(title='多组 Tc 隔离保存 '+suffix, year=2026, uploaded_by_user_id=user.id, review_status='pending', content_revision=1)
            session.add(paper); await session.flush()
            state = models.MaterialState(state_key='tc-state', material_name='隔离验证材料', paper_id=paper.id, paper_revision=1,
                state_kind='theoretical', structure_optimization='unknown', crystal_system='unknown', material_dimensionality='unknown')
            session.add(state)
            file = models.PaperFile(paper_id=paper.id, paper_revision=1, role='main', original_filename='fixture.txt', stored_path='isolated/'+suffix,
                                    sha256='0'*64, size=0, sort_order=0)
            session.add(file); await session.flush()
            chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=file.id, chunk_index=0, content='Isolated source fixture')
            session.add(chunk); await session.flush()
            evidence = models.PaperEvidence(paper_id=paper.id, paper_revision=1, paper_chunk_id=chunk.id, field_path='value_number', quote='Isolated source fixture')
            session.add(evidence); await session.flush()
            incoming = deepcopy(payload['modules'])
            for r in incoming[0]['records'][:2]:
                r['evidences'] = [{'paper_evidence_id': evidence.id, 'field_path': 'value_number'}]
            await persist_property_modules(session, paper_id=paper.id, paper_revision=1, material_state_id=state.id, modules=incoming)
            pid, sid, uid = paper.id, state.id, user.id
        async with sessions() as session:
            paper = await session.get(models.Paper, pid)
            exported = await session.run_sync(lambda db: build_material_state_export(db, paper_id=pid, state_key='tc-state', user=models.User(id=uid, role='user')))
            actual = exported['property_modules'][0]['records']
            assert len(actual) == 4
            expected = {r['record_key']: r for r in records}
            for r in actual:
                before = expected[r['record_key']]
                assert r['value_number'] == before['value_number']
                assert r['payload'] == before['payload']
                assert r['is_representative'] == before['is_representative']
            assert actual[0]['evidences'] and actual[1]['evidences']
            revision = await session.run_sync(lambda db: current_draft(db, db.get(models.Paper, pid)))
            reopened = revision['material_states'][0]['property_modules'][0]['records']
            assert {r['record_key']: r['payload']['tc_group'] for r in reopened} == {r['record_key']: r['payload']['tc_group'] for r in actual}
        # 部分写入不能绕过已保留的不同方法代表，也不能改坏同一共同参数组。
        async with sessions.begin() as session:
            incoming = deepcopy(payload['modules'])
            incoming[0]['records'] = [incoming[0]['records'][0]]
            incoming[0]['records'][0]['is_representative'] = True
            with pytest.raises(PropertyValidationError) as error:
                await persist_property_modules(session, paper_id=pid, paper_revision=1, material_state_id=sid, modules=incoming)
            assert any(i.code == 'duplicate_representative_tc' for i in error.value.issues)
        async with sessions.begin() as session:
            incoming[0]['records'][0]['is_representative'] = False
            incoming[0]['records'][0]['payload']['calculation_conditions']['k_grid'] = '3×3×3'
            with pytest.raises(PropertyValidationError) as error:
                await persist_property_modules(session, paper_id=pid, paper_revision=1, material_state_id=sid, modules=incoming)
            assert any(i.code == 'tc_group_conditions_conflict' for i in error.value.issues)
        await engine.dispose()
    asyncio.run(exercise())
