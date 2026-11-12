"""浅度解析的行为边界，不连接业务库或调用真实模型。"""
import json

import pytest
from fastapi import HTTPException


def test_paper_extraction_keeps_all_paper_fields_without_scientific_output():
    from backend.ingest.shallow_parsing import extract_paper
    calls = []
    def complete(prompt, payload, **kwargs):
        calls.append(json.loads(payload))
        return {'paper': {'title': 'Calcium hydride', 'year': 2020,
            'paper_type': 'theoretical', 'theoretical_subtype': 'calculation',
            'authors': ['A'], 'corresponding_authors': ['A'],
            'research_materials': ['CaH6'], 'summary': 'Summary',
            'research_motivation': 'Motivation', 'methodology': ['DFT'],
            'knowledge_graph_title': 'Calcium hydride', 'keywords_tags': ['hydride'],
            'key_finding': 'Main finding', 'material_families': ['Hydrides']}}
    draft = extract_paper([{'content': 'Original source', 'file_id': 'main'}], complete=complete)
    assert len(calls) == 1
    assert draft['paper']['research_materials'] == ['CaH6']
    assert draft['paper']['corresponding_authors'] == ['A']
    assert draft['paper']['research_motivation'] == 'Motivation'
    assert draft['material_states'] == []
    assert not draft.get('model_review_report')


def test_shallow_validation_does_not_require_a_material_state_or_review():
    from backend.ingest.shallow_parsing import validate_shallow, SHALLOW
    draft = {'_parsing_workflow': SHALLOW.binding(), 'paper': {
        'title': 'Paper only', 'year': 2026, 'paper_type': 'experimental'},
        'material_states': []}
    paper, states = validate_shallow(draft)
    assert paper['title'] == 'Paper only' and states == []
    with pytest.raises(HTTPException):
        validate_shallow({**draft, 'material_states': [{'material': 'CaH6'}]})
    with pytest.raises(HTTPException):
        validate_shallow({**draft, 'paper': {**draft['paper'], 'year': True}})


def test_upload_mode_is_locked_with_enqueue_right(monkeypatch):
    from backend.ingest import upload_tasks as tasks
    state = {'task_id': 'task', 'status': 'uploading', 'defer_parsing': True,
        'files': [{'upload_status': 'completed'}], 'revision': 1}
    class Client:
        raw = json.dumps(state)
        def pipeline(self, **kwargs): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def watch(self, *args): pass
        def get(self, key): return self.raw
        def multi(self): pass
        def set(self, key, value): self.raw = value
        def execute(self): pass
    client = Client()
    monkeypatch.setattr(tasks, 'redis_client', lambda: client)
    with pytest.raises(ValueError):
        tasks.lock_uploaded_manifest('task')
    chosen, queued = tasks.lock_uploaded_manifest('task', parsing_mode='shallow')
    assert queued and chosen['parsing_mode'] == 'shallow'
    assert tasks.lock_uploaded_manifest('task', parsing_mode='shallow')[1] is False
    with pytest.raises(ValueError):
        tasks.lock_uploaded_manifest('task', parsing_mode='deep')


def test_shallow_binding_cannot_be_used_for_a_deep_task():
    from backend.ingest.parsing_workflows import require_task_workflow, CURRENT
    from backend.ingest.shallow_parsing import SHALLOW
    state = {'workflow_policy': 'typed-parsing-v1', 'parsing_mode': 'deep',
        '_parsing_workflow': CURRENT.binding()}
    with pytest.raises(HTTPException):
        require_task_workflow(state, {'_parsing_workflow': SHALLOW.binding()})


@pytest.mark.parametrize('fail', [False, True])
def test_shallow_submit_skips_evidence_and_recovers_failure(monkeypatch, fail):
    import asyncio
    from types import SimpleNamespace
    from backend.api import rag
    from backend.ingest import upload_tasks as tasks, property_evidence
    from backend.ingest.shallow_parsing import SHALLOW
    state = {'task_id': 'task', 'user_id': 7, 'parsing_mode': 'shallow',
        'status': 'ready', 'stage': 'ready', 'processing_status': 'succeeded',
        'workflow_policy': 'typed-parsing-v1', '_parsing_workflow': SHALLOW.binding()}
    draft = {'_parsing_workflow': SHALLOW.binding(), 'paper': {
        'title': 'Paper only', 'year': 2026}, 'material_states': []}
    async def absent(*args): return None
    async def create(*args, **kwargs):
        assert kwargs['evidence_checks'] is None
        if fail: raise RuntimeError('isolated write failure')
        return 241
    def forbidden(*args, **kwargs): raise AssertionError('浅度调用了核对')
    monkeypatch.setattr(rag, '_submitted_paper_for_task', absent)
    monkeypatch.setattr(rag, '_task_for_user', lambda *args: state)
    monkeypatch.setattr(tasks, 'get_draft', lambda *args: draft)
    monkeypatch.setattr(tasks, 'update_state', lambda task_id, **changes: state.update(changes))
    monkeypatch.setattr(rag, '_create_pending_paper', create)
    monkeypatch.setattr(rag, '_record_submitted_upload', lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks, 'cleanup_transient_data', lambda *args, **kwargs: None)
    monkeypatch.setattr(property_evidence, 'upload_snapshot', forbidden)
    monkeypatch.setattr(property_evidence, 'resolve_results', forbidden)
    if fail:
        with pytest.raises(RuntimeError):
            asyncio.run(rag._submit_upload_draft_locked('task', SimpleNamespace(id=7)))
        assert state['status'] == 'ready' and state['submission_status'] == 'failed'
    else:
        result = asyncio.run(rag._submit_upload_draft_locked('task', SimpleNamespace(id=7)))
        assert result == {'ok': True, 'paper_id': 241, 'review_status': 'published'}


def test_research_material_index_does_not_guess_elements_from_names():
    from backend.ingest.shallow_parsing import research_systems
    assert research_systems(['CaH6', 'calcium hydrides', 'LaSc2H24', 'CaH6']) == {
        'Ca-H': ['Ca', 'H'], 'H-La-Sc': ['H', 'La', 'Sc']}
