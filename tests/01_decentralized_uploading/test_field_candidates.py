"""真实 MySQL 审核存储：主动候选、人工采纳、刷新与提交零模型请求。"""
from copy import deepcopy
from types import SimpleNamespace
import os

import pytest
from fastapi import HTTPException

from test_field_decisions_mysql import context, current_mysql
from test_field_review_start import review_api
from backend.api import evidence as api
from backend.ingest import field_candidates as candidates, field_drafts, field_review
from backend.ingest import property_evidence as ev, scientific_evidence as science, upload_tasks

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅显式启用本机回滚测试')


def seed_candidate(context, *, approve=True):
    target, actor, draft, state, snap, record, factory = context
    if approve:
        view = api.field_detail('upload', target, record['item_key'], user=actor)
        api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
            action='approve', review_token=view['review_token']), actor)
    fresh = {'status': 'unsupported', 'reason': '主动模型新意见，不推翻已有人工决定',
             'model': 'isolated-model', 'review_started_at': '2099-01-01T00:00:00Z',
             'proposal': {'values': {'': 'LaScH under pressure'}, 'basis_kind': 'paper_inference',
                          'explanation': '依据本文标题与压力研究范围，归纳为新的展示标题。',
                          'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH'}], 'supported': False}}
    fresh['field_candidate'] = candidates.capture(record, fresh, fresh['review_started_at'])
    with factory.begin() as db:
        science.save_results(db, snap, {record['key']: fresh}, actor.id)
    return api.field_detail('upload', target, record['item_key'], user=actor)


def forbid_models(monkeypatch):
    import backend.rag.llm as llm
    monkeypatch.setattr(llm, 'complete_json', lambda *a, **kw: pytest.fail('不可调用模型'))
    monkeypatch.setattr(api, 'get_llm_config', lambda: pytest.fail('不可准备模型配置'))


def test_candidate_survives_approval_and_apply_reuses_new_version(context, monkeypatch):
    target, actor, draft, state, snap, record, factory = context
    view = seed_candidate(context)
    assert view['record']['human_confirmed'] and view['record']['status'] == 'supported'
    assert view['candidate']['can_apply'] and draft['paper']['title'] == 'LaScH'
    forbid_models(monkeypatch)
    body = api.FieldCandidateRequest(target='upload', target_id=target, item_key=record['item_key'], candidate_token=view['candidate']['token'])
    prepared = api.prepare_field_candidate(body, actor)
    assert api.prepare_field_candidate(body, actor) == prepared
    assert draft['paper']['title'] == 'LaScH'
    # 保存走生产 field_drafts 类型／版本／稳定路径逻辑，隔离上传缓存出口。
    def persist(task, updated, **kw):
        draft.clear(); draft.update(deepcopy(updated))
    monkeypatch.setattr(upload_tasks, 'save_draft', persist)
    with factory.begin() as db:
        field_drafts.save_fields(db, 'upload', target, actor, field_drafts.draft_version(draft), [
            {'path': ['paper', 'title'], 'before': 'LaScH', 'value': prepared['patches'][0]['values']['']}])
    request = api.FieldCandidateRequest(target='upload', target_id=target, item_key=record['item_key'], preparation_id=prepared['preparation_id'])
    interrupted = api.field_detail('upload', target, record['item_key'], user=actor)
    assert interrupted['candidate']['preparation_id'] == prepared['preparation_id']
    assert not interrupted['record']['human_confirmed']
    applied = api.finalize_field_candidate(request, actor)
    assert applied['record']['current_value'] == 'LaScH under pressure'
    assert applied['record']['ai_reason'] == view['candidate']['explanation']
    assert applied['record']['human_confirmed'] and not applied['candidate']
    again = api.finalize_field_candidate(request, actor)
    assert again['record']['field_decision'] == applied['record']['field_decision']
    reopened = api.field_detail('upload', target, record['item_key'], user=actor)
    assert reopened['record']['human_confirmed'] and reopened['candidate'] is None
    current, _ = api._manual_snapshots('upload', target, actor, record['item_key'])
    field_review.bind_support_versions(current)
    with factory() as db:
        cached = science.load_results(db, current, actor.id)
    assert not field_review.blocking(current['records'][0], cached[record['key']])
    assert api.enqueue_review(api.Target(target='upload', target_id=target, purpose='submit',
        expected_version=current['version']), actor, current, cached)['status'] == 'completed'


