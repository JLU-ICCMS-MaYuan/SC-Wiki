from copy import deepcopy
from types import SimpleNamespace

from backend.ingest import property_evidence as ev
from backend.ingest.property_field_review import expand_property_fields
from backend.ingest.evidence_proposals import expected_claim, editable_fields
from backend.ingest.evidence_audit import append_review_event


def draft():
    return {'material_states': [{'state_key': 's', 'material': 'LaSc2H24', 'pressure_value_gpa': 150,
      'property_modules': [{'module_key': 'm', 'module_code': 'superconductive_properties', 'records': [
      {'record_key': 'r', 'record_type': 'predicted_tc', 'property_code': 'tc', 'method_code': 'isotropic_eliashberg',
       'name_raw': 'Tc', 'value_kind': 'number', 'value_number': 311, 'value_raw': '311', 'unit_raw': 'K',
       'definition_key': 'record.superconductive_properties.predicted_tc.isotropic_eliashberg', 'definition_version': 1,
       'payload': {'parameters': {'lambda_ep': 3.94, 'omega_log': 745, 'mu_star': .1},
        'calculation_conditions': {'calculation_code': 'Quantum ESPRESSO', 'k_grid': '24x24x24',
          'extensions': [{'key': 'sscha.energy_cutoff', 'value_kind': 'number', 'value_number': 80, 'unit_raw': 'Ry'},
                         {'field_key': 'manual-x', 'name_raw': '说明', 'value_kind': 'text', 'value_raw': '原文'}]}}}]}]}]}


def snapshot(d):
    return ev.complete_snapshot('upload', 'isolated', ev.draft_records(d, {}), [], d)


def leaves(d):
    return {r['record_field']: r for r in snapshot(d)['records'] if r.get('record_field')}


def test_leaf_claims_scope_dependencies_and_no_parent_grant():
    d = draft(); before = deepcopy(d); first = leaves(d)
    assert d == before
    assert len(first) == 14
    assert not any(r['kind'] == 'property' for r in snapshot(d)['records'])
    d['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters']['mu_star'] = .16
    after = leaves(d)
    assert first['payload.parameters.lambda_ep']['content_hash'] == after['payload.parameters.lambda_ep']['content_hash']
    assert first['payload.parameters.mu_star']['content_hash'] != after['payload.parameters.mu_star']['content_hash']
    d['material_states'][0]['property_modules'][0]['records'][0]['method_code'] = 'allen_dynes'
    d['material_states'][0]['property_modules'][0]['records'][0]['definition_key'] = 'record.superconductive_properties.predicted_tc.allen_dynes'
    method = leaves(d)
    assert method['value_number']['content_hash'] != after['value_number']['content_hash']
    assert method['payload.parameters.lambda_ep']['content_hash'] == after['payload.parameters.lambda_ep']['content_hash']
    d['material_states'][0]['pressure_value_gpa'] = 167
    assert leaves(d)['value_number']['content_hash'] != method['value_number']['content_hash']


def test_stable_extensions_and_shared_groups_do_not_merge_methods_or_points():
    d = draft(); r = d['material_states'][0]['property_modules'][0]['records'][0]
    first = leaves(d); r['payload']['calculation_conditions']['extensions'].reverse()
    second = leaves(d)
    assert first['payload.calculation_conditions.extensions.0']['item_key'] == second['payload.calculation_conditions.extensions.1']['item_key']
    assert first['payload.calculation_conditions.extensions.0']['content_hash'] == second['payload.calculation_conditions.extensions.1']['content_hash']
    r['payload']['tc_group'] = {'version': 1, 'group_key': 'g', 'method_key': 'a', 'point_key': 'r'}
    other = deepcopy(r); other['record_key'] = 'r2';other['value_number'] = 250;other['method_code'] = 'allen_dynes'
    other['payload']['tc_group'].update(method_key='b', point_key='r2')
    d['material_states'][0]['property_modules'][0]['records'].append(other)
    rows = snapshot(d)['records']
    assert len([x for x in rows if x.get('record_field') == 'payload.parameters.lambda_ep']) == 1
    assert len([x for x in rows if x.get('record_field') == 'method_code']) == 2
    assert len([x for x in rows if x.get('record_field') == 'value_number']) == 2


