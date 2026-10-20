"""关联失效必须局部化；重新核对只为有当前证据的字段生成新版本。"""
from copy import deepcopy
import json
from contextlib import nullcontext

import pytest
from fastapi import HTTPException

from backend.ingest import property_evidence as ev
from backend.ingest import scientific_evidence as science
from backend.ingest.association_review import (
    association_id, bind_field, checked_review, snapshot_association,
)
from backend.ingest.scientific_context import apply_associations
from test_issue139_scientific_context import draft, context, candidate


def setup(basis='paper_quote', legacy=False):
    d = draft()
    apply_associations(d, [candidate(d) | {'basis_kind': basis}], context())
    record = d['material_states'][0]['property_modules'][0]['records'][0]
    if legacy:
        record['payload']['source_associations'][0].pop('field_binding', None)
        record['value_min'] = 280
    return d


def snapshot(d):
    return ev.complete_snapshot('upload', 'association-test', ev.draft_records(d, {}), context()['sources'], d)


def grid(snap):
    return next(r for r in snap['records'] if r.get('record_field') == 'payload.calculation_conditions.k_grid')


def raw_review(record, basis='paper_quote'):
    return [{'association_id': association_id(a), 'verdict': 'applicable', 'basis_kind': basis,
             'explanation': '原文明确说明全部压力下的电声耦合计算使用此网格。',
             'fact_evidences': a['fact_evidences'], 'scope_evidences': a['scope_evidences']}
            for a in record['source_associations']]


def evaluate(monkeypatch, snap, **changes):
    row = grid(snap)
    def model(prompt, payload, **kwargs):
        request = json.loads(payload)
        assert request['records'][0]['source_associations'][0]['association_id']
        return {'results': [{'key': row['key'], 'status': 'supported', 'reason': '本文明确提供网格及全部压力范围。',
            'evidences': row['evidences'], 'association_reviews': raw_review(row), **changes}]}
    monkeypatch.setattr('backend.rag.llm.complete_json', model)
    rows = ev.evaluate_batch([row], snap['chunks'])
    result = ev.aggregate_candidates([row], {row['key']: rows}, {row['key']: []}, 'test-model')
    return ev.public_snapshot({**snap, 'records': [row]}, result)['records'][0], result


def test_tc_edit_does_not_stale_grid_or_its_check_version():
    d = setup(); before = grid(snapshot(d))
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    r.update(value_min=280, value_max=320, value_raw='280–320')
    r['payload']['parameters']['mu_star'] = .15
    after = grid(snapshot(d))
    assert not after['source_associations'][0]['stale']
    assert before['content_hash'] == after['content_hash']


@pytest.mark.parametrize('change', ['grid', 'pressure', 'phase', 'software', 'approximation'])
def test_related_change_stales_only_current_binding(change):
    d = setup(); s = d['material_states'][0]; r = s['property_modules'][0]['records'][0]
    if change == 'grid': r['payload']['calculation_conditions']['k_grid'] = '12×12×12'
    if change == 'pressure': s['pressure_value_gpa'] = 200
    if change == 'phase': s['reported_space_group_symbol'] = 'Fm-3m'
    if change == 'software': r['payload']['calculation_conditions']['calculation_code'] = 'VASP'
    if change == 'approximation': r['payload']['approximation'] = 'anharmonic'
    assert grid(snapshot(d))['source_associations'][0]['stale']


def test_extension_reorder_resolves_stable_identity_not_array_index():
    d = setup(); s = d['material_states'][0]; r = s['property_modules'][0]['records'][0]
    r['payload']['calculation_conditions']['extensions'] = [
        {'key': 'electron_phonon.energy_cutoff', 'value_number': 90, 'unit_raw': 'Ry'},
        {'key': 'sscha.energy_cutoff', 'value_number': 80, 'unit_raw': 'Ry'}]
    a = deepcopy(r['payload']['source_associations'][0]); a['target_path'] = '/payload/calculation_conditions/extensions/0'
    bind_field(r, s, a)
    r['payload']['calculation_conditions']['extensions'].reverse()
    current = snapshot_association(r, s, a)
    assert not current['stale'] and current['target_path'].endswith('/1')
    r['payload']['calculation_conditions']['extensions'][1]['value_number'] = 100
    assert snapshot_association(r, s, a)['stale']


