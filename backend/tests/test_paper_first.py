from copy import deepcopy

from backend.ingest.paper_first import paper_conflicts, source_windows
import json
from types import SimpleNamespace
import pytest


def test_material_discovery_cannot_overwrite_reviewed_paper():
    paper = {'research_materials': ['CaH6'], 'summary': 'Reviewed original result.'}
    before = deepcopy(paper)
    differences = paper_conflicts(paper, [{'material': 'CaH6'}, {'material': 'CaH4'}])
    assert paper == before and differences[0]['field'] == 'paper.research_materials'
    assert differences[0]['state_materials'] == ['CaH4', 'CaH6']
    assert not paper_conflicts(paper, [{'material': 'CaH6'}])


def test_source_windows_do_not_truncate_or_repeat_source_content():
    sources = [{'file_id': 'main', 'content': str(i) * 100} for i in range(6)]
    windows = source_windows(sources, 300)
    assert len(windows) > 1
    assert [s for window in windows for s in window] == sources


@pytest.mark.parametrize('technical_failure', [False, True])
def test_paper_review_is_saved_before_handoff_and_technical_failure_cannot_complete(tmp_path, monkeypatch, technical_failure):
    from backend.ingest import upload_jobs, upload_tasks, property_evidence, keyword_extraction, paper_first
    from backend.ingest import research_motivation, paper_summary
    from backend.rag import llm, llm_context
    state = {'user_id': 7, 'status': 'extracting', 'files': []}
    phases, requests = [], []
    monkeypatch.setattr(upload_tasks, 'artifact_directory', lambda _: tmp_path)
    monkeypatch.setattr(upload_tasks, 'update_state', lambda _, **changes: phases.append(changes) or state.update(changes) or state)
    monkeypatch.setattr(upload_jobs, '_ensure_not_cancelled', lambda _: None)
    monkeypatch.setattr(paper_first, 'persist_paper', lambda *_a: requests.append('paper_values_saved'))
    monkeypatch.setattr(upload_jobs, '_classify_material_family_draft', lambda *_a: None)
    monkeypatch.setattr(paper_summary, 'choose_summary', lambda *_a: ('', 'source_absent'))
    monkeypatch.setattr(research_motivation, 'choose_motivation', lambda *_a: ('', 'source_absent', 'source'))
    monkeypatch.setattr(keyword_extraction, 'task_sources', lambda *_a: [])
    monkeypatch.setattr(keyword_extraction, 'select_keywords', lambda *_a, **_kw: {'values': [], 'status': 'uncertain'})
    monkeypatch.setattr(llm_context, 'get_llm_config', lambda: SimpleNamespace(provider='fixture', model='fixture'))
    monkeypatch.setattr(llm, 'complete_json', lambda *_a, **_kw: requests.append('paper_info') or {'paper': {'title': 'Source title', 'paper_type': 'unknown'}})
    from backend.ingest import upload_preview
    monkeypatch.setattr(upload_preview, 'publish_preview', lambda *_a, **_kw: None)
    def review(task, draft, owner, **options):
        assert not draft['material_states'] and options['field_scope'] == 'paper' and owner == 7
        requests.append('paper_review_saved')
        return {'field': {'status': 'uncertain', **({'review_error': 'transport_failure'} if technical_failure else {})}}
    monkeypatch.setattr(property_evidence, 'generate_upload_suggestions', review)
    sources = [{'file_id': 'main', 'content': 'Actual paper source.'}]
    if technical_failure:
        with pytest.raises(RuntimeError, match='技术失败'):
            paper_first.prepare_paper('a' * 32, state, sources)
        assert not json.loads((tmp_path / 'paper-stage.json').read_text())['completed']
    else:
        result = paper_first.prepare_paper('a' * 32, state, sources)
        assert result['paper']['title'] == 'Source title'
        assert json.loads((tmp_path / 'paper-stage.json').read_text())['completed']
        assert paper_first.prepare_paper('a' * 32, state, sources) == result
        assert requests == ['paper_info', 'paper_review_saved', 'paper_values_saved']