def test_single_field_proposals_and_no_default_scientific_autofill():
    d = draft(); leaf = leaves(d)['payload.parameters.mu_star']
    assert editable_fields(leaf)[0]['path'] == ''
    assert editable_fields(leaf)[0]['schema']['type'] == 'number'
    changed = expected_claim(leaf, {'': .16})
    assert changed['value'] == .16
    assert changed['context'] == leaf['claim']['context']
    empty = leaves(d)['payload.calculation_conditions.k_broadening']
    assert not empty['required']
    assert not ev._fill_empty_fields(d, empty, {'basis_kind': 'general_knowledge', 'values': {'': .02}})


def test_annotation_changes_only_own_leaf_and_new_events_are_authoritative():
    d = draft(); first = leaves(d)
    r = d['material_states'][0]['property_modules'][0]['records'][0]
    r['payload']['parameters']['field_settings'] = {'lambda_ep': {'name_raw': 'λ', 'unit_raw': '1'}}
    second = leaves(d)
    assert first['payload.parameters.lambda_ep']['content_hash'] != second['payload.parameters.lambda_ep']['content_hash']
    assert first['payload.parameters.omega_log']['content_hash'] == second['payload.parameters.omega_log']['content_hash']
    record = second['payload.parameters.lambda_ep']
    response = {'model': 'actual-test-model', 'reason': '核对原文', '_audit_action': 'ai_review', '_audit_event_id': 'run-1'}
    append_review_event(None, record, response, None, 8)
    event = response['audit_events'][0]
    assert event['actor'] == {'kind': 'ai', 'model': 'actual-test-model', 'requested_by_user_id': 8}
    assert event['occurred_at'].endswith('+00:00')
    transferred = deepcopy(response)
    append_review_event(None, record, transferred, response, 8)
    assert transferred['audit_events'] == response['audit_events']  # 转接不伪造新模型调用。
    session = SimpleNamespace(get=lambda *_: SimpleNamespace(real_name='真实姓名', username='actor'))
    human = {'decision': {'preparation_id': 'save-1', 'original_value': 3.9, 'reason': '对照原表修正'}}
    append_review_event(session, record, human, None, 9, human=True)
    assert human['audit_events'][0]['actor']['name'] == '真实姓名'
    assert human['audit_events'][0]['kind'] == 'change'


def test_explicit_range_split_keeps_field_identities_and_scientific_versions():
    d = draft();r = d['material_states'][0]['property_modules'][0]['records'][0]
    r.update(value_kind='range', value_number=None, value_min=281, value_max=311, value_raw='281–311')
    r['payload']['parameters'].pop('mu_star')
    r['payload']['parameters']['extensions'] = [{'key':'mu_star','value_kind':'range','value_min':.1,'value_max':.16}]
    before = {x['item_key']:x for x in snapshot(d)['records']if x.get('record_field')}
    points=[]
    for i,(tc,mu) in enumerate([(281,.16),(311,.1)]):
        point=deepcopy(r);point.update(record_key='r' if i==0 else 'new-point',value_kind='number',value_number=tc,value_min=None,value_max=None,value_raw=str(tc))
        point['payload']['parameters'].update(mu_star=mu,extensions=[])
        point['payload']['tc_group']={'version':1,'group_key':'r','method_key':'r','point_key':f'r:{i}'}
        point['payload']['tc_range_origin']={'value_kind':'range','value_min':281,'value_max':311}
        points.append(point)
    d['material_states'][0]['property_modules'][0]['records']=points
    after={x['item_key']:x for x in snapshot(d)['records']if x.get('record_field')}
    assert set(before)==set(after)
    for key in before:
        assert before[key]['content_hash']==after[key]['content_hash'],before[key]['record_field']


