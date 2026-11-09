"""#224：重复科学结构无损传输，不能把内部引用保存为科学值。"""
import copy
import json

import pytest

from backend.ingest.context_encoding import decode_context, encode_context
from backend.ingest.model_memory import (
    _fixed_token_estimate, prepare_fixed_request, validate_context_output,
)
from backend.rag.structured_output import StructuredOutputError


def repeated_scientific_payload():
    evidence = {'file_id': 'main-pdf', 'page_start': 4, 'block_id': 'original-figure-4',
                'quote': 'ScH6 at 300 GPa: estimated Tc 99 K; mu*=0.1; precision 2 K.'}
    return {'candidates': [
        {'candidate_id': f'candidate-{i}', 'material_states': [
            {'material': 'ScH6', 'pressure': 300, 'tc': 99.0, 'mu_star': 0.1,
             'precision': 2, 'evidences': [evidence], 'uncertainty': None}
            for _ in range(12)], 'coverage_exclusions': [
                {'reason': 'Original caption contains no independent result.',
                 'evidence': evidence} for _ in range(12)]}
        for i in range(20)]}


def test_repeated_scientific_tree_fits_without_merging_records():
    payload = repeated_scientific_payload()
    request = {'system_prompt': 'Use current scientific content and actual source identities.',
               'user_prompt': json.dumps(payload), 'images': []}
    original = copy.deepcopy(request)
    prepared = prepare_fixed_request(request, budget=4500)
    assert _fixed_token_estimate(prepared) < 4500
    assert decode_context(json.loads(prepared['user_prompt'])) == payload
    assert request == original
    assert 'lossless-tree-v1' in prepared['system_prompt']


def test_large_citation_catalog_and_scientific_tree_fit_together():
    import hashlib
    from backend.ingest.state_inventory import _evidence
    sources = [{'source_id': f's{i}', 'file_id': 'f' * 32, 'file_role': 'supplementary',
                'source_sha256': 'a' * 64, 'source_version': 1,
                'block_id': hashlib.sha256(str(i).encode()).hexdigest(),
                'page_start': i // 6 + 1, 'page_end': i // 6 + 1,
                'content': f'Original source row {i}: YH10 at 400 GPa with Tc 303 K; original condition and unit retained.'}
               for i in range(180)]
    state = {'material': 'YH10', 'pressure_value_gpa': 400, 'property_modules': [
        {'record_key': 'original-point', 'value_number': 303,
         'parameters': {'mu_star': 0.1, 'lambda_ep': 2.41}, 'evidences': [sources[0]]}] * 12}
    payload = {'sources': sources, 'candidates': [
        {'candidate_id': f'c{i}', 'states': [state] * 5} for i in range(10)]}
    request = {'system_prompt': 'Read all original rows and keep candidates distinct.',
               'user_prompt': json.dumps(payload), 'response_schema': {
                   'type': 'object', 'properties': {'source_ids': {'type': 'array', 'items': {'type': 'string'}}},
                   'required': ['source_ids'], 'additionalProperties': False},
               'images': ['data:image/png;base64,UNCHANGED']}
    original = copy.deepcopy(request)
    prepared = prepare_fixed_request(request, budget=13000)
    wire = decode_context(json.loads(prepared['user_prompt']))
    catalog = wire['sources']['_context_source_catalog']
    rows = [row for group in catalog['file_groups'] for row in group['sources']]
    assert [(row['source_id'], row['content'], row['page_start']) for row in rows] == [
        (row['source_id'], row['content'], row['page_start']) for row in sources]
    assert wire['candidates'] == payload['candidates']
    bound = _evidence(['s0'], {row['source_id']: row for row in sources})[0]
    assert bound['block_id'] == sources[0]['block_id'] and bound['file_id'] == sources[0]['file_id']
    assert catalog['candidate_source_anchors'][0]['block_id'] == bound['block_id']
    assert _fixed_token_estimate(prepared) < 13000
    assert prepared['images'] == request['images'] and prepared['response_schema'] == request['response_schema']
    assert request == original


@pytest.mark.parametrize('payload', [
    None, True, 0.1, '中文 μ*=0.13', [], {},
    {'nested': [{'a': 1, 'b': None}, {'b': False, 'a': 1.0}],
     'different': [{'a': 1}, {'b': 2}], 'unicode': '中文 Å'},
    {'literal': [{'_ref': 0}, {'_rows': {'columns': ['a'], 'values': [[1]]}},
                 {'_object': {'_ref': 0}}]},
    repeated_scientific_payload(),
])
def test_whole_tree_roundtrip(payload):
    assert decode_context(encode_context(payload)) == payload


def test_short_source_identities_are_shared_without_changing_scientific_rows():
    import hashlib
    identity = hashlib.sha256(b'original-file').hexdigest()[:32]
    payload = [{'origin': identity, 'pressure': i, 'tc': 100 + i} for i in range(300)]
    encoded = encode_context(payload)
    assert decode_context(encoded) == payload
    size = _fixed_token_estimate({'user_prompt': json.dumps(encoded)})
    original_size = _fixed_token_estimate({'user_prompt': json.dumps(payload)})
    assert size < original_size / 2


@pytest.mark.parametrize('mutation', ['out_of_range', 'bool_ref', 'cycle', 'digest', 'columns', 'row'])
def test_corrupt_context_is_rejected(mutation):
    encoded = encode_context({'a': '原文' * 100, 'b': '原文' * 100})
    if mutation == 'out_of_range': encoded['data'] = {'_ref': 999}
    elif mutation == 'bool_ref': encoded['data'] = {'_ref': True}
    elif mutation == 'cycle': encoded['references'][0] = {'_ref': 0}
    elif mutation == 'digest': encoded['sha256'] = 'tampered'
    elif mutation == 'columns': encoded['data'] = {'_rows': {'columns': ['a', 'a'], 'values': [[1, 2]]}}
    elif mutation == 'row': encoded['data'] = {'_rows': {'columns': ['a', 'b'], 'values': [[1]]}}
    with pytest.raises(ValueError): decode_context(encoded)


@pytest.mark.parametrize('value', [
    {'tc': {'_ref': 0}}, {'paper': {'summary': {'_rows': {}}}},
    {'paper': {'summary': {'_object': {}}}},
    {'paper': {'summary': '{"_ref": 0}'}},
    {'paper': {'summary': {'_context_encoding': 'lossless-tree-v1'}}},
])
def test_transport_output_is_rejected_only_for_encoded_requests(value):
    request = {'user_prompt': json.dumps(encode_context({'scientific': 'original'}))}
    with pytest.raises(StructuredOutputError): validate_context_output(value, request)
    validate_context_output(value, {'user_prompt': '{"scientific": "original"}'})
    validate_context_output({'tc': 99, 'summary': '约99 K，来源图4'}, request)
