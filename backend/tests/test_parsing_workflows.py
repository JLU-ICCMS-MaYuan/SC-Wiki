"""文献类型判断及上传入口顺序；不调用外部模型。"""
from copy import deepcopy
from dataclasses import replace
import os

os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/scwiki-workflow-tests.db')
os.environ.setdefault('JWT_SECRET_KEY', 'test-only-secret')

import pytest
from fastapi import HTTPException

from backend.ingest import parsing_workflows as workflows


def result(**changes):
    return dict(paper_type='theoretical', theoretical_subtype='calculation',
        superconductor_kind='conventional', reason='本文计算电声耦合和材料临界温度',
        source_ids=['review-source-0'], paper={'title': 'A calculation', 'doi': None,
            'year': None, 'authors': []}, **changes)


SOURCES = [dict(file_id='main', file_role='main', content='We calculate electron phonon pairing and Tc.',
                section_role='result', chunk_index=0)]


@pytest.mark.parametrize('changes,status', [({}, 'matched'),
    ({'paper_type': 'experimental'}, 'unmatched'),
    ({'superconductor_kind': 'unknown'}, 'uncertain'),
    ({'source_ids': ['review-source-42']}, 'uncertain')])
def test_select_only_supported_scientific_scope(changes, status):
    payload = result(); payload.update(changes)
    report = workflows.assess(SOURCES, complete=lambda *_a, **_kw: payload)
    assert report['status'] == status
    assert bool(report.get('binding')) == (status == 'matched')


def test_failure_does_not_default_to_conventional():
    def failed(*_a, **_kw):
        raise RuntimeError('private provider error')
    report = workflows.assess(SOURCES, complete=failed)
    assert report['status'] == 'failed'
    assert 'private provider' not in report['reason']
    assert not report.get('binding')


def test_reference_only_and_empty_sources_do_not_match():
    assert workflows.assess([], complete=lambda *_a, **_kw: pytest.fail())['status'] == 'uncertain'
    sources = [{**SOURCES[0], 'section_role': 'reference'}]
    report = workflows.assess(sources, complete=lambda *_a, **_kw: result())
    assert report['status'] != 'matched'


def test_bindings_are_program_owned_and_exact():
    previous = {'_parsing_workflow': workflows.CURRENT.binding()}
    submitted = {'_parsing_workflow': {'workflow_key': 'forged'}}
    workflows.preserve_binding(submitted, previous)
    assert submitted == previous and submitted is not previous
    broken = deepcopy(previous); broken['_parsing_workflow']['form_version'] = 99
    with pytest.raises(HTTPException):
        workflows.require_workflow(broken)
    with pytest.raises(HTTPException):
        workflows.require_workflow({}, required=True)
    assert workflows.require_workflow({}) is None  # 历史读取不改写。


def test_copy_has_independent_identity_and_runner(monkeypatch):
    called = []
    clone = replace(workflows.CURRENT, key='isolated-test-copy',
                    runner=lambda task: called.append(task) or 'copy')
    monkeypatch.setitem(workflows.WORKFLOWS, clone.key, clone)
    assert clone.execute('copy-task') == 'copy'
    assert called == ['copy-task']
    assert clone.binding()['workflow_key'] != workflows.CURRENT.binding()['workflow_key']
    assert workflows.CURRENT.runner != clone.runner


@pytest.mark.parametrize('decision,expected', [('matched', 'ready'), ('unmatched', 'needs_workflow'),
                                            ('uncertain', 'needs_workflow'), ('failed', 'needs_workflow')])