def test_stale_tampered_and_unauthorized_candidate_cannot_apply(context, monkeypatch):
    target, actor, draft, state, snap, record, factory = context
    view = seed_candidate(context)
    forbid_models(monkeypatch)
    body = api.FieldCandidateRequest(target='upload', target_id=target, item_key=record['item_key'], candidate_token='forged')
    with pytest.raises(HTTPException): api.prepare_field_candidate(body, actor)
    body.candidate_token = view['candidate']['token']
    with pytest.raises(HTTPException): api.prepare_field_candidate(body, SimpleNamespace(id=999999, role='user'))
    prepared = api.prepare_field_candidate(body, actor)
    request = api.FieldCandidateRequest(target='upload', target_id=target, item_key=record['item_key'], preparation_id=prepared['preparation_id'])
    # 未保存值、并发值、来源更换都不能确认。
    with pytest.raises(HTTPException): api.finalize_field_candidate(request, actor)
    draft['paper']['title'] = 'Concurrent edit'
    with pytest.raises(HTTPException): api.prepare_field_candidate(body, actor)
    with pytest.raises(HTTPException): api.finalize_field_candidate(request, actor)
    assert draft['paper']['title'] == 'Concurrent edit'


def test_legacy_candidate_is_field_local_and_resolved_one_is_hidden(context):
    target, actor, draft, state, snap, record, factory = context
    draft['generation_issues'][0]['candidate'] = 'Legacy title'
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    assert view['candidate']['historical'] and not view['candidate']['can_apply']
    api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
        action='approve', review_token=view['review_token']), actor)
    assert api.field_detail('upload', target, record['item_key'], user=actor)['candidate'] is None
    assert draft['generation_issues'][0]['candidate'] == 'Legacy title'


def test_late_candidate_does_not_override_later_human_action():
    previous = {'status': 'supported', 'field_decision': {'action': 'approve', 'occurred_at': '2026-10-28T10:00:00Z'}}
    incoming = {'field_candidate': {'id': 'late', 'origin': 'field', 'review_started_at': '2026-10-28T09:00:00Z'}}
    assert candidates.preserve_candidate(previous, incoming) == previous


def test_explicit_recheck_of_adopted_value_does_not_require_new_manual_reason(review_api, monkeypatch):
    draft, actor, queued, build = review_api
    snap, _ = build()
    record = next(r for r in snap['records'] if r['field'] == 'paper.title')
    record['human_modified'] = True
    prior = {record['key']: {**record, 'status': 'supported', 'source_kind': 'human_review',
        'field_decision': {'contract': 'field-review-v2', 'action': 'approve', 'actor_user_id': actor.id,
                          'content_hash': record['content_hash'], 'source_hash': record['source_hash']}}}
    monkeypatch.setattr(api.manual, '_current', lambda *a: pytest.fail('有效采纳后主动复核无需补人工理由'))
    result = api.enqueue_review(api.Target(target='upload', target_id='task', purpose='field',
        expected_version=snap['version'], retry_keys=[record['key']]), actor, snap, prior)
    assert result['status'] == 'queued' and len(queued) == 1


def test_projection_handles_lists_and_stable_scientific_fields():
    draft = {'paper': {'methodology': ['old']}, 'material_states': [{'state_key': 's', 'property_modules': [
        {'module_key': 'm', 'records': [{'record_key': 'r', 'payload': {'value': 1}}]}]}]}
    result = candidates.patched_draft(draft, {'field': 'paper.methodology'}, {'': ['DFT', 'SSCHA']})
    assert result['paper']['methodology'] == ['DFT', 'SSCHA']
    result = candidates.patched_draft(draft, {'field': 'material_states[0].property_modules[0].records[0].payload.value',
        'state_key': 's', 'module_key': 'm', 'record_key': 'r', 'record_field': 'payload.value'}, {'': 2})
    assert result['material_states'][0]['property_modules'][0]['records'][0]['payload']['value'] == 2
    assert draft['paper']['methodology'] == ['old']


