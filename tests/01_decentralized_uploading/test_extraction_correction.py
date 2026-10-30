"""系统草稿自纠的唯一性、原文、最终复核及人工保护。"""
from copy import deepcopy

import pytest
import os
import json

from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.extraction_correction import correct_extracted_fields
from test_scientific_evidence_mysql import current_mysql


def case():
    draft = {'paper': {}, 'material_states': [{'state_key': 's', 'material': 'CaH6', 'pressure_value_gpa': 253}]}
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'CaH6 is stable at 150 GPa.'}]
    def rebuild(value):
        s = ev.complete_snapshot('upload', 'isolated', science.state_records(value['material_states'][0], 0), chunks, value)
        s['records'] = [r for r in s['records'] if r['field'].endswith('.pressure_value_gpa')]
        return s
    snap = rebuild(draft);row = snap['records'][0]
    result = {'status': 'unsupported', 'reason': '原文为150 GPa', 'proposal': {
        'values': {'': 150}, 'basis_kind': 'paper_quote', 'supported': True, 'unique': True,
        'explanation': '同一材料状态只报告150 GPa，原提取串行。',
        'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}]}}
    def evaluate(rows, sources, *a, **kw):
        assert rows[0]['current_value'] == 150
        return [ev.checked_result(rows[0], {'status': 'supported', 'reason': '原文明确报告150 GPa，该材料状态压力一致。',
            'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}]}, sources)]
    return draft, snap, {row['key']: result}, rebuild, evaluate


def test_unique_original_answer_is_corrected_and_verified_without_mutating_input():
    draft, snap, results, rebuild, evaluate = case();before = deepcopy(draft)
    corrected, final, stored = correct_extracted_fields(snap, draft, results, rebuild=rebuild, evaluate=evaluate)
    assert draft == before and corrected['material_states'][0]['pressure_value_gpa'] == 150
    result = stored[final['records'][0]['key']]
    assert result['status'] == 'supported' and result['auto_corrected']
    assert not result.get('proposal') and not result.get('human_confirmed')
    assert all('253' not in str(r.get('evidences')) for r in stored.values())


@pytest.mark.parametrize('protected', ['human_confirmed', 'field_decision', 'human_modified', 'changed_event', 'ambiguous', 'invented', 'manual_support'])
def test_ambiguous_unverified_or_human_content_is_not_replaced(protected):
    draft, snap, results, rebuild, _ = case();row = snap['records'][0];result = results[row['key']]
    if protected == 'human_confirmed':result['human_confirmed'] = True
    if protected == 'field_decision':result['field_decision'] = {'action': 'approve'}
    if protected == 'human_modified':row['human_modified'] = True
    if protected == 'manual_support':row['paper_source_hash'] = 'manual-support-version'
    if protected == 'changed_event':snap['_field_change_events'] = [{'item_key': row['item_key'], 'before_value': 200}]
    if protected == 'ambiguous':result['proposal']['unique'] = False
    if protected == 'invented':result['proposal']['evidences'][0]['quote'] = 'invented 150 GPa'
    corrected, _, _ = correct_extracted_fields(snap, draft, results, rebuild=rebuild,
        evaluate=lambda *a, **k: pytest.fail('不得应用候选'))
    assert corrected == draft


def test_final_check_failure_keeps_original_value():
    draft, snap, results, rebuild, _ = case()
    corrected, _, _ = correct_extracted_fields(snap, draft, results, rebuild=rebuild,
        evaluate=lambda *a, **k: [{'status': 'uncertain', 'reason': '仍有条件歧义'}])
    assert corrected == draft


def test_source_backed_unique_inference_still_requires_successful_final_review():
    draft, snap, results, rebuild, evaluate = case()
    proposal = next(iter(results.values()))['proposal']
    proposal['basis_kind'] = 'paper_inference'
    corrected, final, stored = correct_extracted_fields(snap, draft, results, rebuild=rebuild, evaluate=evaluate)
    assert corrected['material_states'][0]['pressure_value_gpa'] == 150
    assert stored[final['records'][0]['key']]['status'] == 'supported'


def test_model_absolute_field_path_is_bound_only_to_its_actual_field():
    from backend.ingest.evidence_proposals import checked_proposal
    draft, snap, results, _, _ = case();row = snap['records'][0]
    proposal = deepcopy(results[row['key']]['proposal'])
    proposal['values'] = {row['field']: 150}
    assert checked_proposal(row, proposal, snap['chunks'])['values'] == {'': 150}
    proposal['values'] = {'material_states[1].pressure_value_gpa': 150}
    assert checked_proposal(row, proposal, snap['chunks']) is None


def test_fixed_real_provider_response_binds_its_field_and_source_ids():
    from pathlib import Path
    from backend.ingest.evidence_proposals import checked_proposal
    raw = json.loads((Path(__file__).parents[1] / 'fixtures/field-review-automation/absolute-field-response.json').read_text())
    answer = raw['response']['results'][0]
    # 原供应商的完整路径；只替换供应商网络，不改其字段选择、候选及唯一性。
    draft = {'material_states': [{'state_key': 's', 'material': 'CaH6', 'pressure_value_gpa': 150,
                                 'material_dimensionality': 'two_dimensional'}]}
    sources = raw['sources']
    snap = ev.complete_snapshot('upload', 'replay', science.state_records(draft['material_states'][0], 0), sources, draft)
    row = next(r for r in snap['records'] if r['field'].endswith('material_dimensionality'))
    parsed = checked_proposal(row, answer['proposal'], sources)
    assert parsed['values'] == {'': 'three_dimensional'} and parsed['unique']
    assert [e['chunk_index'] for e in parsed['evidences']] == [3, 7]


def test_final_verification_uses_source_windows_and_combines_actual_support(monkeypatch):
    draft, _, original, _, _ = case()
    sources = [{'file_id': 'main', 'chunk_index': 0, 'content': 'Unrelated background.'},
               {'file_id': 'main', 'chunk_index': 1, 'content': 'CaH6 is stable at 150 GPa.'}]
    def rebuild(value):
        snap = ev.complete_snapshot('upload', 'windows', science.state_records(value['material_states'][0], 0), sources, value)
        snap['records'] = [r for r in snap['records'] if r['field'].endswith('pressure_value_gpa')]
        return snap
    snap = rebuild(draft);row = snap['records'][0]
    result = next(iter(original.values()))
    monkeypatch.setattr(ev, 'source_batches', lambda chunks: [[chunks[0]], [chunks[1]]])
    calls = []
    def evaluate(rows, chunks, *a, **kw):
        calls.append(chunks)
        found = '150 GPa' in chunks[0]['content']
        return [ev.checked_result(rows[0], {'status': 'supported' if found else 'missing',
            'reason': '这一窗口明确报告150 GPa，属于当前材料状态。' if found else '本窗口未提及。',
            'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}] if found else []}, chunks)]
    corrected, final, stored = correct_extracted_fields(snap, draft, {row['key']: result}, rebuild=rebuild, evaluate=evaluate)
    assert len(calls) == 2 and corrected['material_states'][0]['pressure_value_gpa'] == 150
    assert stored[final['records'][0]['key']]['status'] == 'supported'


def test_cancellation_during_final_verification_does_not_publish_correction():
    draft, snap, results, rebuild, evaluate = case();state = {'cancelled': False}
    def finishing(*args, **kwargs):
        answer = evaluate(*args, **kwargs);state['cancelled'] = True
        return answer
    with pytest.raises(InterruptedError):
        correct_extracted_fields(snap, draft, results, rebuild=rebuild, evaluate=finishing,
                                 cancelled=lambda: state['cancelled'])
    assert draft['material_states'][0]['pressure_value_gpa'] == 253


@pytest.mark.skipif(os.getenv('SCWIKI_CURRENT_MYSQL') != '1', reason='显式启用MySQL外层回滚')
def test_tc_leaf_correction_uses_published_definition_and_stable_record(current_mysql, monkeypatch):
    from backend import database
    from backend.tests.test_property_field_review import draft as property_draft
    value = property_draft()
    state = value["material_states"][0]
    state["material"] = "CaH6"
    record = state["property_modules"][0]["records"][0]
    record["canonical_unit"] = "K"
    record["payload"]["calculation_conditions"] = {}
    quote = 'At 150 GPa, isotropic Eliashberg Tc is 235 K for mu_star 0.1.'
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': quote}]
    def rebuild(draft):
        snap = ev.complete_snapshot('upload', 'leaf-correction', ev.draft_records(draft, {}), chunks, draft)
        snap['records'] = [r for r in snap['records'] if r.get('record_field') == 'value_number']
        return snap
    snap = rebuild(value);row = snap['records'][0]
    previous = {row['key']: {'status': 'unsupported', 'proposal': {'values': {'': 235},
        'basis_kind': 'paper_quote', 'supported': True, 'unique': True,
        'evidences': [{'file_id': 'main', 'quote': quote}]}}}
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    def evaluate(rows, sources, *args, **kwargs):
        assert rows[0]['current_value'] == 235 and rows[0]['record_key'] == 'r'
        return [ev.checked_result(rows[0], {'status': 'supported', 'reason': '当前压力和μ*下原文明确报告235 K。',
            'evidences': [{'file_id': 'main', 'quote': quote}]}, sources)]
    corrected, _, _ = correct_extracted_fields(snap, value, previous, rebuild=rebuild, evaluate=evaluate)
    target = corrected['material_states'][0]['property_modules'][0]['records'][0]
    assert target['value_number'] == 235
    assert target['record_key'] == 'r' and target['payload']['parameters']['mu_star'] == .1


def test_missing_redundant_quote_id_is_bound_only_to_actual_current_block():
    from backend.ingest.domain_extraction import normalize_extraction
    raw = {'extraction_version': '1', 'material_states': [{
        'scope': 'current_paper', 'material': 'CaH6', 'pressure_value_gpa': 150,
        'state_kind': 'theoretical', 'property_modules': [],
        'evidences': [{'file_id': 'main', 'pdf_page': 1, 'block_id': 'b', 'quote': None}]}]}
    before = deepcopy(raw)
    sources = {('main', 1, 'b'): 'CaH6 is stable at 150 GPa.'}
    result = normalize_extraction(raw, allowed_blocks=set(sources), allowed_quote_text=sources)
    assert raw == before
    assert result['material_states'][0]['evidences'][0]['quote'] == sources[('main', 1, 'b')]
    raw['material_states'][0]['evidences'][0]['block_id'] = 'invented'
    with pytest.raises(ValueError):
        normalize_extraction(raw, allowed_blocks=set(sources), allowed_quote_text=sources)


@pytest.mark.skipif(os.getenv('SCWIKI_CURRENT_MYSQL') != '1', reason='显式启用MySQL外层回滚')
@pytest.mark.parametrize('human', [False, True, 'approved'])
def test_generation_tool_followup_correction_persistence_and_submit_reuse(current_mysql, monkeypatch, human):
    from backend import database
    from backend.ingest import upload_jobs
    from backend.rag import llm, llm_context
    from types import SimpleNamespace
    draft, _, _, rebuild, _ = case()
    calls = []
    def snapshot(_task, _owner, *, parsing_draft):
        snap = rebuild(parsing_draft)
        if human is True:
            snap['_field_change_events'] = [{'item_key': snap['records'][0]['item_key'], 'before_value': 200}]
        return snap
    def model(system, prompt, **kwargs):
        request = json.loads(prompt);calls.append(request)
        if 'tools' in request and 'observation' not in request:
            return {'action': {'name': 'read_page', 'arguments': {'file_id': 'main', 'page': 1}}}
        row = request['records'][0]
        value = row['claim']['value']
        _, _, old, _, _ = case()
        proposal = next(iter(old.values()))['proposal']
        return {'results': [{'key': row['key'], 'status': 'supported' if value == 150 else 'unsupported',
            'reason': '原文唯一报告150 GPa；当前值应与此压力一致。',
            'evidences': [{'file_id': 'main', 'quote': 'CaH6 is stable at 150 GPa.'}],
            **({'proposal': proposal} if value != 150 else {})}]}
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    monkeypatch.setattr(ev, 'upload_snapshot', snapshot)
    monkeypatch.setattr(upload_jobs, '_ensure_not_cancelled', lambda _: None)
    monkeypatch.setattr(llm, 'complete_json', model)
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: SimpleNamespace(model='fixture', provider='fixture', base_url='local'))
    if human == 'approved':
        initial = snapshot('isolated', 2, parsing_draft=draft);r = initial['records'][0]
        with current_mysql.begin() as db:
            science.save_results(db, initial, {r['key']: {'status': 'supported', 'human_confirmed': True,
                'field_decision': {'contract': 'field-review-v2', 'action': 'approve', 'actor_user_id': 2,
                    'occurred_at': '2026-10-30T12:00:00+00:00', 'content_hash': r['content_hash'], 'source_hash': r['source_hash']}}}, 2)
    result = ev.generate_upload_suggestions('isolated', draft, 2)
    final = snapshot('isolated', 2, parsing_draft=draft)
    with current_mysql() as db:
        restored = science.load_results(db, final, 2)
    row = final['records'][0]
    assert draft['material_states'][0]['pressure_value_gpa'] == (253 if human else 150)
    if not human:
        count = len(calls)
        assert ev.resolve_results(final, restored, 2, None, final['version'])[0]['status'] == 'supported'
        assert len(calls) == count
        assert restored[row['key']]['auto_corrected']
    elif human is True:
        assert restored[row['key']]['status'] != 'supported'
    else:
        assert restored[row['key']]['field_decision']['action'] == 'approve'