def test_real_worker_routes_before_any_specialized_entry(tmp_path, monkeypatch, decision, expected):
    from types import SimpleNamespace
    from backend.ingest import upload_jobs, upload_tasks
    from backend.rag import llm_context
    from backend.storage import paths
    file = tmp_path / 'source.md'
    file.write_text('# Paper\n\n## Results\n\nWe calculate electron phonon coupling and Tc of a material.\n')
    state = dict(task_id='a' * 32, user_id=1, status='queued', parser_profile='legacy',
        file_kind='md', file_path=str(file), filename='source.md',
        files=[dict(file_id='main', role='main', kind='md', stored_path=str(file), original_filename='source.md')])
    calls = []
    from backend.ingest import paper_first
    def paper_stage(*_args, **_kwargs):
        calls.append(('paper_review_saved', None))
        return {'paper': {'title': 'A calculation'}, 'material_states': []}
    monkeypatch.setattr(paper_first, 'prepare_paper', paper_stage)
    monkeypatch.setattr(upload_jobs, 'get_state', lambda _id: deepcopy(state))
    def update(_id, **changes):
        state.update(deepcopy(changes)); calls.append(('state', changes.get('status')))
        return deepcopy(state)
    monkeypatch.setattr(upload_jobs, 'update_state', update)
    monkeypatch.setattr(upload_jobs, '_original_path', lambda _state: file)
    monkeypatch.setattr(upload_jobs, 'data_path', lambda name: tmp_path / name)
    monkeypatch.setattr(upload_jobs, 'markdown_path', lambda _id: tmp_path / 'parsed_markdown' / (_id + '.md'))
    (tmp_path / 'artifacts').mkdir()
    monkeypatch.setattr(upload_jobs, 'artifact_directory', lambda _id: tmp_path / 'artifacts')
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda _id, path: path)
    monkeypatch.setattr(upload_jobs, '_schedule_terminal_cleanup', lambda _id: calls.append(('cleanup', _id)))
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: SimpleNamespace(model='isolated'))
    monkeypatch.setattr(paths, 'object_mode', lambda: False)
    def model(*_args, **_kwargs):
        import json
        calls.append(('model', None))
        if decision == 'failed':
            raise RuntimeError('provider failed')
        payload = result()
        sources = json.loads(_args[1])['sources']
        payload['source_ids'] = [next(c['source_id'] for c in sources if c['section_role'] == 'result')]
        if decision == 'unmatched': payload['paper_type'] = 'experimental'
        if decision == 'uncertain': payload['superconductor_kind'] = 'unknown'
        return payload
    monkeypatch.setattr(upload_jobs, 'complete_json', model)
    def specialized(_id):
        calls.append(('specialized', None))
        assert calls.index(('paper_review_saved', None)) < calls.index(('specialized', None))
        assert state['_parsing_workflow'] == workflows.CURRENT.binding()
        assert state['workflow_assessment']['status'] == 'matched'
        return update(_id, status='ready')
    monkeypatch.setattr(upload_jobs, '_process_conventional_upload_task', specialized)
    value = upload_jobs._process_upload_task(state['task_id'])
    assert value['status'] == expected
    assert calls.count(('specialized', None)) == int(decision == 'matched')
    if decision != 'matched':
        assert value['processing_status'] == 'needs_input'
        assert value['workflow_assessment']['paper'].get('title') or decision == 'failed'
        assert (tmp_path / 'parsed_markdown' / state['task_id'] / 'main.md').read_text() == file.read_text()
        assert (tmp_path / 'artifacts' / 'workflow_assessment.json').is_file()


def test_all_windows_participate_and_final_call_failure_pauses(monkeypatch):
    from backend.ingest import property_evidence
    monkeypatch.setattr(property_evidence, 'SOURCE_BATCH_CHARS', 30)
    sources = [{**SOURCES[0], 'content': SOURCES[0]['content'] + str(i)} for i in range(3)]
    calls = []
    def model(_prompt, body, **_kwargs):
        import json
        payload = json.loads(body); calls.append(payload)
        if 'window_reports' in payload: raise RuntimeError('aggregate failed')
        return result()
    report = workflows.assess(sources, complete=model)
    assert report['status'] == 'failed'
    assert report['covered_batches'] == report['total_batches'] == 3
    assert len(calls[-1]['window_reports']) == 3


def test_aggregate_reuses_valid_window_bibliography_without_requesting_it_again(monkeypatch):
    from backend.ingest import property_evidence
    from backend.rag.structured_output import validate_output
    import json
    monkeypatch.setattr(property_evidence,'SOURCE_BATCH_CHARS',30)
    sources=[{**SOURCES[0],'content':SOURCES[0]['content']+str(i)}for i in range(2)]
    calls=[]
    def model(_prompt,body,**options):
        request=json.loads(body);calls.append(request)
        value=result();value.update(contribution_source_ids=['review-source-0'],tc_materials=[])
        if 'window_reports'in request:
            value.pop('paper')
        else:
            identity=request['sources'][0]['source_id']
            value['source_ids']=value['contribution_source_ids']=[identity]
        validate_output(value,options['response_schema'])
        return value
    report=workflows.assess(sources,complete=model)
    assert report['status']=='matched'
    assert report['paper']==result()['paper']
    assert len(calls)==3


def test_paused_task_timing_never_claims_complete():
    from backend.ingest.upload_contracts import apply_state_changes, apply_user_activity
    timing = dict(elapsed_seconds=0, started_at=10, running_since=10, finished_at=None)
    state = apply_state_changes(dict(status='extracting', extraction_timing=timing),
                                now=30, status='needs_workflow', processing_status='needs_input')
    assert state['extraction_timing'] == dict(elapsed_seconds=20, started_at=10, running_since=None, finished_at=None)
    assert apply_user_activity(state, now=50)['cleanup_at'] > state['cleanup_at']
