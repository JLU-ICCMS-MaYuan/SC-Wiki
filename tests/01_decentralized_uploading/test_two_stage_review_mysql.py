"""本机MySQL外层回滚与隔离Redis键验证。绝不更改真实草稿。"""
import json
import os
import uuid
from copy import deepcopy
from types import SimpleNamespace
from time import perf_counter

import pytest
from sqlalchemy import select
from backend import models
from backend.ingest import scientific_evidence as science, property_evidence as ev
from backend.ingest.field_drafts import save_fields, draft_version, authorized_draft
from test_scientific_evidence_mysql import current_mysql, snapshot

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式启用本机回滚测试')


def test_current_result_reuses_pass_without_quote_or_history_scan(current_mysql, monkeypatch):
    snap = snapshot()
    record = snap['records'][0]
    with current_mysql.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'reason': '有效原文',
            'evidences': [snap['chunks'][0] | {'quote': snap['chunks'][0]['content']}]}}, 7)
    monkeypatch.setattr(science, 'ordered_check_rows', lambda *a, **k: pytest.fail('不应扫描全部历史'))
    monkeypatch.setattr(ev, 'locate_with_reason', lambda *a, **k: pytest.fail('不应重扫旧引句'))
    with current_mysql.begin() as db:
        result = science.load_results(db, snap, 7)[record['key']]
        assert ev.checked_result(record, result, snap['chunks'])['status'] == 'supported'


def test_new_model_conflict_is_persisted_as_anomaly(current_mysql):
    snap = snapshot()
    record = snap['records'][0]
    with current_mysql.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'model': 'a'}}, 7)
        science.save_results(db, snap, {record['key']: {'status': 'unsupported', 'model': 'b'}}, 7)
    with current_mysql.begin() as db:
        result = science.load_results(db, snap, 7)[record['key']]
        assert result['status'] == 'supported'
        assert result['consistency_anomalies'][0]['model'] == 'b'


def test_admin_patch_stages_without_formal_write(current_mysql, monkeypatch):
    with current_mysql.begin() as db:
        users = list(db.scalars(select(models.User).where(models.User.account_status == 'active').limit(2)))
        paper = models.Paper(title='隔离测试旧标题', year=2026, review_status='pending', content_revision=1,
                             uploaded_by_user_id=users[0].id)
        db.add(paper); db.flush()
        actor = SimpleNamespace(id=users[1].id, role='admin', username=users[1].username)
        draft, _ = authorized_draft(db, 'paper', str(paper.id), actor)
        monkeypatch.setattr(ev, 'complete_snapshot', lambda *a, **k: pytest.fail('保存不应构造科学快照'))
        monkeypatch.setattr(science, 'load_results', lambda *a, **k: pytest.fail('保存不应读取核对结果'))
        saved = save_fields(db, 'paper', str(paper.id), actor, draft_version(draft), [
            {'path': ['paper', 'title'], 'before': '隔离测试旧标题', 'value': '隔离测试新标题'}])
        assert saved['changed']
        db.refresh(paper)
        assert paper.title == '隔离测试旧标题'
        staged = db.get(models.ScientificReviewDraft, paper.id)
        assert staged.draft['paper']['title'] == '隔离测试新标题'
        with pytest.raises(Exception):
            save_fields(db, 'paper', str(paper.id), actor, draft_version(draft), [
                {'path': ['paper', 'title'], 'before': '隔离测试旧标题', 'value': '迟到写入'}])
        assert staged.draft['paper']['title'] == '隔离测试新标题'


def test_partial_results_and_failure_are_reused_by_strict_gate(current_mysql):
    snap = snapshot()
    first, second = snap['records']
    with current_mysql.begin() as db:
        science.save_results(db, snap, {first['key']: {'status': 'supported'}, second['key']: {
            'status': 'unsupported', 'reason': '值不对应', 'resolution': '人工说明不能绕过'}}, 7)
    with current_mysql.begin() as db:
        cached = science.load_results(db, snap, 7)
        from backend.ingest.field_review import needs_review
        assert not any(needs_review(r, cached[r['key']]) for r in snap['records'])
        with pytest.raises(Exception) as failure:
            ev.resolve_results(snap, cached, 7, None, snap['version'], manual_pending_keys={second['key']})
        assert failure.value.detail['code'] == 'evidence_review_required'
        assert [r['key'] for r in failure.value.detail['records']] == [second['key']]


@pytest.mark.skipif(not os.environ.get('SCWIKI_SOURCE_TASK'), reason='需指定只读基线草稿')
@pytest.mark.parametrize('field_kind', ['paper', 'dos'])
def test_real_draft_local_save_budget_without_evidence_reads(current_mysql, monkeypatch, field_kind):
    from backend.ingest import upload_tasks
    from backend import database
    original = os.environ['SCWIKI_SOURCE_TASK']
    draft, state = upload_tasks.get_draft(original), upload_tasks.get_state(original)
    target = 'test147-' + uuid.uuid4().hex
    actor = SimpleNamespace(id=int(state['user_id']), role='user', username='isolated-performance')
    client = upload_tasks.redis_client()
    state = {**state, 'id': target, 'task_id': target, '_field_change_events': []}
    client.setex(upload_tasks.task_key(target), 600, json.dumps(state))
    client.setex(upload_tasks.draft_key(target), 600, json.dumps(draft))
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    snap = snapshot(); snap['target_id'] = target
    with current_mysql.begin() as db:
        science.save_results(db, snap, {snap['records'][0]['key']: {'status': 'supported'}}, actor.id)
    monkeypatch.setattr(ev, 'complete_snapshot', lambda *a, **k: pytest.fail('局部保存构造了科学快照'))
    monkeypatch.setattr(ev, 'locate_with_reason', lambda *a, **k: pytest.fail('局部保存读取了旧证据'))
    monkeypatch.setattr(science, 'load_results', lambda *a, **k: pytest.fail('局部保存读取了核对历史'))
    durations = []
    try:
        for index in range(12):
            before = upload_tasks.get_draft(target)
            if field_kind == 'paper':
                path, title = ['paper', 'title'], before['paper']['title']
            else:
                candidates = [(state, module, record) for state in before['material_states']
                    for module in state['property_modules'] for record in module['records']
                    if record.get('property_code') == 'dos_fermi']
                assert candidates
                state, module, record = candidates[0]
                title = record['name_raw']
                path = ['material_states', {'key': 'state_key', 'value': state['state_key']},
                        'property_modules', {'key': 'module_key', 'value': module['module_key']},
                        'records', {'key': 'record_key', 'value': record['record_key']}, 'name_raw']
            start = perf_counter()
            with current_mysql.begin() as db:
                result = save_fields(db, 'upload', target, actor, draft_version(before), [
                    {'path': path, 'before': title, 'value': title + '.'}])
            durations.append(perf_counter() - start)
            assert result['changed']
        p95 = sorted(durations)[-1]  # 12次样本取保守的最大值。
        print('FIELD_SAVE_PERFORMANCE', json.dumps({'field_kind': field_kind, 'samples': durations, 'p95_seconds': p95,
              'full_snapshot_calls': 0, 'evidence_history_reads': 0, 'model_calls': 0}))
        assert p95 < 1.0
        assert upload_tasks.get_draft(original) == draft
    finally:
        client.delete(upload_tasks.task_key(target), upload_tasks.draft_key(target))