def test_range_split_preserves_common_binding():
    d = setup(); before = grid(snapshot(d))
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    second = deepcopy(r)
    for item, value, key in [(r, 281, 'r'), (second, 311, 'point-2')]:
        item.update(value_kind='number', value_min=None, value_max=None, value_number=value,
                    value_raw=str(value), record_key=key)
        item['payload']['tc_group'] = {'group_key': 'r', 'point_key': key, 'method_key': 'r'}
    d['material_states'][0]['property_modules'][0]['records'].append(second)
    after = grid(snapshot(d))
    assert not after['source_associations'][0]['stale']
    assert before['content_hash'] == after['content_hash']


def test_fresh_review_replaces_stale_association_without_mutating_draft(monkeypatch):
    d = setup(legacy=True); original = deepcopy(d); snap = snapshot(d)
    assert grid(snap)['source_associations'][0]['stale']
    result, stored = evaluate(monkeypatch, snap)
    assert result['status'] == 'supported' and not result['source_associations'][0]['stale']
    assert result['association_review']['previous_associations'][0]['stale']
    reopened = ev.public_snapshot(snapshot(d), json.loads(json.dumps(stored)))
    assert grid(reopened)['status'] == 'supported'
    assert not grid(reopened)['source_associations'][0]['stale']
    assert d == original


def test_review_cannot_promote_inference(monkeypatch):
    result, _ = evaluate(monkeypatch, snapshot(setup(basis='paper_inference', legacy=True)))
    assert result['status'] == 'uncertain'
    assert result['adopted_basis'] == 'paper_inference'
    assert not result['human_confirmed']
    assert not result['source_associations'][0]['stale']


def test_renewed_legacy_grid_survives_unrelated_tc_edit(monkeypatch):
    d = setup(legacy=True); snap = snapshot(d); _, stored = evaluate(monkeypatch, snap)
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    r.update(value_min=279, value_raw='279–311')
    current = snapshot(d)
    assert grid(current)['content_hash'] == grid(snap)['content_hash']
    restored = grid(ev.public_snapshot(current, stored))
    assert restored['status'] == 'supported'
    assert not restored['source_associations'][0]['stale']


@pytest.mark.parametrize('broken', ['missing', 'quote', 'identity', 'conflict', 'scope'])
def test_bad_review_never_renews(monkeypatch, broken):
    snap = snapshot(setup(legacy=True)); raw = raw_review(grid(snap))
    if broken == 'missing': raw = []
    if broken == 'quote': raw[0]['fact_evidences'] = [{'file_id': 'main', 'quote': 'Invented quote.'}]
    if broken == 'identity': raw[0]['association_id'] = 'wrong'
    if broken == 'conflict': raw[0]['verdict'] = 'conflict'
    if broken == 'scope': raw[0]['scope_evidences'] = []
    result, _ = evaluate(monkeypatch, snap, association_reviews=raw)
    assert result['source_associations'][0]['stale']
    assert result['status'] != 'supported'


def test_new_value_or_source_cannot_reuse_review(monkeypatch):
    snap = snapshot(setup(legacy=True)); _, stored = evaluate(monkeypatch, snap); row = grid(snap)
    for key in ['content_hash', 'source_hash']:
        changed = {**row, key: 'changed'}
        result = ev.checked_result(changed, stored[row['key']], snap['chunks'])
        assert result['source_associations'][0]['stale']


