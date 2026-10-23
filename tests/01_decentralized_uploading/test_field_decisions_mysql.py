"""真实 MySQL 外层回滚：字段决定、详情、刷新与提交门禁共享同一结果。"""
import os
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend import models, database
from backend.api import evidence as api
from backend.ingest import field_drafts, field_source_metadata as metadata, field_review, property_evidence as ev, scientific_evidence as science, upload_tasks
from test_scientific_evidence_mysql import current_mysql

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅显式启用本机回滚测试')


def test_state_scope_persistence_and_support_validation(current_mysql):
    target=uuid4().hex
    def build(method):
        state={'state_key':'scope','material':'LaSc2H24','pressure_value_gpa':300,
               'structure_optimization':method,'material_dimensionality':'three_dimensional'}
        snap=ev.complete_snapshot('upload',target,science.state_records(state,0),[],{})
        snap['records']=[r for r in snap['records'] if r['field'].endswith('.material_dimensionality')]
        return snap
    before=build('sscha');row=before['records'][0]
    with current_mysql.begin() as db:
        field_review.bind_support_versions(before,db)
        field_review.validate_support_versions(before,db)
        science.save_results(db,before,{row['key']:{'status':'supported','reason':'原文支持 SSCHA 状态',
            'model':'test','review_started_at':'2026-10-22T00:00:00+00:00'}},7)
    with current_mysql() as db:
        restored=science.load_results(db,before,7)
        assert field_review.reusable(row,restored[row['key']])
        after=build('classical_static')
        changed=science.load_results(db,after,7,include_stale=True)
        assert changed[row['key']]['stale']
        from backend.ingest.field_decisions import detail
        assert not detail(after,changed)['can_approve']


@pytest.fixture
def context(current_mysql, monkeypatch):
    target = uuid4().hex
    actor = SimpleNamespace(id=7, role='user', username='isolated-reviewer')
    draft = {'paper': {'title': 'LaScH', 'year': 2024}, 'material_states': []}
    draft['generation_issues'] = [{'field': 'paper.title', 'code': 'conflict', 'message': '已纠正角色；只保存新候选供人工比较'}]
    state = {'user_id': actor.id, 'files': [{'file_id': 'main', 'role': 'main', 'sha256': 'source'}], '_field_change_events': []}
    monkeypatch.setattr(api, 'SessionLocal', current_mysql)
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    monkeypatch.setattr(upload_tasks, 'get_state', lambda task: state if task == target else None)
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda task: deepcopy(draft) if task == target else None)
    monkeypatch.setattr(api, 'get_state', lambda task: state if task == target else None)
    monkeypatch.setattr(field_drafts, 'target_lock', lambda *a: nullcontext())
    # 本组持久化场景使用待人工确认的必需项；默认书目信息可选免审，不能借它测试通过按钮。
    draft_records = ev.draft_records
    monkeypatch.setattr(ev, 'draft_records', lambda *a, **kw: [
        {**r, 'required': True} if r['field'] == 'paper.title' else r for r in draft_records(*a, **kw)])
    snap = ev.complete_snapshot('upload', target, ev.draft_records(draft, {}),
        [{'file_id': 'main', 'chunk_index': 0, 'content': 'LaScH'}], draft)
    with current_mysql.begin() as db:
        metadata.remember(db, snap, actor.id)
        science.save_results(db, snap, {r['key']: {'status': 'uncertain', 'reason': '已找到原文，等待人工确认',
            'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH'}]} for r in snap['records']}, actor.id)
    record = next(r for r in snap['records'] if r['field'] == 'paper.title')
    return target, actor, draft, state, snap, record, current_mysql


def test_human_approval_survives_summary_reopen_and_submission_without_model(context, monkeypatch):
    target, actor, draft, state, snap, record, factory = context
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    assert view['can_approve'] and view['source_state'] == 'available'
    assert view['record']['evidences'][0]['quote'] == 'LaScH'
    request = api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'], action='approve', review_token=view['review_token'])
    monkeypatch.setattr(api, 'get_llm_config', lambda: pytest.fail('人工通过与复用不应读取模型配置'))
    result = api.save_field_decision(request, actor)
    assert result['record']['status'] == 'supported'
    assert not result['can_approve']
    assert result['record']['field_decision']['actor_user_id'] == actor.id
    assert result['record']['resolved_generation_issue']['message'] == '已纠正角色；只保存新候选供人工比较'
    assert result['record']['reason'] == '已找到原文，等待人工确认'
    again = api.save_field_decision(request, actor)
    assert again['record']['field_decision'] == result['record']['field_decision']
    summary = api.field_summary(api.Target(target='upload', target_id=target), actor)
    summary_record = next(r for r in summary['records'] if r['key'] == record['key'])
    assert summary_record['status'] == 'supported' and summary_record['human_confirmed']
    assert not summary_record['pending_review']
    assert not api.field_detail('upload', target, record['item_key'], user=actor)['can_approve']
    history = api.field_detail('upload', target, record['item_key'], history=True, user=actor)
    events = history['history'][0]['audit_events']
    assert sum(e.get('kind') == 'human_review' for e in events) == 1
    with factory() as db:
        cached = science.load_results(db, snap, actor.id)
    one = {**snap, 'records': [record]}
    assert not field_review.blocking(record, cached[record['key']])
    assert api.enqueue_review(api.Target(target='upload', target_id=target, purpose='submit', expected_version=snap['version']), actor, one, cached)['status'] == 'completed'
    assert ev.resolve_results(one, cached, actor.id, None, snap['version'])[0]['status'] == 'supported'
    assert draft['paper']['title'] == 'LaScH'


