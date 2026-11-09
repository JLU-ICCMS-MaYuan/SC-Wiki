"""真实主入口检查回调：正常状态字典不能当成取消标志。"""
from copy import deepcopy
import hashlib
import pytest

from backend.ingest.document_ir import DocumentIR, PageGeometry


@pytest.mark.parametrize('cancel_after_entry', [False, True])
def test_normal_pdf_dispatch_reaches_chart_reading_without_false_cancel(tmp_path, monkeypatch, cancel_after_entry):
    from backend.ingest import upload_jobs as jobs, upload_tasks, paper_first, chart_reading, parsing_workflows
    from backend.storage import paths
    from backend.rag import llm_context
    from types import SimpleNamespace
    source = tmp_path / 'source.pdf'; source.write_bytes(b'%PDF-isolated')
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    task = 'f' * 32
    state = {'task_id': task, 'user_id': 1, 'status': 'queued', 'parser_profile': 'complementary',
        'file_kind': 'pdf', 'file_path': str(source), 'filename': source.name,
        'files': [{'file_id': 'main', 'role': 'main', 'kind': 'pdf', 'stored_path': str(source),
                   'sha256': sha, 'original_filename': source.name}]}
    artifact = tmp_path / 'artifacts'; (artifact / 'document_ir').mkdir(parents=True)
    ir = DocumentIR(document_id=task, source_file_id='main', source_sha256=sha,
        parse_profile='complementary', pages=[PageGeometry(pdf_page=1, width=200, height=200)])
    (artifact / 'document_ir' / 'main.json').write_text(ir.model_dump_json())
    monkeypatch.setattr(jobs, 'get_state', lambda _: deepcopy(state))
    def update(_, **changes):
        state.update(changes); return deepcopy(state)
    monkeypatch.setattr(jobs, 'update_state', update)
    monkeypatch.setattr(jobs, '_original_path', lambda _: source)
    monkeypatch.setattr(jobs, '_extract_markdown', lambda *_a: 'This is the actual source window.')
    monkeypatch.setattr(jobs, 'artifact_directory', lambda _: artifact)
    monkeypatch.setattr(jobs, 'data_path', lambda name: tmp_path / name)
    monkeypatch.setattr(jobs, 'markdown_path', lambda _: tmp_path / 'parsed_markdown' / (task + '.md'))
    monkeypatch.setattr(jobs, '_schedule_terminal_cleanup', lambda _: None)
    monkeypatch.setattr(upload_tasks, 'available_published_path', lambda _, p: p)
    monkeypatch.setattr(paper_first, 'prepare_paper', lambda *_a: {})
    monkeypatch.setattr(paths, 'object_mode', lambda: False)
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: SimpleNamespace(model='fixture'))
    monkeypatch.setattr(parsing_workflows, 'assess', lambda *_a, **_kw: {'status': 'unmatched', 'binding': None})
    observed = []
    def read_chart(_ir, path, metadata, model, **options):
        observed.append(metadata['file_id'])
        assert options['cancelled']() is False
        if cancel_after_entry:
            state['status'] = 'cancelling'
            options['cancelled']()
    monkeypatch.setattr(chart_reading, 'enrich_document', read_chart)
    assert jobs._process_upload_task(task)['status'] == ('cancelled' if cancel_after_entry else 'needs_workflow')
    assert observed == ['main']
