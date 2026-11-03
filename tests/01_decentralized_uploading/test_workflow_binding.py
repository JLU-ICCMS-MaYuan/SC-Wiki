"""流程绑定的真实SQL历史、快照和无法绕过的操作边界。"""
from copy import deepcopy
from contextlib import nullcontext
import os
from types import SimpleNamespace

os.environ.setdefault('DATABASE_URL', 'sqlite:////tmp/scwiki-workflow-binding-tests.db')
os.environ.setdefault('JWT_SECRET_KEY', 'test-only-secret')

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend import models
from backend.ingest import parsing_workflows as w
from backend.services import manuscript_handoffs as h


@pytest.fixture
def context():
    engine = create_engine('sqlite:///:memory:')
    for model in (models.User, models.Paper, models.PaperHistoryEvent, models.ScientificReviewDraft,
                  models.MaterialFamily, models.PaperMaterialFamily, models.MaterialState,
                  models.PaperEvidence, models.PaperChunk):
        model.__table__.create(engine)
    with Session(engine) as session:
        paper = models.Paper(title='Isolated', year=2026, content_revision=1,
            uploaded_by_user_id=2, review_status='pending')
        session.add(paper); session.flush()
        yield session, paper, SimpleNamespace(id=2, username='author', role='user')
    engine.dispose()


def test_sql_submission_and_frozen_snapshot_restore_binding(context):
    from backend.services.paper_revisions import current_draft
    session, paper, author = context
    draft = {'paper': {'title': 'Isolated'}, 'material_states': [], w.BINDING: w.CURRENT.binding()}
    first = h.record_handoff(session, paper, author, action='submit', draft=draft,
        records=[], operation_id='isolated-workflow', initial=True)
    session.commit(); session.expire_all()
    event = session.scalar(select(models.PaperHistoryEvent))
    assert event.classification_snapshot['upload_submission'][w.BINDING] == w.CURRENT.binding()
    assert h.public_snapshot(session, paper, author, first['snapshot_id'])['content']['draft'][w.BINDING] == w.CURRENT.binding()
    assert current_draft(session, paper)[w.BINDING] == w.CURRENT.binding()


def test_legacy_current_read_does_not_assign_workflow(context):
    from backend.services.paper_revisions import current_draft
    session, paper, _author = context
    assert w.BINDING not in current_draft(session, paper)
    assert not list(session.scalars(select(models.PaperHistoryEvent)))


def test_invalid_binding_cannot_be_handed_off(context):
    session, paper, author = context
    with pytest.raises(HTTPException) as exc:
        h.record_handoff(session, paper, author, action='submit', draft={w.BINDING: {'workflow_key': 'forged'}},
            records=[], operation_id='forged-workflow', initial=True)
    assert exc.value.detail['code'] == 'parsing_workflow_unavailable'


@pytest.mark.parametrize('status', ['failed', 'needs_workflow'])
def test_manual_endpoint_cannot_bypass_unselected_new_task(monkeypatch, status):
    import asyncio
    from backend.api import rag
    monkeypatch.setattr(rag, '_task_for_user', lambda *_a: dict(status=status,
        processing_status='failed', workflow_policy=w.POLICY))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rag.use_manual_upload_draft('a' * 32, SimpleNamespace(id=2)))
    assert exc.value.detail['code'] == 'parsing_workflow_unavailable'


def test_local_change_cannot_modify_program_binding():
    from backend.ingest.field_drafts import apply_changes
    draft = {'paper': {'title': 'Old'}, 'material_states': [], w.BINDING: w.CURRENT.binding()}
    changed = apply_changes(draft, [{'path': ['paper', 'title'], 'value': 'New'}])
    assert changed[w.BINDING] == draft[w.BINDING]
    with pytest.raises(HTTPException):
        apply_changes(draft, [{'path': [w.BINDING, 'workflow_key'], 'value': 'forged'}])


def test_new_task_cannot_request_scientific_review_before_selection(monkeypatch):
    from backend.ingest import property_evidence, upload_tasks
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _id: dict(user_id=2,
        status='needs_workflow', workflow_policy=w.POLICY))
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda _id: {'paper': {}, 'material_states': []})
    with pytest.raises(HTTPException) as exc:
        property_evidence.upload_snapshot('a' * 32, 2)
    assert exc.value.detail['code'] == 'parsing_workflow_unavailable'


def test_normalization_preserves_server_binding_but_not_model_binding():
    from backend.ingest.upload_jobs import _normalize_draft
    draft = {'paper': {}, 'material_states': [], w.BINDING: w.CURRENT.binding()}
    assert _normalize_draft(draft)[w.BINDING] == w.CURRENT.binding()
    assert w.BINDING not in _normalize_draft(draft, preserve_citation_extraction=False)


def test_paused_original_download_is_owned_and_independent_of_scientific_draft(tmp_path, monkeypatch):
    from backend.api.upload_tasks import download_original_file
    from backend.ingest import upload_tasks
    file = tmp_path / 'original.pdf'; file.write_bytes(b'isolated source')
    state = dict(user_id=2, status='needs_workflow', workflow_policy=w.POLICY, files=[
        dict(file_id='main', stored_path=str(file), original_filename='original.pdf')])
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _id: state)
    response = download_original_file('a' * 32, 'main', SimpleNamespace(id=2, role='user'))
    assert response.path == file and response.filename == 'original.pdf'
    with pytest.raises(HTTPException) as exc:
        download_original_file('a' * 32, 'main', SimpleNamespace(id=3, role='user'))
    assert exc.value.status_code == 403


def test_new_task_binding_must_equal_selected_binding():
    state = dict(workflow_policy=w.POLICY, **{w.BINDING: w.CURRENT.binding()})
    with pytest.raises(HTTPException):
        w.require_task_workflow(state, {})