def test_machine_pass_cannot_be_approved_but_can_be_rejected(context):
    target, actor, draft, state, snap, record, factory = context
    with factory.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'reason': '模型已核对'}}, actor.id)
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    assert not view['can_approve']
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
            action='approve', review_token=view['review_token']), actor)
    rejected = api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
        action='reject', review_token=view['review_token']), actor)
    assert rejected['record']['field_decision']['action'] == 'reject'
    assert rejected['can_approve']


def test_reject_blocks_without_change_and_stale_token_cannot_approve(context):
    target, actor, draft, state, snap, record, factory = context
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    rejected = api.save_field_decision(api.FieldDecision(target='upload', target_id=target,
        item_key=record['item_key'], action='reject', review_token=view['review_token']), actor)
    assert rejected['record']['field_decision']['action'] == 'reject'
    with factory() as db:
        cached = science.load_results(db, snap, actor.id)
    with pytest.raises(HTTPException):
        ev.resolve_results({**snap, 'records': [record]}, cached, actor.id, None, snap['version'])
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
            action='approve', review_token=view['review_token']), actor)
    draft['paper']['title'] = 'changed'
    state['_field_change_events'] = [{'item_key': record['item_key'], 'before_value': 'LaScH'}]
    modified = api.field_detail('upload', target, record['item_key'], user=actor)
    assert not modified['can_approve']
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
            action='approve', review_token=modified['review_token']), actor)
    assert draft['paper']['title'] == 'changed'


def test_unrelated_edit_does_not_invalidate_field_and_wrong_user_cannot_decide(context):
    target, actor, draft, state, snap, record, factory = context
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    draft['paper']['year'] = 2025
    request = api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'], action='approve', review_token=view['review_token'])
    with pytest.raises(HTTPException) as error:
        api.save_field_decision(request, SimpleNamespace(id=actor.id + 1, role='user'))
    assert error.value.status_code == 403
    assert api.save_field_decision(request, actor)['record']['status'] == 'supported'


def test_late_model_cannot_replace_human_decision(context):
    target, actor, draft, state, snap, record, factory = context
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'], action='reject', review_token=view['review_token']), actor)
    with factory.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'model': 'late', 'review_started_at': '2026-01-01T00:00:00Z'}}, actor.id)
    latest = api.field_detail('upload', target, record['item_key'], user=actor)
    assert latest['record']['field_decision']['action'] == 'reject'
    with factory.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'model': 'explicit', 'review_started_at': '2099-01-01T00:00:00Z'}}, actor.id)
    assert api.field_detail('upload', target, record['item_key'], user=actor)['record']['status'] == 'supported'


def test_note_only_change_is_pending_in_summary_and_cannot_reuse_machine_pass(context):
    from backend.ingest import manual_evidence
    target, actor, draft, state, snap, record, factory = context
    with factory.begin() as db:
        science.save_results(db, snap, {record['key']: {'status': 'supported', 'reason': '旧依据已经通过'}}, actor.id)
    first = api.field_summary(api.Target(target='upload', target_id=target), actor)
    first = next(r for r in first['records'] if r['key'] == record['key'])
    with factory.begin() as db:
        manual_evidence.save_explanation(db, snap, {'records': []}, record['item_key'], actor.id,
            reason='修改了用于核对的人工说明', no_evidence_reason='使用论文已有引句，没有新增附件', text_items=[])
    second = api.field_summary(api.Target(target='upload', target_id=target), actor)
    second = next(r for r in second['records'] if r['key'] == record['key'])
    assert second['pending_review'] and second['human_modified']
    assert first['detail_ref'] != second['detail_ref']
    assert not api.field_detail('upload', target, record['item_key'], user=actor)['can_approve']