def test_explicit_model_response_generates_candidate_for_populated_value(context, monkeypatch):
    import json
    from backend.rag import llm
    target, actor, draft, state, snap, record, factory = context
    calls = []
    def complete(system, prompt, **kwargs):
        calls.append(json.loads(prompt))
        assert '用户主动单字段核对' in system
        return {'results': [{'key': record['key'], 'status': 'supported', 'reason': '原值符合标题',
            'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH'}],
            'proposal': {'values': {'': 'LaScH study'}, 'basis_kind': 'paper_inference', 'supported': False,
                'explanation': '依据原文标题归纳，更清楚地表达研究对象。',
                'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH'}]}}]}
    monkeypatch.setattr(llm, 'complete_json', complete)
    evaluated = ev.evaluate_batch([record], snap['chunks'], 'field', {record['key']: {'auto_filled': True}})
    aggregated = ev.aggregate_candidates([record], {record['key']: evaluated}, {record['key']: []}, 'fixture', snap['chunks'])
    candidate = candidates.capture(record, aggregated[record['key']], '2099-01-01T00:00:00Z')
    assert len(calls) == 1 and calls[0]['purpose'] == 'field'
    assert candidate['values'][''] == 'LaScH study'
    assert candidate['evidences'][0]['quote'] == 'LaScH'
    assert draft['paper']['title'] == 'LaScH'


def test_new_candidate_and_source_change_reject_prepared_application(context):
    target, actor, draft, state, snap, record, factory = context
    view = seed_candidate(context)
    prepared = api.prepare_field_candidate(api.FieldCandidateRequest(target='upload', target_id=target,
        item_key=record['item_key'], candidate_token=view['candidate']['token']), actor)
    with factory.begin() as db:
        rows = candidates.proposals.rows_for(db, snap, True)
        row = next(r for r in rows if r.item_key == record['item_key'])
        updated = deepcopy(row.result)
        updated['field_candidate']['id'] = 'newer-candidate'
        row.result = updated
    draft['paper']['title'] = 'LaScH under pressure'
    request = api.FieldCandidateRequest(target='upload', target_id=target, item_key=record['item_key'], preparation_id=prepared['preparation_id'])
    with pytest.raises(HTTPException): api.finalize_field_candidate(request, actor)


@pytest.mark.parametrize('target', ['upload', 'revision', 'paper'])
@pytest.mark.parametrize('field,before,after', [('research_motivation', '1. Original motivation.', '1. New motivation.'),
                                               ('methodology', ['DFT'], ['DFT', 'SSCHA']),
                                               ('pressure_value_gpa', 167, 250)])
