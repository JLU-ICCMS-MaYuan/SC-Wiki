"""授权历史修正的真实事务回滚；不修改用户目标。"""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api import evidence as api
from backend import models
from backend.ingest import scientific_evidence as science, property_evidence as ev
from backend.ingest.field_review import changed_keys
from test_field_decisions_mysql import context, current_mysql

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅本机回滚测试')
loader = importlib.util.spec_from_file_location('review_baseline_repair', Path(__file__).resolve().parents[2] / 'scripts/repair-upload-review-baseline.py')
repair = importlib.util.module_from_spec(loader)
loader.loader.exec_module(repair)


def test_authorized_baseline_preserves_history_and_future_edits_still_require_review(context, monkeypatch):
    target, actor, draft, state, snap, record, factory = context
    old_event = {'id': 'original-edit', 'kind': 'field_change', 'item_key': record['item_key'],
                 'before_value': 'Original', 'after_value': 'LaScH'}
    state['_field_change_events'] = [old_event]
    snap['_field_change_events'] = deepcopy(state['_field_change_events'])
    before_draft = deepcopy(draft)
    assert changed_keys(snap) == {record['item_key']}
    with factory.begin() as db:
        cached = science.load_results(db, snap, actor.id, include_stale=True)
        updated, count = repair.apply_records(db, snap, cached, state, actor, {record['item_key']})
    assert count == 1 and updated['_field_change_events'][0] == old_event
    state.clear(); state.update(updated)
    after = {**snap, '_field_change_events': state['_field_change_events']}
    assert not changed_keys(after) and draft == before_draft
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    assert view['approval_state'] == 'human_approved'
    assert not view['record']['human_modified']
    assert view['record']['field_decision']['repair_id'] == repair.REPAIR
    summary = api.field_summary(api.Target(target='upload', target_id=target), actor)
    assert not next(r for r in summary['records'] if r['item_key'] == record['item_key'])['human_modified']
    with factory.begin() as db:
        cached = science.load_results(db, after, actor.id)
        repeated, count = repair.apply_records(db, after, cached, state, actor, {record['item_key']})
        assert count == 0 and repeated == state
    one = {**after, 'records': [record]}
    monkeypatch.setattr(api, 'get_llm_config', lambda: pytest.fail('有效修正结果不能请求模型'))
    assert api.enqueue_review(api.Target(target='upload', target_id=target, purpose='submit', expected_version=one['version']), actor, one, cached)['status'] == 'completed'
    assert ev.resolve_results(one, cached, actor.id, None, one['version'])[0]['status'] == 'supported'
    draft['paper']['title'] = 'Changed again'
    state['_field_change_events'].append({'id': 'new-edit', 'kind': 'field_change', 'item_key': record['item_key'],
        'before_value': 'LaScH', 'after_value': 'Changed again'})
    view = api.field_detail('upload', target, record['item_key'], user=actor)
    assert view['approval_state'] == 'modification_required'
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target='upload', target_id=target, item_key=record['item_key'],
            action='approve', review_token=view['review_token']), actor)
    assert state['_field_change_events'][0] == old_event


def test_numeric_baseline_survives_mysql_json_precision(current_mysql):
    from sqlalchemy import select
    from types import SimpleNamespace
    from uuid import uuid4
    from backend.ingest.field_decisions import detail
    target = uuid4().hex
    raw = 120.00000000000001
    snap = ev.complete_snapshot('upload', target, [{'key': 'angle', 'item_key': 'angle',
        'field': 'structure.gamma', 'fields': ['structure.gamma'], 'label': '晶胞角度',
        'current_value': raw, 'claim': {'value': raw}, 'required': True}], [], {})
    record = snap['records'][0]
    with current_mysql.begin() as db:
        state, _ = repair.apply_records(db, snap, {}, {}, SimpleNamespace(id=7, username='fixture'), {'angle'})
    with current_mysql() as db:
        row = db.scalar(select(models.ScientificEvidenceCheck).where(models.ScientificEvidenceCheck.target_id == target))
        baseline = next(e for e in row.result['audit_events'] if e['kind'] == 'field_review_baseline')
        assert baseline['after_value'] == '120.00000000000001'
        snap['_field_change_events'] = [baseline]
        assert not changed_keys(snap)
        cached = science.load_results(db, snap, 7)
        view = detail(snap, cached)
        assert view['approval_state'] == 'human_approved' and not view['record']['pending_review']