def test_saved_changes_track_actor_values_settings_without_dependency_noise():
    from backend.ingest.evidence_audit import draft_change_events
    user = SimpleNamespace(id=27, username='actual-editor')
    before = draft(); after = deepcopy(before)
    r = after['material_states'][0]['property_modules'][0]['records'][0]
    r['payload']['parameters']['mu_star'] = .16
    events = draft_change_events(before, after, user)
    assert len(events) == 1  # Tc依赖失效，但用户没有修改Tc值。
    assert events[0]['actor'] == {'kind': 'human', 'user_id': 27, 'name': 'actual-editor'}
    assert events[0]['before_value'] == .1 and events[0]['after_value'] == .16
    assert events[0]['occurred_at'].endswith('+00:00')
    assert draft_change_events(after, deepcopy(after), user) == []
    annotated = deepcopy(after)
    annotated['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters']['field_settings'] = {'lambda_ep': {'name_raw': '耦合', 'unit_raw': '1'}}
    event, = draft_change_events(after, annotated, user)
    assert event['summary'] == '修改并保存字段设置'
    assert event['after_settings']['name_raw'] == '耦合'


def test_upload_save_audit_is_server_owned_atomic_and_does_not_change_retention(monkeypatch):
    import json
    from backend.ingest import upload_tasks
    class Redis:
        def __init__(self):
            self.values = {upload_tasks.task_key('audit'): json.dumps({'user_id': 99, 'is_shadow': True}),
                           upload_tasks.draft_key('audit'): json.dumps(draft())}
            self.ttls = {}
        def get(self, key): return self.values.get(key)
        def pipeline(self, transaction):
            assert transaction
            return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def setex(self, key, ttl, value): self.values[key] = value; self.ttls[key] = ttl
        def execute(self): pass
    client = Redis();monkeypatch.setattr(upload_tasks, 'redis_client', lambda: client)
    after = draft(); after['material_states'][0]['property_modules'][0]['records'][0]['value_number'] = 310
    after['_field_change_events'] = [{'id': 'forged'}]
    upload_tasks.save_draft('audit', after, editor=SimpleNamespace(id=27, username='actual-editor'))
    state = json.loads(client.values[upload_tasks.task_key('audit')]); event, = state['_field_change_events']
    assert event['actor']['user_id'] == 27  # 不能冒用owner=99。
    assert event['before_value'] == 311 and event['after_value'] == 310
    assert client.ttls[upload_tasks.task_key('audit')] == client.ttls[upload_tasks.draft_key('audit')]
    upload_tasks.save_draft('audit', after, editor=SimpleNamespace(id=27, username='actual-editor'))
    assert json.loads(client.values[upload_tasks.task_key('audit')])['_field_change_events'] == [event]
    after['material_states'][0]['property_modules'][0]['records'][0]['value_number'] = 309
    upload_tasks.save_draft('audit', after)  # 后台调用不能伪造人工事件。
    assert json.loads(client.values[upload_tasks.task_key('audit')])['_field_change_events'] == [event]


def test_only_successful_model_evaluation_creates_ai_review_event(monkeypatch):
    record = leaves(draft())['payload.parameters.lambda_ep']
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'lambda 3.94'}]
    empty = ev.aggregate_candidates([record], {record['key']: []}, {record['key']: []}, 'actual-model')
    assert '_audit_action' not in empty[record['key']]
    monkeypatch.setattr('backend.rag.llm.complete_json', lambda *a, **kw: {'results': [
        {'key': record['key'], 'status': 'supported', 'reason': '对应原文',
         'evidences': [{'file_id': 'main', 'quote': 'lambda 3.94'}]}]})
    evaluated = ev.evaluate_batch([record], chunks)
    result = ev.aggregate_candidates([record], {record['key']: evaluated}, {record['key']: []}, 'actual-model')
    assert result[record['key']]['_audit_action'] == 'ai_review'
    assert result[record['key']]['model'] == 'actual-model'