def test_three_hosts_real_storage_and_submit_reuse(current_mysql, monkeypatch, target, field, before, after):
    """真实 MySQL 草稿／审核行与隔离 Redis 键，使用生产保存函数，不模拟持久化。"""
    import json
    from uuid import uuid4
    from sqlalchemy import select
    from backend import database, models
    from backend.ingest import field_source_metadata as metadata
    monkeypatch.setattr(api, 'SessionLocal', current_mysql)
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    identity = uuid4().hex
    client = upload_tasks.redis_client()
    with current_mysql.begin() as db:
        users = list(db.scalars(select(models.User).where(models.User.account_status == 'active').limit(2)))
        owner = users[0]
        actor = SimpleNamespace(id=users[1].id if target == 'paper' else owner.id, role='admin' if target == 'paper' else 'user', username='candidate-fixture')
        paper = models.Paper(title='Isolated candidate integration', year=2026, content_revision=1,
                             review_status='rejected' if target == 'revision' else 'pending', uploaded_by_user_id=owner.id)
        db.add(paper); db.flush()
        target_id = str(paper.id) if target == 'paper' else identity
        draft = {'paper': {'title': paper.title, 'year': 2026, field: before}, 'material_states': [], '_field_edit_format': 1}
        numeric = field == 'pressure_value_gpa'
        path = ['paper', field]
        if numeric:
            draft['paper'].pop(field)
            draft['material_states'] = [{'state_key': 's1', 'material': 'LaSc2H24', field: before}]
            path = ['material_states', {'key': 'state_key', 'value': 's1'}, field]
        if target == 'revision':
            db.add(models.PaperRevisionDraft(revision_id=identity, paper_id=paper.id, owner_id=actor.id,
                base_revision=1, base_fingerprint='fixture', draft=draft, draft_version=1))
        elif target == 'paper':
            db.add(models.ScientificReviewDraft(paper_id=paper.id, owner_id=actor.id, base_revision=1,
                base_fingerprint='fixture', draft=draft))
        else:
            state = {'user_id': actor.id, 'stage': 'ready', 'status': 'ready', 'processing_status': 'succeeded',
                     'files': [{'file_id': 'main', 'role': 'main', 'sha256': 'fixture'}]}
            science.persist_upload(db, identity, state, draft)
            client.setex(upload_tasks.task_key(identity), 600, json.dumps(state))
            client.setex(upload_tasks.draft_key(identity), 600, json.dumps(draft))
    try:
        snap = ev.complete_snapshot(target, target_id, ev.draft_records(draft, {}),
                                    [{'file_id': 'main', 'chunk_index': 0, 'content': 'Fixture original source.'}], draft)
        record = next(r for r in snap['records'] if r['field'] == ('material_states[0].' if numeric else 'paper.') + field)
        with current_mysql.begin() as db:
            metadata.remember(db, snap, actor.id)
            source = metadata.read(db, target, target_id)
            snap, _ = metadata.field_snapshot(db, target, target_id, actor, record['item_key'], source)
            field_review.bind_support_versions(snap, db)
            record = snap['records'][0]
            result = {'status': 'supported', 'model': 'isolated', 'proposal': {'values': {'': after},
                'basis_kind': 'paper_inference', 'explanation': '模型依据本文归纳的独立候选理由', 'evidences': [], 'supported': False}}
            result['field_candidate'] = candidates.capture(record, result, '2099-01-01T00:00:00Z')
            science.save_results(db, snap, {record['key']: result}, actor.id)
        forbid_models(monkeypatch)
        view = api.field_detail(target, target_id, record['item_key'], user=actor)
        prepared = api.prepare_field_candidate(api.FieldCandidateRequest(target=target, target_id=target_id,
            item_key=record['item_key'], candidate_token=view['candidate']['token']), actor)
        with field_drafts.target_lock(target, target_id), current_mysql.begin() as db:
            current, _ = field_drafts.authorized_draft(db, target, target_id, actor)
            field_drafts.save_fields(db, target, target_id, actor, field_drafts.draft_version(current), [
                {'path': path, 'before': before, 'value': prepared['patches'][0]['values']['']}])
        applied = api.finalize_field_candidate(api.FieldCandidateRequest(target=target, target_id=target_id,
            item_key=record['item_key'], preparation_id=prepared['preparation_id']), actor)
        assert applied['record']['current_value'] == after
        with current_mysql() as db:
            stored, _ = field_drafts.authorized_draft(db, target, target_id, actor)
            assert (stored['material_states'][0] if numeric else stored['paper'])[field] == after
            if target == 'upload':
                durable = db.get(models.ScientificUploadDraft, identity).draft
                assert (durable['material_states'][0] if numeric else durable['paper'])[field] == after
            else:
                assert db.get(models.Paper, paper.id).title == paper.title
        reopened = api.field_detail(target, target_id, record['item_key'], user=actor)
        assert reopened['record']['human_confirmed'] and reopened['candidate'] is None
        snap, _ = api._manual_snapshots(target, target_id, actor, record['item_key'])
        field_review.bind_support_versions(snap)
        with current_mysql() as db: cached = science.load_results(db, snap, actor.id)
        snap, cached = field_review.prepare_submission(snap, cached)
        assert api.enqueue_review(api.Target(target=target, target_id=target_id,
            expected_version=snap['version'], purpose='submit'), actor, snap, cached)['status'] == 'completed'
    finally:
        if target == 'upload':
            client.delete(upload_tasks.task_key(identity), upload_tasks.draft_key(identity), upload_tasks.lock_key(identity))
