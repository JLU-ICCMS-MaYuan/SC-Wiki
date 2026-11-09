"""按现有预算分组规划，跨组归位保持记录、参数和逐项结论。"""
from copy import deepcopy
import json

import pytest

from backend.ingest.state_inventory import plan_states, FIELDS
from backend.ingest.model_memory import ContextBudgetError


def case():
    return {'paper': {'research_materials': ['Reviewed hydrides']}, 'material_states': [
        {'state_key': 's'+str(i), 'material': name, 'material_name': name, 'pressure_value_gpa': pressure,
         'state_kind': 'theoretical', 'structure_optimization': 'unknown', 'property_modules': [
             {'module_key': 'm'+str(i), 'module_code': 'superconductive_properties', 'records': [
                 {'record_key': 'r'+str(i), 'property_code': 'tc', 'value_number': value,
                  'payload': {'parameters': {'lambda_ep': i + 2.69}}}]}]}
        for i, (name, pressure, value) in enumerate([('CaH2', 100, 110), ('CaH4', 150, 235)])]}


def budget(monkeypatch):
    from backend.ingest import model_memory
    def prepare(request, **_kw):
        if len(json.loads(request['user_prompt'])['candidates']) > 1:
            raise ContextBudgetError('隔离测试预算，不改变生产预算')
        return request
    monkeypatch.setattr(model_memory, 'prepare_fixed_request', prepare)


def response(request):
    candidate = request['candidates'][0]; source = request['sources'][0]['source_id']
    shared = {key: None for key in FIELDS}
    shared.update(material='CaH8', material_name='CaH8', pressure_value_gpa=200,
                  state_kind='theoretical', structure_optimization='unknown')
    return {'states': [{'values': shared, 'source_ids': [source], 'reason': '同一完整结构来源'},
        {'values': {key: candidate.get(key) for key in FIELDS}, 'source_ids': [source], 'reason': '本组实际状态'}],
        'assignments': [{'candidate_state_key': candidate['state_key'], 'target_index': 1,
            'status': 'supported', 'source_ids': [source], 'reason': '对应本组原候选'}], 'record_assignments': []}


def test_budget_partitions_keep_all_records_and_merge_only_equal_states(monkeypatch):
    budget(monkeypatch)
    draft = case(); before = deepcopy(draft); seen = []
    def model(_prompt, body, **_kw):
        request = json.loads(body); seen.extend(c['state_key'] for c in request['candidates'])
        assert len(request['known_state_roster']) == 2
        return response(request)
    plan_states(draft, [{'file_id': 'main', 'content': 'Original complete state and structure sources.'}], model)
    assert seen == ['s0', 's1'] and len(draft['material_states']) == 3
    records = [r for s in draft['material_states'] for m in s['property_modules'] for r in m['records']]
    expected = [r for s in before['material_states'] for m in s['property_modules'] for r in m['records']]
    assert records == expected and draft['paper'] == before['paper']


def test_missing_batch_assignment_never_applies_partial_plan(monkeypatch):
    budget(monkeypatch)
    draft = case(); before = deepcopy(draft)
    def model(_prompt, body, **_kw):
        result = response(json.loads(body)); result['assignments'] = []; return result
    with pytest.raises(ValueError, match='本组候选'):
        plan_states(draft, [{'file_id': 'main', 'content': 'Original sources.'}], model)
    assert draft == before
