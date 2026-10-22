"""两阶段审核的字段边界、保存与复用回归。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from backend.ingest.field_drafts import apply_changes
from backend.ingest.field_review import independent_fields, content_claim, reusable, needs_review, blocking, retain_valid_pass
from backend.ingest.property_evidence import complete_snapshot


def property_parent():
    return {'key': 'parent', 'item_key': 'parent', 'kind': 'property',
            'field': 'material_states[0].property_modules[0].records[0]', 'label': 'N(EF)',
            'record_key': 'dos', 'module_key': 'electronic', 'state_key': 'state', 'evidences': [],
            'claim': {'record': {'record_type': 'generic', 'name_raw': 'N(EF)', 'value_number': 17.27,
                                 'unit_raw': 'states/eV', 'value_kind': 'number', 'payload': {}},
                      'state': {'material': 'LaScH', 'pressure_value_gpa': 300}}}


def test_name_change_does_not_change_value_unit_or_identity():
    before = property_parent()
    after = deepcopy(before)
    after['claim']['record']['name_raw'] = '电子态密度 N(EF)'
    first = {r['record_field']: r for r in complete_snapshot('upload', 'test', [before], [], {})['records']}
    second = {r['record_field']: r for r in complete_snapshot('upload', 'test', [after], [], {})['records']}
    for key in ('value_number', 'unit_raw', 'value_kind'):
        assert first[key]['content_hash'] == second[key]['content_hash']
        assert first[key]['item_key'] == second[key]['item_key']
        assert first[key]['fields'] == [first[key]['field']]
    assert first['name_raw']['content_hash'] != second['name_raw']['content_hash']
    assert first['name_raw']['item_key'] == second['name_raw']['item_key']


def test_extension_reorder_does_not_change_field_identity():
    parent = property_parent()
    parent['claim']['record']['payload']['conditions'] = {'extensions': [
        {'field_key': 'a', 'name_raw': 'A', 'value_raw': '12'},
        {'field_key': 'b', 'name_raw': 'B', 'value_raw': '24'}]}
    a = independent_fields([parent])
    parent['claim']['record']['payload']['conditions']['extensions'].reverse()
    b = independent_fields([parent])
    assert {r['item_key'] for r in a} == {r['item_key'] for r in b}


def test_patch_preserves_incomplete_input_and_addresses_stable_record():
    draft = {'material_states': [{'state_key': 's', 'property_modules': [
        {'module_key': 'm', 'records': [{'record_key': 'r2', 'value_raw': '5'}, {'record_key': 'r1', 'value_raw': '10'}]}]}]}
    result = apply_changes(draft, [{'path': ['material_states', {'key': 'state_key', 'value': 's'},
        'property_modules', {'key': 'module_key', 'value': 'm'}, 'records',
        {'key': 'record_key', 'value': 'r1'}, 'value_raw'], 'before': '10', 'value': '1e-'}])
    rows = result['material_states'][0]['property_modules'][0]['records']
    assert rows[0]['value_raw'] == '5'
    assert rows[1]['value_raw'] == '1e-'
    assert draft['material_states'][0]['property_modules'][0]['records'][1]['value_raw'] == '10'


def test_patch_rejects_concurrent_change_without_overwriting():
    draft = {'paper': {'title': 'new'}}
    with pytest.raises(HTTPException) as failure:
        apply_changes(draft, [{'path': ['paper', 'title'], 'before': 'old', 'value': 'mine'}])
    assert failure.value.status_code == 409
    assert draft['paper']['title'] == 'new'


@pytest.mark.parametrize('status', ['unsupported', 'uncertain', 'missing'])
def test_same_version_failure_blocks_without_semantic_retry(status):
    record = {'item_key': 'k', 'content_hash': 'value', 'source_hash': 'source'}
    result = {**record, 'status': status, 'resolution': '我确认', 'human_confirmed': True}
    assert reusable(record, result)
    assert not needs_review(record, result)
    assert blocking(record, result)


def test_same_version_conflicting_model_cannot_replace_valid_pass():
    record = {'item_key': 'k', 'content_hash': 'value', 'source_hash': 'source'}
    old = {**record, 'status': 'supported', 'model': 'model-a'}
    incoming = {**record, 'status': 'unsupported', 'model': 'model-b', 'reason': 'contradiction'}
    result = retain_valid_pass(record, old, incoming)
    assert result['status'] == 'supported'
    assert result['consistency_anomalies'][0]['model'] == 'model-b'
    assert 'consistency_anomalies' not in old


def test_empty_optional_human_change_needs_review_but_blank_alone_does_not():
    record = {'item_key': 'k', 'content_hash': 'empty', 'source_hash': 'source', 'required': False}
    assert not needs_review(record, None)
    assert needs_review({**record, 'human_modified': True}, None)
    assert not blocking(record, None)


@pytest.mark.parametrize('action', ['approve', 'reject'])
def test_program_quote_match_cannot_overwrite_explicit_human_decision(action):
    from backend.ingest.field_review import merge_program_results
    record = {'key': 'title', 'item_key': 'title', 'content_hash': 'value', 'source_hash': 'source',
              'field': 'paper.title', 'current_value': 'LaScH', 'required': True,
              'evidences': [{'file_id': 'main', 'chunk_index': 0, 'quote': 'LaScH', 'origin_kind': 'verified_front_matter'}]}
    result = {**record, 'status': 'supported' if action == 'approve' else 'uncertain', 'reason': '保留人工决定',
              'field_decision': {'contract': 'field-review-v2', 'action': action, 'actor_user_id': 7,
                                 'content_hash': 'value', 'source_hash': 'source'}}
    snapshot = {'records': [record], 'chunks': [{'file_id': 'main', 'chunk_index': 0, 'content': 'LaScH'}]}
    cached = {'title': result}
    merge_program_results(snapshot, cached)
    assert cached['title']['reason'] == '保留人工决定'
    assert blocking(record, cached['title']) == (action == 'reject')
    if action == 'reject':
        assert blocking({**record, 'required': False}, cached['title'])
    changed = {**record, 'source_hash': 'different'}
    assert not reusable(changed, result)
    snapshot['_field_change_events'] = [{'item_key': 'title', 'before_value': 'before'}]
    empty = {}
    merge_program_results(snapshot, empty)
    assert not empty, '人工修改不能被程序字面匹配跳过模型审核'


def test_returning_to_passed_version_reuses_without_model():
    record = {'item_key': 'k', 'content_hash': 'original', 'source_hash': 'source'}
    old = {**record, 'status': 'supported'}
    assert needs_review({**record, 'content_hash': 'modified'}, old)
    assert not needs_review(record, old)