def test_explicit_conflict_in_other_window_prevents_renewal(monkeypatch):
    snap = snapshot(setup(legacy=True)); row = grid(snap)
    result, _ = evaluate(monkeypatch, snap)
    other = {**result, 'association_review': None, 'association_conflict': True, 'status': 'unsupported'}
    merged = ev.aggregate_candidates([row], {row['key']: [result, other]}, {row['key']: []}, 'model')
    assert not merged[row['key']]['association_review']
    assert ev.checked_result(row, merged[row['key']], snap['chunks'])['source_associations'][0]['stale']


def test_stale_upload_rejected_before_any_database_write(monkeypatch):
    monkeypatch.setattr('backend.ingest.upload_tasks.upload_task_lock', lambda _: nullcontext())
    monkeypatch.setattr(ev, 'upload_snapshot', lambda *args: {'version': 'new'})
    def forbidden(*args):
        pytest.fail('不得写入过期任务')
    monkeypatch.setattr(science, 'save_results', forbidden)
    with pytest.raises(HTTPException):
        ev.persist_completed_results({'target': 'upload', 'target_id': 't', 'version': 'old'}, {}, 7)


def test_repeated_read_does_not_duplicate_stale_reason():
    snap = snapshot(setup(legacy=True)); row = grid(snap)
    result = {'status': 'supported', 'reason': '原文支持。', 'evidences': row['evidences']}
    for _ in range(3): result = ev.checked_result(row, result, snap['chunks'])
    assert result['reason'].count('共用设置的旧关联需要重新核对') == 1


def test_formal_transfer_relocates_new_association_evidence(monkeypatch):
    snap = snapshot(setup(legacy=True)); row = grid(snap)
    _, stored = evaluate(monkeypatch, snap)
    result = {**row, **stored[row['key']]}
    formal = deepcopy(row)
    chunks = [{**c, 'file_id': '99'} for c in snap['chunks']]
    for a in formal['source_associations']:
        for name in ['fact_evidences', 'scope_evidences']:
            for e in a[name]: e['file_id'] = '99'
    for e in formal['evidences']: e['file_id'] = '99'
    transferred = science.transfer_result(formal, result, chunks, {'main': '99'})
    reopened = ev.checked_result(formal, transferred, chunks)
    assert reopened['status'] == 'supported'
    assert not reopened['source_associations'][0]['stale']
    assert reopened['source_associations'][0]['scope_evidences'][0]['file_id'] == '99'


def test_top_level_reviews_require_unique_server_side_owner(monkeypatch):
    snap = snapshot(setup(legacy=True)); row = grid(snap)
    response = {'results': [{'key': row['key'], 'status': 'supported', 'evidences': row['evidences']}],
                'association_reviews': raw_review(row)}
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *args, **kwargs: response)
    assert ev.evaluate_batch([row], snap['chunks'])[0]['association_review']
    duplicate = {**deepcopy(row), 'key': 'other', 'content_hash': 'different-current-value'}
    response['results'].append({**response['results'][0], 'key': 'other'})
    results = ev.evaluate_batch([row, duplicate], snap['chunks'])
    assert all(not r['association_review'] for r in results)


def test_source_ids_expand_exact_original_block_without_relaxing_quote_matching():
    snap = snapshot(setup(legacy=True)); row = grid(snap)
    raw = raw_review(row)
    raw[0]['fact_evidences'] = raw[0]['scope_evidences'] = [{'source_id': 'review-source-0'}]
    review = checked_review(row, raw, snap['chunks'])
    assert review['associations'][0]['fact_evidences'][0]['quote'] == snap['chunks'][0]['content']
    raw[0]['fact_evidences'] = [{'source_id': 'review-source-999'}]
    assert checked_review(row, raw, snap['chunks']) is None
    raw[0]['fact_evidences'] = [{'source_id': 'review-source-0', 'quote': 'model-rewritten quote'}]
    review = checked_review(row, raw, snap['chunks'])
    assert review['associations'][0]['fact_evidences'][0]['quote'] == snap['chunks'][0]['content']
    raw[0]['fact_evidences'] = [{'quote': 'model-rewritten quote'}]
    assert checked_review(row, raw, snap['chunks']) is None
