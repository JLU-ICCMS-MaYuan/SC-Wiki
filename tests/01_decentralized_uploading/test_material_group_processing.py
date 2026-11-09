"""材料小组串行填写/核对/保存，复用正式填写合同，不访问业务库。"""
from copy import deepcopy
import json

import pytest

from backend.ingest.material_batches import process_material_groups, MaterialBatchIncomplete


def draft_for_groups():
    quote = 'Each calcium hydride has a DOS reported for its own pressure.'
    states = [{'state_key': f's{i}', 'material': f'CaH{i+2}', 'pressure_value_gpa': i * 50,
        'property_modules': [{'module_key': f'm{i}', 'module_code': 'electronic_properties', 'records': [
            {'record_key': f'r{i}', 'module_code': 'electronic_properties', 'record_type': 'property',
             'property_code': 'dos_fermi', 'definition_version': 2, 'name_raw': 'DOS at EF',
             'value_kind': 'number', 'value_number': .1+i, 'value_raw': str(.1+i),
             'evidences': [{'file_id': 'main', 'block_id': 'body', 'pdf_page': 1, 'quote': quote}]}]}]}
        for i in range(5)]
    return {'paper': {'research_materials': ['Reviewed calcium hydrides']}, 'material_states': states}, [
        {'file_id': 'main', 'block_id': 'body', 'page_start': 1, 'content': quote}]


def model_for(events):
    def model(_prompt, content):
        body = json.loads(content)
        ids = [c['candidate_id'] for c in body['candidates']]
        events.append(('fill', ids))
        assert len(body['states']) <= 2
        return {'done': True, 'records': [{'candidate_ids': [c['candidate_id']], 'group': None,
            'method': None, 'values': {'value_kind': 'number', 'value_number': c['record']['value_number'],
                'value_raw': c['record']['value_raw'], 'canonical_unit': 'states/eV/f.u.',
                'unit_raw': 'states/eV/f.u.'}, 'source_ids': [body['sources'][0]['source_id']],
            'reason': '保留当前状态的原文DOS'} for c in body['candidates']], 'excluded': [], 'unresolved': []}
    return model


def test_real_filling_is_interleaved_with_review_and_save_and_uses_global_ids(tmp_path):
    draft, sources = draft_for_groups(); original = deepcopy(draft); events = []
    def review(current, keys):
        events.append(('review', list(keys)))
        for state in current['material_states']:
            if state['state_key'] in keys: state['note'] = 'reviewed'
        return {k: {'status': 'uncertain'} for k in keys}
    def save(current):
        events.append(('save', [s['state_key'] for s in current['material_states'] if s.get('note') == 'reviewed']))
    result = process_material_groups(draft, sources, model_for(events), review=review, save=save,
        prepare=lambda *_: [], checkpoint=tmp_path/'material-stage.json', identity={'model': 'fixture'})
    assert [e[0] for e in events] == ['fill', 'review', 'save'] * 3
    assert [e[1] for e in events if e[0] == 'fill'] == [
        ['s0:m0:r0', 's1:m0:r0'], ['s2:m0:r0', 's3:m0:r0'], ['s4:m0:r0']]
    assert [e[1] for e in events if e[0] == 'review'] == [['s0','s1'], ['s2','s3'], ['s4']]
    assert draft['paper'] == original['paper']
    assert result['filling_report']['status'] == 'completed'
    assert set(result['filling_report']['candidate_dispositions']) == {f's{i}:m0:r0' for i in range(5)}
    assert all('attempts' not in g for g in result['filling_report']['batches'])


def test_failed_group_stops_later_work_and_resume_reuses_only_saved_prefix(tmp_path):
    original, sources = draft_for_groups(); events = []
    def failed_review(current, keys):
        events.append(('review', list(keys)))
        return {k: {'status': 'unchecked', 'review_error': 'upstream_503'} for k in keys} if 's2' in keys else {}
    options = dict(save=lambda _: events.append(('save', [])), prepare=lambda *_: [],
                   checkpoint=tmp_path/'material-stage.json', identity={'model': 'fixture'})
    with pytest.raises(MaterialBatchIncomplete, match='upstream_503'):
        process_material_groups(deepcopy(original), sources, model_for(events), review=failed_review, **options)
    assert [e[1] for e in events if e[0] == 'fill'] == [['s0:m0:r0','s1:m0:r0'],['s2:m0:r0','s3:m0:r0']]
    assert len(json.loads(options['checkpoint'].read_text())['completed_groups']) == 1
    events.clear()
    process_material_groups(deepcopy(original), sources, model_for(events), review=lambda *_: {}, **options)
    assert [e[1] for e in events if e[0] == 'fill'] == [['s2:m0:r0','s3:m0:r0'],['s4:m0:r0']]
    events.clear()
    options['identity'] = {'model': 'changed'}
    process_material_groups(deepcopy(original), sources, model_for(events), review=lambda *_: {}, **options)
    assert len([e for e in events if e[0] == 'fill']) == 3


def test_single_form_over_budget_never_falls_back_to_full_draft(tmp_path, monkeypatch):
    from backend.ingest import model_memory
    from backend.ingest.model_memory import ContextBudgetError
    draft, sources = draft_for_groups(); events = []
    monkeypatch.setattr(model_memory, 'prepare_fixed_request', lambda *_a, **_k: (_ for _ in ()).throw(ContextBudgetError('必要原文仍超限')))
    with pytest.raises(MaterialBatchIncomplete, match='超限'):
        process_material_groups(draft, sources, model_for(events), review=lambda *_: events.append(('review', [])),
            save=lambda _: None, prepare=lambda *_: [], checkpoint=tmp_path/'material-stage.json', identity={})
    assert not events


def test_save_failure_cannot_mark_group_completed(tmp_path):
    draft, sources = draft_for_groups(); events = []
    def fail(_): raise OSError('save failed')
    with pytest.raises(OSError, match='save failed'):
        process_material_groups(draft, sources, model_for(events), review=lambda *_: {}, save=fail,
            prepare=lambda *_: [], checkpoint=tmp_path/'material-stage.json', identity={})
    assert len(events) == 1 and not (tmp_path/'material-stage.json').exists()


def test_stop_after_saved_group_prevents_next_request_and_source_change_invalidates_cache(tmp_path):
    original, sources = draft_for_groups(); events = []; stopped = [False]
    def progress(value):
        if value['completed_states'] == 2 and value['action'] == 'completed': stopped[0] = True
    def cancelled():
        if stopped[0]: raise InterruptedError('stopped')
    options = dict(review=lambda *_: {}, save=lambda _: None, prepare=lambda *_: [],
                   checkpoint=tmp_path/'material-stage.json', identity={})
    with pytest.raises(InterruptedError):
        process_material_groups(deepcopy(original), sources, model_for(events),
            cancelled=cancelled, on_progress=progress, **options)
    assert len(events) == 1
    changed = deepcopy(sources); changed[0]['content'] += ' Updated document version.'
    events.clear()
    process_material_groups(deepcopy(original), changed, model_for(events), **options)
    assert len(events) == 3
