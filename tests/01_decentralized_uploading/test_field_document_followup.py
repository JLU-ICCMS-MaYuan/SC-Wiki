"""模型选择本地工具→程序读取→模型判断的真实处理链，固定供应商响应。"""
from copy import deepcopy
import json

import pytest

from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.field_document_followup import follow_up_fields


def case():
    state = {'state_key': 's', 'material': 'CaH6', 'pressure_value_gpa': 150}
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'page_start': 1,
               'content': 'CaH6 is stable at 150 GPa.'},
              {'file_id': 'si', 'chunk_index': 1, 'page_start': 2, 'content': 'Additional methods.'}]
    snap = ev.complete_snapshot('upload', 'test', science.state_records(state, 0), chunks, {})
    row = next(r for r in snap['records'] if r['field'].endswith('.pressure_value_gpa'))
    result = ev.checked_result(row, {'status': 'unchecked', 'reason': '等待查证', 'evidences': []}, chunks)
    return row, chunks, {row['key']: result}


def test_reads_document_before_model_conclusion_and_keeps_other_results():
    row, chunks, prior = case()
    prior['unrelated'] = {'status': 'supported', 'reason': '不改动'}
    calls = []
    def model(system, prompt, **kw):
        request = json.loads(prompt);calls.append(request)
        if len(calls) == 1:
            return {'action': {'name': 'search_within_document', 'arguments': {'file_id': 'main', 'query': '150'}}}
        assert '150 GPa' in request['observation']['blocks'][0]['text']
        return {'results': [{'key': row['key'], 'status': 'supported', 'reason': '当前材料在150 GPa下稳定，压力值与原文一致。',
                             'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}]}]}
    result = follow_up_fields([row], prior, chunks, complete=model)
    assert result[row['key']]['status'] == 'supported'
    assert result[row['key']]['review_followup']['actions'] == 1
    assert result['unrelated'] == prior['unrelated']


def test_valid_result_never_calls_model_again():
    row, chunks, prior = case();prior[row['key']]['status'] = 'supported'
    assert follow_up_fields([row], prior, chunks, complete=lambda *a, **k: pytest.fail('重复请求')) == prior


@pytest.mark.parametrize('arguments', [{'file_id': 'other', 'page': 1},
                                     {'file_id': 'main', 'page': 1, 'path': '/etc/passwd'}])
def test_outside_sources_and_arbitrary_paths_rejected_with_finite_retries(arguments):
    row, chunks, prior = case(); calls = []
    def model(system, prompt, **kw):
        calls.append(json.loads(prompt))
        return {'action': {'name': 'read_page', 'arguments': arguments}}
    result = follow_up_fields([row], prior, chunks, complete=model)[row['key']]
    assert result['status'] != 'supported'
    assert len(calls) == 4
    assert result['review_followup']['actions'] == 3
    assert '预算' in result['reason']


def test_no_document_read_cannot_forge_supported_and_budget_is_bounded():
    row, chunks, prior = case()
    answer = {'results': [{'key': row['key'], 'status': 'supported', 'reason': '通过',
                          'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}]}]}
    result = follow_up_fields([row], prior, chunks, complete=lambda *a, **k: deepcopy(answer))[row['key']]
    assert result['status'] != 'supported'
    assert result['review_followup']['actions'] == 12


def test_technical_failure_preserves_value_and_explains_retry():
    row, chunks, prior = case()
    def model(*a, **kw):raise TimeoutError('private provider detail')
    result = follow_up_fields([row], prior, chunks, complete=model)[row['key']]
    assert result['status'] == 'unchecked' and result['review_error'] == 'TimeoutError'
    assert 'private' not in result['reason'] and '重试' in result['reason']
    assert result['current_value'] == 150


def test_followup_failure_keeps_existing_scientific_rejection():
    row, chunks, prior = case();prior[row['key']].update(status='unsupported', reason='现有科学结论不支持当前值')
    def model(*a, **kw):raise TimeoutError('isolated')
    result = follow_up_fields([row], prior, chunks, complete=model)[row['key']]
    assert result['status'] == 'unsupported'
    assert '现有科学结论' in result['reason'] and result['review_error'] == 'TimeoutError'


def test_cancellation_does_not_publish_result():
    row, chunks, prior = case()
    with pytest.raises(InterruptedError):
        follow_up_fields([row], prior, chunks, cancelled=lambda: True, complete=lambda *a, **k: {})


def test_table_tool_returns_real_cells_and_source_reference():
    row, chunks, prior = case()
    chunks[0]['content'] = '<table><tr><th>P</th><th>Tc</th></tr><tr><td>150 GPa</td><td>235 K</td></tr></table>'
    called = []
    def model(system, prompt, **kw):
        request = json.loads(prompt);called.append(request)
        if len(called) == 1:
            table = request['documents'][0]['tables'][0]
            return {'action': {'name': 'extract_table', 'arguments': {'file_id': 'main', 'table_id': table}}}
        observed = request['observation']
        assert [c['text'] for c in observed['cells']] == ['P', 'Tc', '150 GPa', '235 K']
        return {'results': [{'key': row['key'], 'status': 'supported', 'reason': '表格明确报告150 GPa，该压力属于此材料。',
                             'evidences': [{'source_id': observed['source_id']}]}]}
    result = follow_up_fields([row], prior, chunks, complete=model)
    assert result[row['key']]['status'] == 'supported'
