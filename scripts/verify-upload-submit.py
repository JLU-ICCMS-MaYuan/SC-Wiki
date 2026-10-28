"""真实草稿完整提交回放：数据库外层回滚，生命周期和快照写入隔离副本。"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def verify(task_id, output):
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from backend import models, storage
    from backend.api import rag
    from backend.ingest import upload_tasks as uploads, property_evidence as ev, scientific_evidence as science
    from backend.ingest.upload_contracts import apply_state_changes
    from backend.database import SessionLocal
    from backend.rag import database as adb
    from backend.storage.files import LocalFileStorage

    actual_state, actual_draft = uploads.get_state(task_id), uploads.get_draft(task_id)
    if not actual_state or actual_state.get('stage') != 'ready' or actual_state.get('paper_id'):
        raise ValueError('需要未提交且 ready 的已授权任务')
    snapshot = ev.upload_snapshot(task_id, int(actual_state['user_id']))
    with SessionLocal() as db:
        actor_row = db.get(models.User, int(actual_state['user_id']))
        actor = SimpleNamespace(id=actor_row.id, username=actor_row.username, role=actor_row.role)
        cached = science.load_results(db, snapshot, actor.id, include_stale=True)
    checks = []  # 已提交到一半的任务在隔离事务中恢复原上传关联后再走真实门禁。
    output.mkdir(parents=True, exist_ok=True)
    local_artifact = output / 'result.json'
    original_artifact = uploads.read_artifact_path(task_id)
    if original_artifact.exists():
        shutil.copyfile(original_artifact, local_artifact)
    state, draft = deepcopy(actual_state), deepcopy(actual_draft)
    report = {'task_id': task_id, 'original_fields': len(snapshot['records']), 'actual_paper_submitted': False,
              'storage_mode': 'isolated_local', 'cleanup': [], 'model_calls': 0}

    def get_state(key):
        assert key == task_id
        return deepcopy(state)

    def get_draft(key):
        assert key == task_id
        return deepcopy(draft)

    def update_state(key, **changes):
        assert key == task_id
        updated = apply_state_changes(state, now=int(time.time()), **changes)
        state.clear(); state.update(updated)
        return deepcopy(state)

    original_record = rag._record_submitted_upload
    def record_snapshot(*args, **kwargs):
        with patch.object(uploads, 'artifact_path', lambda _: local_artifact), \
             patch.object(uploads, 'read_artifact_path', lambda _, **kw: local_artifact), \
             patch.object(storage, 'create_storage', lambda **kw: LocalFileStorage(output / 'objects')):
            original_record(*args, **kwargs)

    original_cleanup = uploads.cleanup_transient_data
    class IsolatedCleanup:
        def delete(self, *keys): report['cleanup'].append({'delete': list(keys)})
        def zrem(self, key, value): report['cleanup'].append({'zrem': [key, value]})

    def cleanup(*args, **kwargs):
        with patch.object(uploads, 'data_path', lambda name: output / 'cleanup' / name), \
             patch.object(uploads, 'redis_client', lambda: IsolatedCleanup()), \
             patch.object(uploads, '_delete_processing_job', lambda key: report['cleanup'].append({'job': key})):
            original_cleanup(*args, **kwargs)

    engine = create_async_engine(adb.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            try:
                existing_id = await connection.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id))
                report['existing_paper_preserved'] = existing_id
                async with factory() as setup:
                    if existing_id is not None:
                        # 只在外层回滚事务中腾出原任务身份并恢复上传关联，外部仍读取真实已提交记录。
                        from backend.manual_evidence_models import ScientificManualEvidence
                        from backend.ingest.field_review import bind_support_versions
                        paper = await setup.get(models.Paper, existing_id)
                        paper.upload_task_id = None
                        paper.doi = None  # 回滚副本释放重复检查身份；正式论文在事务外保持原值。
                        for event in (await setup.scalars(select(models.PaperHistoryEvent).where(
                                models.PaperHistoryEvent.operation_id == task_id))).all():
                            event.operation_id = None
                        by_item = {r['item_key']: r for r in snapshot['records']}
                        for note in (await setup.scalars(select(ScientificManualEvidence).where(
                                ScientificManualEvidence.target == 'paper', ScientificManualEvidence.target_id == str(existing_id)))).all():
                            record = by_item.get(note.item_key)
                            if record is not None and note.value_hash == record['content_hash']:
                                note.target, note.target_id = 'upload', task_id
                                note.paper_id, note.paper_revision = None, None
                                note.source_hash = record.get('paper_source_hash', record['source_hash'])
                        for spectrum in (await setup.scalars(select(models.SpectrumCollection).where(models.SpectrumCollection.paper_id == existing_id))).all():
                            spectrum.target, spectrum.target_id = 'upload', task_id
                            spectrum.paper_id, spectrum.paper_revision, spectrum.material_state_id = None, None, None
                        await setup.flush()
                        await setup.run_sync(lambda s: bind_support_versions(snapshot, s))
                    cached = await setup.run_sync(lambda s: science.load_results(s, snapshot, actor.id, include_stale=True))
                    checks = ev.resolve_results(snapshot, cached, actor.id, None, snapshot['version'])
                    await setup.commit()
                with ExitStack() as stack:
                    for owner, name, replacement in [(adb, 'async_session_factory', factory), (uploads, 'get_state', get_state),
                        (uploads, 'get_draft', get_draft), (uploads, 'update_state', update_state),
                        (rag, '_record_submitted_upload', record_snapshot), (uploads, 'cleanup_transient_data', cleanup)]:
                        stack.enter_context(patch.object(owner, name, replacement))
                    stack.enter_context(patch.object(ev, 'upload_snapshot', lambda key, uid: deepcopy(snapshot)))
                    from backend.rag import llm
                    stack.enter_context(patch.object(llm, 'complete_json', side_effect=AssertionError('已确认草稿提交不能调用模型')))
                    response = await rag.submit_upload_draft(task_id, actor,
                        rag.SubmitUploadOptions(expected_evidence_version=snapshot['version']))
                    report['response'] = response
                    paper_id = response['paper_id']
                    async with factory() as db:
                        paper = await db.get(models.Paper, paper_id)
                        formal = await db.run_sync(lambda s: ev.paper_snapshot(s, paper_id, actor.id, actor.role, check_access=False))
                        restored = await db.run_sync(lambda s: science.load_results(s, formal, actor.id, include_stale=True))
                        report['paper_status'] = paper.review_status
                        for name, table in [('material_states', models.MaterialState), ('property_records', models.PropertyRecord),
                            ('structures', models.StructureModel), ('paper_evidence', models.PaperEvidence),
                            ('spectra', models.SpectrumCollection)]:
                            report[name] = await db.scalar(select(func.count()).select_from(table).where(table.paper_id == paper_id))
                        report['formal_fields'] = len(formal['records'])
                        report['formal_supported'] = sum(r.get('status') == 'supported' and not r.get('stale') for r in restored.values())
                        from backend.api import evidence as evidence_api
                        from backend.ingest.field_review import valid_field_decision
                        report['formal_human_confirmed'] = sum(valid_field_decision(r, restored.get(r['key']), 'approve') for r in formal['records'])
                        def read_summary(session):
                            @contextmanager
                            def same_session(): yield session
                            reviewer = SimpleNamespace(id=actor.id + 1000000, role='admin')
                            with patch.object(evidence_api, 'SessionLocal', same_session):
                                return evidence_api.field_summary(evidence_api.Target(target='paper', target_id=str(paper_id)), reviewer)
                        summary = await db.run_sync(read_summary)
                        report['summary_pending'] = sum(r.get('pending_review', False) for r in summary['records'])
                        report['summary_human_confirmed'] = sum(r.get('human_confirmed', False) for r in summary['records'])
                        report['formal_problems'] = [{'field': r['field'], 'value': r.get('current_value'),
                            'status': restored.get(r['key'], {}).get('status'), 'stale': restored.get(r['key'], {}).get('stale'),
                            'old_claim': next((old.get('claim') for old in checks if old['item_key'] == r['item_key']), None),
                            'new_claim': r.get('claim'), 'content_hash': r['content_hash'],
                            'old_content_hash': next((old.get('content_hash') for old in checks if old['item_key'] == r['item_key']), None)} for r in formal['records']
                            if restored.get(r['key'], {}).get('status') != 'supported' or restored.get(r['key'], {}).get('stale')]
                    report['virtual_task_status'] = state['status']
                    assert state.get('paper_id') == paper_id and state['status'] == 'submitted', '提交后快照/状态未完成'
                    assert local_artifact.exists() and json.loads(local_artifact.read_text())['paper_id'] == paper_id
                    from backend.storage import paths
                    with patch.object(paths, 'create_storage', lambda **kw: LocalFileStorage(output / 'objects')), \
                         patch.object(paths, '_cache_root', lambda namespace=None: output / 'reader-cache'):
                        stored_snapshot = rag._artifact_by_paper_id(paper_id, task_id, 1)
                        assert stored_snapshot and stored_snapshot[2]['paper_id'] == paper_id
                        report['artifact_reader_verified'] = True
                    repeated = await rag.submit_upload_draft(task_id, actor,
                        rag.SubmitUploadOptions(expected_evidence_version=snapshot['version']))
                    assert repeated['paper_id'] == paper_id
                    report['idempotent'] = True
                    assert report['formal_supported'] == report['formal_fields']
                    assert report['formal_human_confirmed'] == report['original_fields']
                    assert report['summary_pending'] == 0 and report['summary_human_confirmed'] == report['original_fields']
            except Exception as error:
                report['failure'] = {'type': type(error).__name__, 'detail': getattr(error, 'detail', str(error))}
            finally:
                await outer.rollback()
            assert await connection.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id)) == existing_id
    finally:
        await engine.dispose()
    assert uploads.get_draft(task_id) == actual_draft
    assert uploads.get_state(task_id) == actual_state
    report['original_preserved'] = True
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in {'formal_problems', 'cleanup'}}, ensure_ascii=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    values = read_config(ROOT); validate_local(values, ROOT); os.environ.update(values)
    report = asyncio.run(verify(args.task, args.output.resolve()))
    if report.get('failure'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
