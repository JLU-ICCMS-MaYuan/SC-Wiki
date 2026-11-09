"""本组核对保留全局位置与他组值，模型只读取当前字段相关原文。"""
from copy import deepcopy
import json
import pytest

from backend.ingest import property_evidence as ev, model_review


@pytest.mark.parametrize('markdown_windows', [False, True])
def test_referenced_source_policy_does_not_attach_other_groups_full_text(markdown_windows):
    quote = 'The DOS at the Fermi level is 0.1 states per eV.'
    row = {'key': 'dos', 'item_key': 'dos', 'field': 'material_states[2].pressure_value_gpa',
        'kind': 'field', 'label': 'Pressure', 'current_value': 150, 'claim': {'value': 150},
        'required': True, 'evidences': [{'file_id': 'si', 'block_id': 'own', 'quote': quote}]}
    chunks = [{'file_id': 'si', 'block_id': 'own', 'chunk_index': 0, 'page_start': 2, 'content': quote},
              {'file_id': 'si', 'block_id': 'other', 'chunk_index': 1, 'page_start': 3,
               'content': 'Unrelated other material. ' * 3000}]
    if markdown_windows:
        for chunk in chunks: chunk.pop('block_id')
    snap = ev.complete_snapshot('upload', 'isolated', [row], chunks, {})
    requests = []
    def model(_, prompt, **_kw):
        body = json.loads(prompt); requests.append(body)
        assert [s['content'] for s in body['sources']] == [quote]
        assert body['source_index']  # 未读原块仍可查找，不删除必要上下文。
        return {'results': [{'key': 'dos', 'status': 'supported', 'reason': '固定响应验证当前字段独立读取原块。',
            'source_ids': [body['sources'][0]['source_id']], 'basis_kind': 'paper_quote'}]}
    result = model_review.review_fields(snap['records'], snap['chunks'], model=model, source_policy='referenced')
    assert result['dos']['status'] == 'supported' and len(requests) == 1


def test_scoped_review_preserves_unselected_states_and_global_field_paths(monkeypatch):
    draft = {'_form_contract_version': 1, 'paper': {'research_materials': ['Reviewed calcium hydrides']},
        'material_states': [{'state_key': f's{i}', 'material': f'CaH{i+2}',
            'pressure_value_gpa': i * 50, 'property_modules': []} for i in range(4)]}
    original = deepcopy(draft); calls = []
    def rebuild(current):
        records = [r for r in ev.draft_records(current, {}) if r.get('state_key') == 's2']
        return ev.complete_snapshot('upload', 'isolated', records, [], current)
    def review(records, chunks, **options):
        calls.extend(deepcopy(records))
        assert options['source_policy'] == 'referenced'
        return {r['key']: model_review.bind_result(r, {'status': 'uncertain', 'evidences': [],
            'reason': '本测试验证分组身份，不构造科学支持结论'}, chunks) for r in records}
    monkeypatch.setattr(model_review, 'review_fields', review)
    values, snapshot, _, _ = model_review.review_draft(draft, rebuild, state_keys=['s2'], preserve_paper=True)
    assert calls and all(r.get('state_key') == 's2' for r in calls)
    assert all(r['field'].startswith('material_states[2]') for r in snapshot['records'])
    assert values['paper'] == original['paper']
    assert [values['material_states'][i] for i in (0,1,3)] == [original['material_states'][i] for i in (0,1,3)]
