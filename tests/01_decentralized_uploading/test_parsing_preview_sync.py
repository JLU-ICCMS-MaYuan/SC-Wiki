"""#195：阶段预览与题录更新相互独立，失败保留已生成的科学内容。"""
from copy import deepcopy
import json

from backend.ingest import upload_jobs as jobs


def test_summarizing_does_not_hide_already_extracted_states(tmp_path, monkeypatch):
    state = {'status': 'summarizing', 'partial_draft': {'paper': {'title': 'CaH6'}, 'material_states': []}}
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'items': [{'index': 0, 'status': 'completed', 'file_id': 'main'}]}))
    chunk = tmp_path / 'chunk.json'
    chunk.write_text(json.dumps({'material_states': [{'material': 'CaH6', 'scope': 'current_paper',
        'pressure_value_gpa': 150, 'state_kind': 'theoretical', 'property_modules': []}]}))
    monkeypatch.setattr(jobs, 'get_state', lambda _: deepcopy(state))
    monkeypatch.setattr(jobs, '_chunk_manifest_path', lambda *a, **k: manifest)
    monkeypatch.setattr(jobs, '_chunk_result_path', lambda *a, **k: chunk)
    from backend.ingest import upload_tasks
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda _, path: path)
    detail = jobs.public_parsing_detail('preview')
    assert detail['partial_draft']['material_states'][0]['material'] == 'CaH6'


def test_paper_stream_cannot_clear_scientific_preview(monkeypatch):
    from backend.ingest.upload_preview import publish_preview
    from backend.ingest import upload_tasks
    state = {'status': 'summarizing'}
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _: deepcopy(state))
    def update(_, **changes):
        state.update(deepcopy(changes))
        return deepcopy(state)
    monkeypatch.setattr(upload_tasks, 'update_state', update)
    states = [{'state_key': 's', 'material': 'CaH6', 'pressure_value_gpa': 150}]
    publish_preview('preview', states=states, phase='reviewing')
    publish_preview('preview', paper={'title': 'Late title'}, phase='assembling')
    assert state['partial_draft']['material_states'] == states
    assert state['partial_draft']['paper']['title'] == 'Late title'
    assert state['preview_phase'] == 'reviewing'
    state['status'] = 'ready'
    before = deepcopy(state)
    publish_preview('preview', paper={'title': 'Too late'}, phase='assembling')
    assert state == before


def test_failed_preview_retains_scientific_content(tmp_path, monkeypatch):
    state = {'status': 'failed', 'partial_draft': {'paper': {}, 'material_states': [{'material': 'CaH6'}]},
             'preview_phase': 'reviewing'}
    monkeypatch.setattr(jobs, 'get_state', lambda _: deepcopy(state))
    monkeypatch.setattr(jobs, '_chunk_manifest_path', lambda *a, **k: tmp_path / 'missing.json')
    from backend.ingest import upload_tasks
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda _, path: path)
    detail = jobs.public_parsing_detail('preview')
    assert detail['partial_draft'] == state['partial_draft']
    assert detail['preview_phase'] == 'reviewing'


def test_rq_worker_failure_keeps_last_published_preview(monkeypatch):
    from types import SimpleNamespace
    from backend.ingest import upload_tasks as tasks
    preview = {'paper': {'title': 'CaH6'}, 'material_states': [{'material': 'CaH6'}]}
    state = {'task_id': 'a' * 32, 'status': 'summarizing', 'stage': 'summarizing', 'partial_draft': preview}
    captured = []
    monkeypatch.setattr(tasks, 'get_state', lambda _: deepcopy(state))
    monkeypatch.setattr(tasks, 'update_state', lambda task, **changes: captured.append(changes))
    monkeypatch.setattr(tasks, 'schedule_cleanup', lambda _: None)
    monkeypatch.setattr('backend.ingest.document_shadow.refresh_comparison', lambda _: None)
    tasks.handle_upload_job_failure(SimpleNamespace(args=(state['task_id'],)), RuntimeError, RuntimeError('isolated'), None)
    assert captured[0]['partial_draft'] == preview and captured[0]['status'] == 'failed'
