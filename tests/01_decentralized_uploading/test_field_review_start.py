"""主动字段核对：草稿令牌、实际模型输入、持久结果复用的接口边界。"""
import json
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.api import evidence as api
from backend.ingest import field_drafts, field_review, property_evidence as ev, scientific_evidence as science


@pytest.fixture
def review_api(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    models.ScientificEvidenceCheck.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    draft = {'paper': {'title': 'LaScH', 'year': 2026}, 'material_states': []}
    user = SimpleNamespace(id=7, role='user')
    monkeypatch.setattr(api, 'SessionLocal', factory)
    monkeypatch.setattr(field_drafts, 'authorized_draft', lambda *a, **k: (deepcopy(draft), None))
    monkeypatch.setattr(field_drafts, 'target_lock', lambda *a: nullcontext())
    monkeypatch.setattr(api, 'get_state', lambda *a: {})
    from backend.ingest import field_source_metadata
    monkeypatch.setattr(field_source_metadata, 'manifest', lambda *a: [])
    def snapshot(*args):
        return ev.complete_snapshot('upload', 'task', ev.draft_records(draft, {}),
            [{'file_id': 'main', 'chunk_index': 0, 'content': 'LaScH'}], draft), {}
    monkeypatch.setattr(api, 'snapshot_for', snapshot)
    queued = []
    client = SimpleNamespace(eval=lambda *a: '', setex=lambda *a: queued.append(a))
    monkeypatch.setattr(api, 'redis_client', lambda: client)
    monkeypatch.setattr(api, 'get_llm_config', lambda: SimpleNamespace(api_key='test', model='test'))
    monkeypatch.setattr(api, 'save_llm_config', lambda *a: None)
    monkeypatch.setattr(ev, 'write_job_control', lambda *a: None)
    monkeypatch.setattr(api, 'upload_queue', lambda: SimpleNamespace(enqueue=lambda *a, **k: None))
    yield draft, user, queued, snapshot
    engine.dispose()


def test_summary_token_starts_one_field_job_and_science_token_stays_distinct(review_api):
    draft, user, queued, snapshot = review_api
    summary = api.field_summary(api.Target(target='upload', target_id='task'), user)
    key = next(r['key'] for r in summary['records'] if r['field'] == 'paper.title')
    assert summary['version'] != snapshot()[0]['version']
    # 旧前端把草稿版本当科学版本发送，确实在排队前就失败，未调用模型。
    with pytest.raises(HTTPException):
        api.create_job(api.Target(target='upload', target_id='task', expected_version=summary['version'],
                                  purpose='field', retry_keys=[key]), user)
    assert not queued
    result = api.create_job(api.Target(target='upload', target_id='task', expected_draft_version=summary['version'],
                                      purpose='field', retry_keys=[key]), user)
    assert result['status'] == 'queued'
    job = json.loads(queued[0][2])
    assert job['requested_keys'] == [key]
    assert job['snapshot']['draft_version_token'] == summary['version']
    assert job['snapshot']['version'] != summary['version']
    draft['paper']['title'] = '另一窗口改过'
    with pytest.raises(HTTPException):
        api.create_job(api.Target(target='upload', target_id='task', expected_draft_version=summary['version'],
                                  purpose='field', retry_keys=[key]), user)
    assert len(queued) == 1


def test_change_during_snapshot_cannot_bind_old_claim_to_new_draft(review_api, monkeypatch):
    draft, user, queued, snapshot = review_api
    summary = api.field_summary(api.Target(target='upload', target_id='task'), user)
    key = next(r['key'] for r in summary['records'] if r['field'] == 'paper.title')
    def concurrent_snapshot(*args):
        result = snapshot()
        draft['paper']['title'] = '并发修改'
        return result
    monkeypatch.setattr(api, 'snapshot_for', concurrent_snapshot)
    with pytest.raises(HTTPException):
        api.create_job(api.Target(target='upload', target_id='task', expected_draft_version=summary['version'],
                                  purpose='field', retry_keys=[key]), user)
    assert not queued


@pytest.mark.parametrize('assessment,status,expected', [('reasonable', 'supported', 'supported'),
    ('questionable', 'supported', 'missing'), ('reasonable', 'unsupported', 'missing')])
def test_model_explicitly_judges_absence_reason_and_does_not_invent_paper_evidence(monkeypatch, assessment, status, expected):
    from backend.rag import llm
    record = {'key': 'mu', 'item_key': 'mu', 'field': 'mu_star', 'fields': ['mu_star'],
              'claim': {'value': 0.1}, 'current_value': 0.1, 'evidences': [], 'content_hash': 'value', 'source_hash': 'source'}
    reason = '按原始表格的等价写法，0.10 与 0.1 是同一数值，适用范围保持一致'
    context = {'mu': {'decisions': [{'reason': '仅调整等价表示', 'no_evidence_reason': '未增加新科学事实，无新增附件'}], 'items': []}}
    def complete(system, prompt, **kwargs):
        assert json.loads(prompt)['human_provided_evidence'] == context
        return {'results': [{'key': 'mu', 'status': status, 'reason': reason, 'evidences': [],
            'manual_reason_review': {'status': assessment, 'explanation': reason}}]}
    monkeypatch.setattr(llm, 'complete_json', complete)
    evaluated = ev.evaluate_batch([record], [], 'field', human_context=context)
    result = ev.aggregate_candidates([record], {'mu': evaluated}, {'mu': []}, 'test')['mu']
    assert result['status'] == expected
    assert result['evidences'] == []
    assert not result.get('human_confirmed')
    if expected == 'supported':
        assert result['source_kind'] == 'model_reasoning'
        assert not field_review.needs_review(record, {**record, **result})


def test_submit_reuses_persisted_field_pass_without_enqueuing_again(review_api):
    _, user, queued, snapshot = review_api
    snap, _ = snapshot()
    record = next(r for r in snap['records'] if r['field'] == 'paper.title')
    snap['records'] = [record]
    result = {**record, 'status': 'supported', 'source_kind': 'model_reasoning', 'stored_result': True,
              'reason': '本次模型认可当前字段及说明', 'evidences': []}
    with api.SessionLocal.begin() as session:
        session.add(models.ScientificEvidenceCheck(target='upload', target_id='task', item_key=record['item_key'],
            content_hash=record['content_hash'], source_hash=record['source_hash'], rule_version=snap['rule_version'],
            result=result, resolutions={}, actor_user_id=user.id))
    with api.SessionLocal() as session:
        cached = science.load_results(session, snap, user.id)
    response = api.enqueue_review(api.Target(target='upload', target_id='task', purpose='submit',
        expected_version=snap['version']), user, snap, cached)
    assert response['status'] == 'completed'
    assert response['records'][0]['status'] == 'supported'
    assert not queued


def test_submit_96_passes_only_enqueues_4_changes_and_does_not_retry_scientific_failure(review_api, monkeypatch):
    _, user, queued, snapshot = review_api
    snap, _ = snapshot()
    template = snap['records'][0]
    snap['records'] = [{**template, 'key': str(i), 'item_key': str(i), 'field': 'paper.field' + str(i),
        'fields': ['paper.field' + str(i)], 'content_hash': 'value' + str(i), 'current_value': 'after', 'required': True} for i in range(100)]
    snap['_field_change_events'] = [{'item_key': str(i), 'before_value': 'before'} for i in range(96, 100)]
    cached = {r['key']: {**r, 'status': 'supported', 'stored_result': True} for r in snap['records'][:96]}
    monkeypatch.setattr(api.manual, '_current', lambda *a: SimpleNamespace(reason='修改理由', items=[], no_evidence_reason='依据已存原文，无新增附件'))
    body = api.Target(target='upload', target_id='task', purpose='submit', expected_version=snap['version'])
    assert api.enqueue_review(body, user, snap, cached)['status'] == 'queued'
    assert json.loads(queued[0][2])['requested_keys'] == ['96', '97', '98', '99']
    cached.update({r['key']: {**r, 'status': 'unsupported' if r['key'] == '99' else 'supported', 'stored_result': True} for r in snap['records'][96:]})
    assert api.enqueue_review(body, user, snap, cached)['status'] == 'completed'
    assert len(queued) == 1
    with pytest.raises(HTTPException):
        ev.resolve_results(snap, cached, user.id, None, snap['version'])


def test_missing_manual_reason_blocks_before_model_configuration(review_api, monkeypatch):
    _, user, queued, snapshot = review_api
    snap, _ = snapshot()
    row = snap['records'][0]
    snap['records'] = [row]
    snap['_field_change_events'] = [{'item_key': row['item_key'], 'before_value': 'old'}]
    monkeypatch.setattr(api.manual, '_current', lambda *a: None)
    monkeypatch.setattr(api, 'get_llm_config', lambda: pytest.fail('缺少人工理由时不应启动模型'))
    with pytest.raises(HTTPException) as failure:
        api.enqueue_review(api.Target(target='upload', target_id='task', purpose='field', expected_version=snap['version'], retry_keys=[row['key']]), user, snap, {})
    assert failure.value.detail['issues'][0]['message'] == '请填写人工修改理由'
    assert not queued


@pytest.mark.parametrize('issue,expected', [('已纠正角色；只保存新候选供人工比较', 'supported'), ('其他真实冲突', 'uncertain')])
def test_explicit_model_review_resolves_only_the_old_candidate_marker(monkeypatch, issue, expected):
    from backend.rag import llm
    record = {'key': 'title', 'item_key': 'title', 'field': 'paper.title', 'fields': ['paper.title'],
        'claim': {'value': 'LaScH'}, 'current_value': 'LaScH', 'evidences': [],
        'generation_issue': {'code': 'conflict', 'message': issue}}
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'LaScH'}]
    monkeypatch.setattr(llm, 'complete_json', lambda *a, **k: {'results': [{'key': 'title', 'status': 'supported',
        'reason': '原文给出了当前材料名称', 'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH'}]}]})
    result = ev.evaluate_batch([record], chunks, 'field')[0]
    assert result['status'] == expected
