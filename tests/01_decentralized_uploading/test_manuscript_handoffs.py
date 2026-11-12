"""整稿交接的真实SQL存储与权限；只使用隔离SQLite。"""
from types import SimpleNamespace
from copy import deepcopy

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend import models
from backend.services import manuscript_handoffs as h


@pytest.fixture
def context():
    engine = create_engine('sqlite:///:memory:')
    for table in (models.User.__table__, models.Paper.__table__, models.PaperHistoryEvent.__table__, models.ScientificReviewDraft.__table__):
        table.create(engine)
    with Session(engine) as session:
        paper = models.Paper(title='isolated', year=2026, uploaded_by_user_id=2, review_status='pending')
        session.add(paper); session.flush()
        yield session, paper, SimpleNamespace(id=2, username='author', role='user'), SimpleNamespace(id=1, username='reviewer', role='admin')
    engine.dispose()


def handoff(session, paper, actor, operation, *, action='submit', holder='review', reason='原文支持', initial=False):
    return h.record_handoff(session, paper, actor, action=action, holder=holder, initial=initial,
        operation_id=operation, draft={'paper': {'title': 'isolated'}, 'material_states': []},
        records=[{'field': 'paper.title', 'status': 'supported', 'reason': reason}])


def test_no_change_reuses_content_but_records_each_handoff(context):
    session, paper, author, reviewer = context
    first = handoff(session, paper, author, 'submit', initial=True)
    for i in range(6):
        returned = handoff(session, paper, reviewer, f'return-{i}', action='return', holder='author')
        sent = handoff(session, paper, author, f'send-{i}')
        assert first['snapshot_id'] == returned['snapshot_id'] == sent['snapshot_id']
    assert len(h.event_headers(session, paper.id)) == 13
    assert len([e for e in session.scalars(select(models.PaperHistoryEvent))
                if (e.classification_snapshot or {}).get('manuscript_snapshot')]) == 1


def test_original_chart_limits_remain_in_initial_history_without_changing_science(context):
    session,paper,author,_=context
    limits=[{'file_id':'si','source_sha256':'a'*64,'block_id':'chart-unresolved-source',
             'observation':{'reason':'Unquantified overlap; not a reported numerical zero.'}}]
    result=h.record_handoff(session,paper,author,action='submit',holder='review',initial=True,
        operation_id='source-limits',draft={'paper':{'title':'isolated'},'material_states':[]},
        records=[],source_limits=limits)
    event=session.get(models.PaperHistoryEvent,result['event_id'])
    assert event.classification_snapshot['document_source_limits']==limits
    assert event.classification_snapshot['manuscript_snapshot']['draft']['material_states']==[]


def test_reason_or_result_change_freezes_new_content_and_preserves_old(context):
    session, paper, author, reviewer = context
    first = handoff(session, paper, author, 'submit', initial=True)
    changed = handoff(session, paper, reviewer, 'return', action='return', holder='author', reason='核查表格后的理由')
    assert changed['snapshot_number'] == 2
    old = h.public_snapshot(session, paper, author, first['snapshot_id'])
    assert old['content']['records'][0]['reason'] == '原文支持'
    assert h.public_snapshot(session, paper, reviewer, changed['snapshot_id'])['content']['records'][0]['reason'] == '核查表格后的理由'


def test_handed_off_author_cannot_write_and_retries_are_idempotent(context):
    session, paper, author, reviewer = context
    sent = handoff(session, paper, author, 'submit', initial=True)
    with pytest.raises(HTTPException):h.require_writer(session, paper, author, author=True)
    assert handoff(session, paper, author, 'submit', initial=True)['snapshot_id'] == sent['snapshot_id']
    assert len(h.event_headers(session, paper.id)) == 1
    handoff(session, paper, reviewer, 'return', action='return', holder='author')
    h.require_writer(session, paper, author, author=True)
    with pytest.raises(HTTPException):h.require_writer(session, paper, reviewer)
    with pytest.raises(HTTPException):h.public_snapshot(session, paper, SimpleNamespace(id=99, role='user'), sent['snapshot_id'])


def test_published_reference_stays_until_next_approval(context):
    session, paper, author, reviewer = context
    handoff(session, paper, author, 'submit', initial=True)
    approved = handoff(session, paper, reviewer, 'approve', action='approve', holder='published')
    assert approved['published_snapshot_id'] == approved['snapshot_id']
    with pytest.raises(HTTPException):h.require_writer(session, paper, reviewer)
    # 已批准稿的正式交还由单独受权接口进行；不是原作者自行取回。
    returned = h.record_handoff(session, paper, reviewer, action='return_revision', holder='author',
        draft={'paper': {'title': 'isolated'}, 'material_states': []}, records=[],
        operation_id='return-published', initial=True)
    sent = handoff(session, paper, author, 'revision-submit', reason='修订结果')
    assert returned['published_snapshot_id'] == sent['published_snapshot_id'] == approved['snapshot_id']


def test_transaction_failure_does_not_leave_a_handoff_or_transfer_rights(context):
    session, paper, author, reviewer = context
    handoff(session, paper, author, 'submit', initial=True)
    with pytest.raises(RuntimeError):
        with session.begin_nested():
            handoff(session, paper, reviewer, 'return', action='return', holder='author')
            raise RuntimeError('模拟交接事务失败')
    assert h.latest(session, paper.id)['holder'] == 'review'
    assert len(h.event_headers(session, paper.id)) == 1


def test_current_content_omits_intermediate_history_without_mutating_input():
    data={'draft':{'paper':{'title':'A'},'_field_change_events':[{'before':'B'}]},
          'records':[{'status':'supported','reason':'理由','audit_events':[1],'history':[2]}]}
    before=deepcopy(data)
    assert h.content_hash(data)==h.content_hash({'draft':{'paper':{'title':'A'}},'records':[{'status':'supported','reason':'理由'}]})
    assert data==before

def test_frozen_file_survives_working_attachment_replacement(context,tmp_path,monkeypatch):
    import hashlib
    monkeypatch.setenv('JWT_SECRET_KEY','isolated-workdraft-test-secret')
    from backend.api.manuscript_handoffs import read_file
    from pathlib import Path
    monkeypatch.setenv('FILE_STORAGE_BACKEND','local')
    monkeypatch.setenv('FILE_STORAGE_LOCAL_ROOT',str(tmp_path))
    monkeypatch.setattr('backend.rag.config.settings',SimpleNamespace(sc_wiki_data_dir=tmp_path))
    session,paper,author,reviewer=context
    original=tmp_path/'source.txt';original.write_bytes(b'Frozen original source')
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    result=h.record_handoff(session,paper,author,action='submit',initial=True,operation_id='file-submit',
        draft={'paper':{'title':'A'}},records=[],files=[dict(file_id='source',stored_path=str(original),
        sha256=digest,size=original.stat().st_size,original_filename='source.txt',role='manual',media_type='text/plain')])
    original.write_bytes(b'Replaced current working file')
    response=read_file(paper.id,result['snapshot_id'],'source',user=author,session=session)
    assert Path(response.path).read_bytes()==b'Frozen original source'

def test_absent_optional_review_metadata_is_not_a_content_change():
    assert h.content_hash({'records':[{'status':'supported','state_review_context':None}]}) == h.content_hash({'records':[{'status':'supported'}]})
    assert h.content_hash({'mu_star':0}) != h.content_hash({'mu_star':None})


def test_213_handoff_listing_has_no_independent_revision_write_route(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'isolated-handoff-read-only-test')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.manuscript_handoffs import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/api/rag/handoffs/1/return', json={'operation_id': 'removed-return'})
    assert response.status_code == 404
