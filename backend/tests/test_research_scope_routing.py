from copy import deepcopy
import pytest
from backend.ingest.tc_material_scope import collect_scope, assert_allowed, is_excluded


def scope():
    return collect_scope([{'tc_materials': [{'material': 'CeH10', 'has_specific_tc': False,
        'has_range_tc': True, 'source_ids': ['s'], 'reason': '本文仅报告Tc小于56 K'}]}],
        {'s': {'file_id': 'main', 'content': 'Current study CeH10, Tc < 56 K.'}})


def test_current_paper_structure_is_not_deleted_for_range_only_tc():
    value = scope()
    assert is_excluded('CeH10', value)
    assert not is_excluded('CeH10', value, purpose='structure')
    assert_allowed([{'material': 'CeH10', 'structure': {'structure_text': 'original coordinates'}}], value)
    with pytest.raises(ValueError):
        assert_allowed([{'material': 'CeH10', 'tc_results': [{'value_number': 56}]}], value)
    assert value['materials'][0]['evidences'][0]['content'].endswith('Tc < 56 K.')


def test_tc_record_hint_does_not_change_structure_only_request_identity():
    from backend.ingest.tc_material_scope import scope_prompt
    value = scope()
    assert 'emit NO predicted_tc/measured_tc' in scope_prompt(value)
    original = scope_prompt(value, purpose='structure')
    assert 'emit NO predicted_tc/measured_tc' not in original
    assert 'retain all structures' in original


@pytest.mark.parametrize('purpose',['form','structure'])
def test_whole_paper_scope_audit_cannot_offer_other_window_as_current_extraction_source(purpose):
    from backend.ingest.tc_material_scope import scope_prompt
    value = scope()
    marker = '361a4d642b57f5ade746276252a4a9f4653d5fe4624e0ba0c55fbc1c11a920a0'
    value['excluded_materials'][0]['evidences'][0]['content'] = '<!-- block: ' + marker + ' --> Other window Tc < 56 K.'
    before = deepcopy(value)
    prompt = scope_prompt(value,purpose=purpose)
    assert marker not in prompt
    assert 'Other window' not in prompt
    if purpose=='form':assert 'CeH10' in prompt and '本文仅报告Tc小于56 K' in prompt
    assert value == before  # 完整原审计与来源保存，不在提示投影时删除。


def test_chunk_scope_rejection_precedes_success_checkpoint_and_resume_reissues_only_failure(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path / 'isolated.sqlite'))
    monkeypatch.setenv('JWT_SECRET_KEY', 'isolated-scope-test-only')
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.chunker import Chunk
    from backend.ingest.model_runtime import ModelRuntime, ModelRequestError, execution_context
    from backend.rag.structured_output import StructuredOutputError
    from backend.storage import paths
    monkeypatch.setattr(paths, 'object_mode', lambda: False)
    from backend.rag import llm, llm_context
    import json
    state = {'status': 'reading', 'execution_generation': 1}
    config = SimpleNamespace(provider='fixture', model='fixture', base_url='https://fixture.invalid')
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: config)
    monkeypatch.setattr(llm, 'get_llm_config', lambda: config)
    monkeypatch.setattr(jobs, '_chunk_result_path', lambda _t, index, _f=None: tmp_path / f'chunk-{index}.json')
    bad = {'material_states': [{'material': 'CeH10', 'tc_results': [{'value_number': 56}]}]}
    good = {'material_states': [{'material': 'CeH10', 'property_modules': []}]}
    calls = []
    def invoke(*_args, **_options):
        calls.append(1)
        return deepcopy(bad if len(calls) == 1 else good)
    monkeypatch.setattr(llm, '_complete_json', invoke)
    def runtime():
        return ModelRuntime('a' * 32, 1, tmp_path / 'runtime', lambda: dict(state),
            lambda **changes: state.update(changes), lambda: nullcontext(), identity={'model': 'fixture'})
    chunk = Chunk(content='Current paper reports Tc < 56 K.', section_name='Results', chunk_index=0,
                  paper_id=0, heading=None, token_count=10)
    source = {'tc_material_scope': scope()}
    with execution_context(runtime()), pytest.raises((StructuredOutputError, ModelRequestError)):
        jobs._read_chunk('a' * 32, chunk, source=source)
    assert not list((tmp_path / 'runtime').rglob('result.json'))
    assert list((tmp_path / 'runtime').rglob('failure-*.json'))
    with execution_context(runtime()):
        result = jobs._read_chunk('a' * 32, chunk, source=source)
    assert result['material_states'] == good['material_states']
    assert len(calls) == 2
    assert json.loads((tmp_path / 'chunk-0.json').read_text()) == result


def test_reference_relationship_is_candidate_local_not_a_formula_or_chapter_filter():
    from backend.ingest.structure_reading import _apply_structure_scope
    source = {'a': {'content': 'Other work'}, 'b': {'content': 'This work studies it independently'}}
    entries = {'cited': {'material': 'CeH10', 'source_scope': 'referenced_work', 'source_ids': ['a'], 'reason': '仅引用'},
               'studied': {'material': 'CeH10', 'source_scope': 'current_paper', 'source_ids': ['b'], 'reason': '本文结果'}}
    retained, history = _apply_structure_scope(entries, scope(), source)
    assert list(retained) == ['studied'] and history[0]['reading_id'] == 'cited'
    assert entries['cited']['source_scope'] == 'referenced_work'
    broken = deepcopy(entries); broken['cited']['source_ids'] = ['not-read']
    with pytest.raises(ValueError): _apply_structure_scope(broken, scope(), source)


def test_scientific_route_requires_explicit_conflict_and_actual_sources():
    from backend.ingest.human_question_routing import route_problem
    record = {'item_key': 'field', 'field': 'material_states[0].reported_space_group_symbol', 'content_hash': 'v', 'source_hash': 's'}
    sources = {'a': {'file_id': 'main', 'content': 'P63/mmc'}, 'b': {'file_id': 'si', 'content': 'Cc'}}
    fact = {'reason_code': 'source_conflict', 'reason': '原文两处物相矛盾', 'source_ids': ['a', 'b'],
            'checked_context': '已读取两处原文及适用压力', 'requires_human': True}
    assert route_problem(record, fact, sources)['kind'] == 'human_required'
    assert route_problem(record, {'status': 'uncertain'}, sources) is None
    assert route_problem(record, {**fact, 'review_error': 'timeout'}, sources)['kind'] == 'technical_unfinished'
    assert route_problem(record, {**fact, 'source_ids': ['fake']}, sources)['kind'] == 'technical_unfinished'
    assert route_problem(record, {'status': 'supported', 'unique': True}, sources)['kind'] == 'resolved'
    assert route_problem(record, fact, {'a': sources['a'], 'b': sources['a']})['kind'] == 'technical_unfinished'


def test_waiting_uses_existing_dependencies_and_does_not_suspend_entire_state():
    from backend.ingest.human_question_routing import dependent_records
    rows = [
        {'key': 'phase', 'item_key': 'phase', 'state_key': 's', 'field': 'reported_space_group_symbol'},
        {'key': 'tc', 'item_key': 'tc', 'state_key': 's', 'field': 'value_number', 'state_dependencies': ['reported_space_group_symbol']},
        {'key': 'note', 'item_key': 'note', 'state_key': 's', 'field': 'notes'},
        {'key': 'other', 'item_key': 'other', 'state_key': 'other', 'field': 'value_number', 'state_dependencies': ['reported_space_group_symbol']},
    ]
    assert [r['item_key'] for r in dependent_records(rows, [rows[0]])] == ['tc']
