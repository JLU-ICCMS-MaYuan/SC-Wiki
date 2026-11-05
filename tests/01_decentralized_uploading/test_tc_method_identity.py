"""#189：真实失败的原文别名、方法关系与核对依赖。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.ingest.tc_contexts import compact_module, expand_module
from backend.ingest.tc_groups import tc_collection_issues
from backend.ingest.property_field_review import review_context


def failure_module():
    path = Path(__file__).parents[1] / 'fixtures/issue189/method-alias-failure.json'
    return json.loads(path.read_text())['state']['property_modules'][0]


def test_original_failure_preserves_all_points_spellings_sources_and_identities():
    original = failure_module()
    stored = compact_module(original)
    assert stored['metadata']['tc_contexts']['version'] == 2
    actual = expand_module(stored)
    assert actual == {**original, 'metadata': original.get('metadata', {})}
    assert [(r['value_number'], r['method_raw']) for r in actual['records'][:2]] == [
        (131, 'McMillan equation'), (114, 'McMillan')]
    assert compact_module(stored) == stored
    assert all(r['method_code'] is None for r in stored['records'])
    assert len(stored['metadata']['tc_contexts']['methods']) == 1
    view = expand_module(stored)
    before = deepcopy(view['records'][1])
    view['records'].pop(0)
    assert expand_module(compact_module(view))['records'][0] == before


def custom_module(code='other', explicit=True):
    module = failure_module()
    module['records'] = module['records'][:2]
    for index, r in enumerate(module['records']):
        r['method_code'] = code
        r['definition_key'] = f'record.superconductive_properties.predicted_tc.{code}'
        r['method_raw'] = ['Reported solver A', 'Full name of solver A'][index]
        if explicit:
            r['payload']['tc_group']['method_name'] = 'solver A'
    return module


@pytest.mark.parametrize('code', ['other', 'unknown'])
def test_explicit_nonstandard_method_keeps_own_spellings_and_common_description_once(code):
    original = custom_module(code)
    assert not tc_collection_issues(original['records'])
    stored = compact_module(original)
    assert json.dumps(stored).count('"method_name": "solver A"') == 1
    assert all('method_name' not in r['payload']['tc_group'] for r in stored['records'])
    assert expand_module(stored) == {**original, 'metadata': original.get('metadata', {})}


@pytest.mark.parametrize('code', ['other', 'unknown'])
def test_equal_generic_code_does_not_establish_same_method(code):
    wrong = custom_module(code, explicit=False)
    wrong['records'][1]['payload']['tc_group']['method_key'] = 'separate-method'
    assert not tc_collection_issues(wrong['records'])
    assert len(next(iter(compact_module(wrong)['metadata']['tc_contexts']['methods'].values()))) == 2
    assert [r['method_raw'] for r in expand_module(compact_module(wrong))['records']] == [r['method_raw'] for r in wrong['records']]


@pytest.mark.parametrize('code', ['other', 'unknown'])
def test_existing_explicit_relation_preserves_spellings_without_added_method_name(code):
    original = custom_module(code, explicit=False)
    assert not tc_collection_issues(original['records'])
    stored = compact_module(original)
    assert expand_module(stored) == {**original, 'metadata': original.get('metadata', {})}
    assert all('method_name' not in m for group in stored['metadata']['tc_contexts']['methods'].values() for m in group.values())


def test_real_method_conflict_names_both_results():
    wrong = failure_module()
    wrong['records'][1]['method_code'] = 'allen_dynes'
    a, b = [r['record_key'] for r in wrong['records'][:2]]
    with pytest.raises(ValueError) as error:
        compact_module(wrong)
    assert a in str(error.value) and b in str(error.value)


def test_clear_and_switch_common_meaning_never_erases_point_originals():
    from backend.ingest.tc_methods import write_method_value
    module = custom_module(); before = deepcopy(module)
    for r in module['records']: write_method_value(r, 'method_raw', '')
    assert [r['method_raw'] for r in module['records']] == [r['method_raw'] for r in before['records']]
    assert all(r['payload']['tc_group']['method_name'] == '' for r in module['records'])
    with pytest.raises(ValueError, match='名称'): compact_module(module)
    for r in module['records']: write_method_value(r, 'method_code', 'mcmillan')
    actual = expand_module(compact_module(module))
    assert all(r['method_code'] == 'mcmillan' for r in actual['records'])
    assert [r['method_raw'] for r in actual['records']] == [r['method_raw'] for r in before['records']]
    assert [r['evidences'] for r in actual['records']] == [r['evidences'] for r in before['records']]


def test_existing_v1_snapshot_read_is_pure_and_keeps_old_shared_name():
    old = {'metadata': {'tc_contexts': {'version': 1,
        'groups': {'g': {'parameters': {'lambda_ep': 2}, 'calculation_conditions': {}}},
        'methods': {'g': {'m': {'method_code': 'mcmillan', 'method_raw': 'Old original'}}}}},
        'records': [{'record_key': 'p', 'method_code': None, 'method_raw': None,
                     'payload': {'parameters': {'mu_star': .1},
                     'tc_context_ref': {'version': 1, 'group_key': 'g', 'method_key': 'm'}}}]}
    before = deepcopy(old)
    actual = expand_module(old)
    assert actual['records'][0]['method_raw'] == 'Old original'
    assert old == before


@pytest.mark.parametrize('path', ['method_code', 'value_number', 'payload.parameters.mu_star'])
def test_method_meaning_or_relationship_change_invalidates_related_review(path):
    r = custom_module()['records'][0]
    state = {'material': 'LaH8', 'pressure_value_gpa': 200}
    baseline = review_context(r, state, path)
    changed = deepcopy(r)
    changed['payload']['tc_group']['method_name'] = 'solver B'
    changed['method_raw'] = 'Reported solver B'
    assert review_context(changed, state, path) != baseline
    changed = deepcopy(r)
    changed['payload']['tc_group']['method_key'] = 'different-relation'
    assert review_context(changed, state, path) != baseline
    if path == 'method_code':
        changed = deepcopy(r)
        changed['value_number'] += 1
        assert review_context(changed, state, path) == baseline


def test_reference_cannot_silently_override_explicit_group_identity():
    stored = compact_module(custom_module())
    stored['records'][0]['payload']['tc_group']['method_key'] = 'wrong-reference'
    with pytest.raises(ValueError, match='引用'):
        expand_module(stored)


def test_shared_method_review_covers_second_original_and_is_not_order_dependent():
    from backend.ingest.property_field_review import expand_property_fields
    from backend.ingest.scientific_evidence import canonical
    module = failure_module()
    def method_claim(records):
        parents = []
        for index, r in enumerate(records):
            meta = r['payload']['tc_group']
            parents.append({'kind': 'property', 'key': r['record_key'], 'item_key': r['record_key'],
                'record_key': r['record_key'], 'state_key': 's', 'module_key': 'm', 'label': 'Tc',
                'tc_group_key': meta['group_key'], 'tc_method_key': meta['method_key'], 'tc_group_meta': meta,
                'field': f'material_states.0.property_modules.0.records.{index}',
                'claim': {'record': r, 'state': {'material': 'LaH8'}}, 'evidences': r.get('evidences', [])})
        method = next(x for x in expand_property_fields(parents) if x.get('record_field') == 'method_code')
        return canonical(method['claim'])
    points = module['records'][:2]
    original = method_claim(points)
    assert method_claim(list(reversed(points))) == original
    changed = deepcopy(points)
    changed[1]['method_raw'] = 'different reported name'
    assert method_claim(changed) != original
    changed = deepcopy(points)
    changed[1]['value_number'] += 1
    assert method_claim(changed) == original
    blank = deepcopy(points[0])
    blank['record_key'] = 'new-empty-point'
    blank['payload']['tc_group']['point_key'] = 'new-empty-point'
    blank['value_number'], blank['evidences'] = None, []
    assert method_claim([*points, blank]) == original


def test_existing_candidate_projection_changes_common_meaning_without_overwriting_originals():
    from backend.ingest.field_candidates import patched_draft
    module = custom_module()
    module['module_key'] = 'module'
    draft = {'paper': {}, 'material_states': [{'state_key': 'state', 'property_modules': [module]}]}
    point = module['records'][0]
    meta = point['payload']['tc_group']
    field = {'state_key': 'state', 'module_key': 'module', 'record_key': point['record_key'],
             'record_field': 'method_code', 'record_group_key': meta['group_key'],
             'record_method_key': meta['method_key']}
    result = patched_draft(draft, field, {'': 'other', 'method_raw': 'Corrected common method'})
    rows = result['material_states'][0]['property_modules'][0]['records']
    assert [r['method_raw'] for r in rows] == [r['method_raw'] for r in module['records']]
    assert {r['payload']['tc_group']['method_name'] for r in rows} == {'Corrected common method'}


@pytest.mark.parametrize('path', ['method_code', 'value_number', 'payload.parameters.mu_star'])
def test_real_snapshot_and_persisted_result_reject_changed_method_semantics(db_session, path):
    from backend.ingest import property_evidence as ev, scientific_evidence as science, field_review, field_input
    module = custom_module()
    module['module_key'] = 'module'
    draft = {'paper': {}, 'material_states': [{'state_key': 's', 'material': 'LaH8',
             'pressure_value_gpa': 300, 'property_modules': [module]}]}
    def snapshot(value):
        result = ev.complete_snapshot('upload', 'isolated-method-proof', ev.draft_records(value, {}), [], {})
        result['records'] = [r for r in result['records'] if r.get('record_field') == path][:1]
        assert len(result['records']) == 1
        field_review.bind_support_versions(result, db_session)
        return result
    before = snapshot(draft)
    record = before['records'][0]
    science.save_results(db_session, before, {record['key']: {'status': 'supported', 'reason': '隔离预置的旧方法结论',
        'field_review_binding': {'contract': field_input.CONTRACT, 'token': record['field_input_token']}}}, 1)
    db_session.flush()
    changed = deepcopy(draft)
    for r in changed['material_states'][0]['property_modules'][0]['records']:
        r['payload']['tc_group']['method_name'] = 'different solver'
    after = snapshot(changed)
    assert after['records'][0]['field_input_token'] != record['field_input_token']
    loaded = science.load_results(db_session, after, 1, include_stale=True)
    assert loaded[after['records'][0]['key']]['stale']
