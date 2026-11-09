"""#198/#224：优化关联读完整科学正文，定位身份由程序持有，技术错误不能冒充科学疑点。"""
from copy import deepcopy
import hashlib
import json

import pytest


def candidate():
    return [{'material_states': [{'material': 'H', 'state_kind': 'theoretical',
        'structure_optimization': 'unknown', 'pressure_value_gpa': 100, 'property_modules': []}]}]


def test_model_request_failure_is_not_scientific_uncertainty():
    from backend.ingest.state_optimization import resolve_candidates
    from backend.ingest.model_runtime import ModelRequestError
    def fail(*_):
        raise ModelRequestError('必要原文超过预算')
    with pytest.raises(ModelRequestError):
        resolve_candidates(candidate(), [{'file_id': 'main', 'content': 'Original text'}], fail)


@pytest.mark.parametrize('method_quote', [
    'Static DFT structural optimization was performed for H.',
    'All the generated structures are optimized to their local minima by using DFT calculations.',
    'We optimized a number of low-enthalpy structures using static DFT.',
])
def test_only_verified_program_locators_are_projected_and_original_quotes_bind(method_quote):
    from backend.ingest.state_optimization import resolve_candidates
    block, literal = 'b' * 64, 'c' * 64
    original = (f'<!-- page: 1 -->\n<!-- block: {block} -->\n'
                f'{method_quote}\n\n'
                f'<!-- block: {literal} -->\nH at 100 GPa.\n')
    sources = [{'file_id': 'main', 'content': original}]
    snapshot, audits = deepcopy(sources), []
    def model(_, content):
        request = json.loads(content)
        assert f'<!-- block: {block} -->' not in request['sources'][0]['content']
        assert f'<!-- block: {literal} -->' in request['sources'][0]['content']
        assert '<!-- page: 1 -->' in request['sources'][0]['content']
        return {'workflows': [{'id': 'w', 'material': 'H', 'optimization': 'classical_static',
            'evidences': [{'workflow_source_id': 'workflow-source-0'}]}],
            'assignments': [{'target': '0/0', 'optimization': 'classical_static', 'workflow_id': 'w',
                'reason': '原文静态DFT几何优化', 'evidences': [{'source_index': 0, 'quote': 'H at 100 GPa.'}]}]}
    result, issues = resolve_candidates(candidate(), sources, model,
        source_blocks={'main': {block}}, on_request=audits.append)
    assert sources == snapshot and not issues
    assert audits[0]['original']['sources'] == sources
    assert result[0]['material_states'][0]['structure_optimization'] == 'classical_static'
    evidence = result[0]['material_states'][0]['field_evidence']['structure_optimization']
    assert all(item['file_id'] == 'main' and item['quote'] in original for item in evidence)


def test_large_program_locator_payload_reaches_model_without_losing_scientific_text():
    from backend.ingest.state_optimization import resolve_candidates
    blocks = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(4000)]
    paragraphs = [f'H at 100 GPa; original scientific source row {i}.' for i in range(4000)]
    original = '\n\n'.join(f'<!-- block: {block} -->\n{paragraph}'
                           for block, paragraph in zip(blocks, paragraphs))
    calls = []
    def model(_, content):
        calls.append(content)
        assert len(content) <= 450000
        from backend.ingest.context_encoding import decode_context
        data = json.loads(content)
        if data.get('_context_encoding'): data = decode_context(data)
        assert all(paragraph in data['sources'][0]['content'] for paragraph in paragraphs)
        return {'workflows': [], 'assignments': [{'target': '0/0', 'optimization': 'unknown',
            'workflow_id': None, 'reason': '未报告几何优化', 'evidences': []}]}
    _, issues = resolve_candidates(candidate(), [{'file_id': 'main', 'content': original}], model,
                                  source_blocks={'main': set(blocks)})
    assert len(calls) == 1
    assert not any(issue['code'] == 'scope_too_large' for issue in issues)
