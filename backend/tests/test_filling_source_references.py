"""整理模型引用共享原文，宿主保留完整证据和服务器来源元数据。"""
from copy import deepcopy
import json

from backend.ingest.scientific_form_filling import fill_scientific_forms
import pytest


def test_filling_references_sources_and_keeps_provenance_outside_model_patch():
    quote = 'The DOS of CaH6 at 150 GPa is 0.1 states/eV/f.u.'
    evidence = {'file_id': 'main', 'block_id': 'body', 'pdf_page': 1, 'quote': quote}
    record = {'record_key': 'r', 'property_code': 'dos_fermi', 'record_type': 'property',
        'module_code': 'electronic_properties', 'definition_version': 1, 'name_raw': 'DOS at EF',
        'value_kind': 'number', 'value_number': .1, 'evidences': [evidence],
        'payload': {'dos_fermi_sources': {'version': 1, 'records': [
            {'module_code': 'electronic_properties', 'record_type': 'property', 'property_code': 'dos_fermi', 'value_number': .1,
             'value_raw': '0.1', 'payload': {}, 'evidences': [evidence], 'server_provenance': 'kept'}]}}}
    states = [{'state_key': 's', 'material': 'CaH6', 'property_modules': [
        {'module_key': 'm', 'module_code': 'electronic_properties', 'records': [record]}]}]
    before = deepcopy(states)
    def model(_prompt, body):
        request = json.loads(body)
        candidate = request['candidates'][0]
        source_value = candidate['record']['payload']['dos_fermi_sources']['records'][0]
        assert source_value['value_number'] == .1 and 'server_provenance' not in source_value
        assert source_value['evidences'] == [{'evidence_id': 'evidence-0'}]
        reference = next(iter(request['candidate_evidences'].values()))
        assert set(reference) == {'source_id', 'quote_span'}
        source = next(s for s in request['sources'] if s['source_id'] == reference['source_id'])
        a, b = reference['quote_span']; assert source['content'][a:b] == quote
        return {'done': True, 'records': [{'candidate_ids': [candidate['candidate_id']],
            'group': None, 'method': None, 'values': {'value_kind': 'number', 'value_number': .1,
                'value_raw': '0.1', 'unit_raw': 'states/eV/f.u.', 'canonical_unit': 'states/eV/f.u.'},
            'source_ids': [source['source_id']], 'reason': '原文支持同一DOS值'}], 'excluded': [], 'unresolved': []}
    values, report = fill_scientific_forms(states, [{'file_id': 'main', 'block_id': 'body', 'page_start': 1, 'content': quote}], model)
    assert report['status'] == 'completed' and states == before
    assert values[0]['property_modules'][0]['records'][0]['payload']['dos_fermi_sources'] == record['payload']['dos_fermi_sources']


def test_model_still_cannot_write_server_dos_archive():
    from backend.ingest.scientific_form_filling import apply_plan
    states = [{'property_modules': [{'records': [{'record_key': 'r', 'record_type': 'property',
        'property_code': 'dos_fermi'}]}]}]
    response = {'done': True, 'records': [{'candidate_ids': ['s0:m0:r0'], 'reason': '尝试写宿主档案',
        'values': {'dos_fermi_sources': {'version': 1, 'records': []}}}]}
    with pytest.raises(ValueError, match='结果字段或整理理由无效'):
        apply_plan(states, [], response)
