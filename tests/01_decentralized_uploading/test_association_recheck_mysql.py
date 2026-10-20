"""真实 MySQL 保存重读；显式启用且所有测试写入由事务回滚。"""
import os
import uuid
import pytest

from backend.ingest import property_evidence as ev, scientific_evidence as science
from test_scientific_evidence_mysql import current_mysql
from test_association_recheck import setup, snapshot, grid, evaluate

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式启用事务回滚 MySQL 验证')


def test_real_persistence_keeps_renewal_and_invalidates_changed_value(current_mysql, monkeypatch):
    draft = setup(legacy=True); snap = snapshot(draft); snap['target_id'] = uuid.uuid4().hex
    row = grid(snap); _, results = evaluate(monkeypatch, snap)
    with current_mysql.begin() as db:
        science.save_results(db, snap, results, 7)
    with current_mysql.begin() as db:
        reopened = ev.public_snapshot(snap, science.load_results(db, snap, 7))
        assert grid(reopened)['status'] == 'supported'
        assert not grid(reopened)['source_associations'][0]['stale']
        assert grid(reopened)['association_review']['previous_associations'][0]['stale']
        science.save_results(db, snap, results, 7)
    draft['material_states'][0]['property_modules'][0]['records'][0]['payload']['calculation_conditions']['k_grid'] = '12×12×12'
    changed = snapshot(draft); changed['target_id'] = snap['target_id']
    with current_mysql.begin() as db:
        reopened = ev.public_snapshot(changed, science.load_results(db, changed, 7, include_stale=True))
        assert grid(reopened)['stale']
        assert grid(reopened)['source_associations'][0]['stale']


def test_recheck_preserves_current_human_decision_and_previous_review(current_mysql, monkeypatch):
    from copy import deepcopy
    snap = snapshot(setup(legacy=True)); snap['target_id'] = uuid.uuid4().hex
    row = grid(snap); _, results = evaluate(monkeypatch, snap)
    decision = {'accepted': True, 'human_confirmed': True, 'actor_user_id': 7,
                'reason': '用户核对当前原文后保留网格', 'final_content_hash': row['content_hash'],
                'source_hash': row['source_hash']}
    initial = deepcopy(results)
    initial[row['key']]['decision'] = decision
    with current_mysql.begin() as db:
        science.save_results(db, snap, initial, 7)
    changed = deepcopy(results)
    changed[row['key']]['association_review']['associations'][0]['explanation'] = '本次独立重核的说明'
    with current_mysql.begin() as db:
        science.save_results(db, snap, changed, 7)
    with current_mysql.begin() as db:
        restored = grid(ev.public_snapshot(snap, science.load_results(db, snap, 7)))
        assert restored['human_confirmed'] and restored['decision'] == decision
        assert any(h.get('association_review') == results[row['key']]['association_review']
                   for h in restored['history'])


def test_new_field_binding_survives_real_draft_json_round_trip(current_mysql):
    from backend import models
    from copy import deepcopy
    draft = setup(); task_id = uuid.uuid4().hex
    expected = deepcopy(draft)
    with current_mysql.begin() as db:
        science.persist_upload(db, task_id, {'user_id': 7}, draft)
    with current_mysql.begin() as db:
        restored = db.get(models.ScientificUploadDraft, task_id).draft
        assert restored == expected
        r = restored['material_states'][0]['property_modules'][0]['records'][0]
        r.update(value_min=280, value_raw='280–311')
        assert not grid(snapshot(restored))['source_associations'][0]['stale']
