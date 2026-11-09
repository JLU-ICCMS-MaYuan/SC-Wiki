"""跨状态不能合并的整理单元可分组；每候选的总交互上限仍为四轮。"""
from copy import deepcopy
import json

from backend.ingest.scientific_form_filling import fill_scientific_forms, validate_filling_coverage
from backend.ingest.model_memory import ContextBudgetError


def test_later_context_overflow_partitions_states_without_extra_rounds_or_identity_drift(monkeypatch):
    from backend.ingest import model_memory
    quote = 'CaH6 and CaH4 have distinct DOS values at their own pressures.'
    states = [{'state_key': 's'+str(i), 'material': material, 'property_modules': [
        {'module_key': 'm'+str(i), 'module_code': 'electronic_properties', 'records': [
            {'record_key': 'r'+str(i), 'record_type': 'property', 'property_code': 'dos_fermi',
             'value_kind': 'number', 'value_number': .1+i,
             'payload': {'dos_fermi_sources': [{'server_source': 'keep'}]},
             'evidences': [{'file_id': 'main', 'block_id': 'body', 'pdf_page': 1, 'quote': quote}]}]}]}
        for i, material in enumerate(['CaH6', 'CaH4'])]
    before = deepcopy(states)
    def prepare(request, **_kw):
        body = json.loads(request['user_prompt'])
        if len(body['candidates']) > 1 and body.get('previous_error'):
            raise ContextBudgetError('隔离测试模拟后续必要原文超限')
        return request
    monkeypatch.setattr(model_memory, 'prepare_fixed_request', prepare)
    calls = []
    def model(_prompt, content):
        body = json.loads(content); calls.append((len(body['candidates']), body['remaining_rounds']))
        if len(body['candidates']) > 1:
            return {'done': False, 'read_source_ids': [], 'search': []}
        assert body['remaining_rounds'] == 3
        return {'done': True, 'records': [], 'excluded': [], 'unresolved': [
            {'candidate_id': body['candidates'][0]['candidate_id'], 'category': 'ambiguous',
             'reason': '隔离测试保留原值供核对'}]}
    result, report = fill_scientific_forms(states, [{'file_id': 'main', 'block_id': 'body', 'content': quote, 'page_start': 1}], model)
    assert report['status'] == 'completed' and report['stop_reason'] == 'partitioned_by_state'
    assert calls == [(2, 4), (1, 3), (1, 3)]
    assert set(report['candidate_dispositions']) == {'s0:m0:r0', 's1:m0:r0'}
    assert [report['candidate_dispositions'][key]['state_index'] for key in sorted(report['candidate_dispositions'])] == [0, 1]
    assert states == before and result == before
    validate_filling_coverage(before, result, report)


def test_partition_failure_reports_actual_child_error_and_keeps_originals(monkeypatch):
    from backend.ingest import model_memory
    states = [{'property_modules': [{'records': [{'record_type': 'property', 'property_code': 'dos_fermi',
        'record_key': 'r', 'value_number': i}]}]} for i in range(2)]
    before = deepcopy(states)
    def prepare(request, **_kw):
        if len(json.loads(request['user_prompt'])['candidates']) > 1:
            raise ContextBudgetError('父请求超限')
        return request
    monkeypatch.setattr(model_memory, 'prepare_fixed_request', prepare)
    result, report = fill_scientific_forms(states, [], lambda *_: {'done': True, 'records': []})
    assert result == before == states
    assert report['status'] == 'incomplete' and report['stop_reason'] == 'invalid_response'
    assert '整理遗漏原候选' in report['issues'][0]['message']
    assert all(len(child['attempts']) == 4 for child in report['batches'])
