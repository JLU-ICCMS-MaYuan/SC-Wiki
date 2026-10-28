"""真实提交门禁及正式论文/谱绑定，MySQL 外层回滚，随机 Redis 键隔离。"""
import asyncio
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend import database, models
from backend.api import rag
from backend.ingest import property_evidence as ev, scientific_evidence as science, upload_tasks
from backend.services import spectra
from test_scientific_evidence_mysql import current_mysql

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅本机回滚测试')


@pytest.mark.parametrize('blocked', [False, True])
def test_real_submit_carries_unreviewed_spectra_but_retains_field_gate(current_mysql, monkeypatch, tmp_path, blocked):
    from backend.rag import database as async_database
    target = uuid4().hex
    client = upload_tasks.redis_client()
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    monkeypatch.setattr(upload_tasks, 'markdown_path', lambda _: tmp_path / (target + '.md'))
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda task, path: path)
    # 仅隔离提交完成后的临时文件收尾；字段门禁、论文持久化、谱绑定不替换。
    monkeypatch.setattr(rag, '_record_submitted_upload', lambda *a, **k: None)
    monkeypatch.setattr(upload_tasks, 'cleanup_transient_data', lambda *a, **k: None)
    monkeypatch.setattr(spectra, 'review_curve', lambda *a, **k: pytest.fail('提交不应审核谱'))
    from backend.spectra import jobs
    monkeypatch.setattr(jobs, 'dispatch', lambda *a, **k: pytest.fail('提交不应请求谱模型'))
    keys = [upload_tasks.task_key(target), upload_tasks.draft_key(target), upload_tasks.lock_key(target)]
    owners = []

    async def exercise():
        engine = create_async_engine(async_database.engine.url, poolclass=NullPool)
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            monkeypatch.setattr(async_database, 'async_session_factory', factory)
            try:
                async with factory() as db:
                    user = await db.scalar(select(models.User).where(models.User.account_status == 'active').limit(1))
                    family = await db.scalar(select(models.MaterialFamily).limit(1))
                    actor = SimpleNamespace(id=user.id, role='user', username=user.username)
                    owners.append(actor.id)
                    draft = {'_field_edit_format': 1, 'paper': {'title': 'Isolated unreviewed spectra submit',
                        'year': 2026, 'paper_type': 'theoretical', 'theoretical_subtype': 'calculation', 'superconductor_kind': 'conventional',
                        'material_families': [{'id': family.id, 'name': family.name_zh, 'status': 'confirmed'}]},
                        'material_states': [{'state_key': 's1', 'material': 'H3S', 'state_kind': 'theoretical',
                            'pressure_value_gpa': 150, 'property_modules': []}]}
                    state = {'user_id': actor.id, 'stage': 'ready', 'status': 'ready', 'processing_status': 'succeeded',
                             'file_kind': 'txt', 'filename': 'isolated.txt', 'parser_profile': 'legacy'}
                    client.setex(keys[0], 600, json.dumps(state)); client.setex(keys[1], 600, json.dumps(draft))
                    collections = []
                    for kind in ('alpha2f', 'phonon_dos'):
                        row = await db.run_sync(lambda session: spectra.collection(session,
                            {'target': 'upload', 'target_id': target, 'owner_id': actor.id, 'paper': None,
                             'paper_revision': None}, 'source', kind, {}))
                        row.state_key = 's1'
                        run, _ = await db.run_sync(lambda session: spectra.new_run(session, row, {}, draft['material_states'][0]))
                        run.status = 'needs_review'
                        run.result_json = {'curves': [{'id': kind, 'kind': kind,
                            'points': [{'frequency_thz': 1, 'observed_amplitude': 2}]}], 'quality': {}, 'candidates': {}}
                        row.current_run_id = run.id
                        row.review_json = {}
                        collections.append((row.id, run.id, run.result_json))
                    await db.commit()
                snapshot = ev.upload_snapshot(target, actor.id)
                with current_mysql.begin() as sync:
                    science.save_results(sync, snapshot, {r['key']: {'status': 'unsupported' if blocked and r['field'] == 'paper.superconductor_kind' else 'supported',
                        'reason': '隔离预置字段结论，谱未审核'} for r in snapshot['records']}, actor.id)
                if blocked:
                    with pytest.raises(HTTPException) as failure:
                        await rag.submit_upload_draft(target, actor, rag.SubmitUploadOptions(expected_evidence_version=snapshot['version']))
                    assert failure.value.detail['code'] == 'evidence_review_required'
                    async with factory() as db:
                        assert await db.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == target)) is None
                else:
                    result = await rag.submit_upload_draft(target, actor, rag.SubmitUploadOptions(expected_evidence_version=snapshot['version']))
                    assert result['ok'] and result['review_status'] == 'pending'
                    async with factory() as db:
                        for collection_id, run_id, payload in collections:
                            row = await db.get(models.SpectrumCollection, collection_id)
                            run = await db.get(models.SpectrumRun, run_id)
                            assert row.target == 'paper' and row.paper_id == result['paper_id']
                            assert row.material_state_id is not None
                            assert row.review_json == {} and run.status == 'needs_review'
                            assert run.result_json == payload
            finally:
                await outer.rollback()
        await engine.dispose()

    try:
        asyncio.run(exercise())
    finally:
        client.delete(*keys)
        for owner in owners:
            client.zrem(upload_tasks.user_tasks_key(owner), target)
