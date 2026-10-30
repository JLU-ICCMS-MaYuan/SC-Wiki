"""经手人变更只覆盖当前说明；旧快照和实际证据提供者保持。"""
from pathlib import Path
from copy import deepcopy
import hashlib
from sqlalchemy import select
from backend.manual_evidence_models import ScientificManualEvidence
from backend.services import manuscript_handoffs as h,workdrafts as w
from backend.ingest import property_evidence as ev,manual_evidence as manual
from backend.storage import FileRef,create_storage
from test_workdraft_ownership import context

def test_reviewer_handoff_preserves_items_and_allows_current_holder_to_edit(context,tmp_path,monkeypatch):
    session,paper,(author,reviewer,other)=context
    monkeypatch.setenv('FILE_STORAGE_BACKEND','local')
    monkeypatch.setenv('FILE_STORAGE_LOCAL_ROOT',str(tmp_path))
    monkeypatch.setattr(manual.settings,'sc_wiki_data_dir',tmp_path)
    monkeypatch.setenv('JWT_SECRET_KEY','isolated-manual-handoff')
    ScientificManualEvidence.__table__.create(session.connection(),checkfirst=True)
    w.open_draft(session,'paper',str(paper.id),reviewer);session.commit()
    def snapshot():
        result=ev.paper_snapshot(session,paper.id,reviewer.id,reviewer.role)
        result['records']=[r for r in result['records'] if r['field']=='paper.title']
        return result
    first=snapshot();record=first['records'][0]
    manual.save_explanation(session,first,{'records':[]},record['item_key'],reviewer.id,
        reason='旧经手人的说明',no_evidence_reason='',text_items=[{'text':'共同文字证据','source_description':'原文'}],actor_name=reviewer.username)
    saved=manual.add_file(session,first,{'records':[]},record['item_key'],reviewer.id,
        filename='evidence.txt',raw=b'Original manual evidence',source_description='原文件',actor_name=reviewer.username)
    file=next(item for item in saved['items'] if item['kind']=='text_file')
    session.commit()
    content=h.current_review_content(session,paper,reviewer)
    sent=h.record_handoff(session,paper,reviewer,action='forward',holder='review',
        operation_id='manual-forward',**content)
    session.commit()
    w.open_draft(session,'paper',str(paper.id),other);session.commit()
    current=snapshot()
    before=manual.read_field(session,current,{'records':[]},record['item_key'],include_history=False)
    ids=[item['id'] for item in before['items']]
    manual.save_explanation(session,current,{'records':[]},record['item_key'],other.id,
        reason='新经手人的说明',no_evidence_reason='',text_items=[],changed_fields={'reason'},actor_name=other.username)
    session.commit()
    after=manual.read_field(session,snapshot(),{'records':[]},record['item_key'],include_history=False)
    assert after['reason']=='新经手人的说明'
    assert [item['id'] for item in after['items']]==ids
    assert all(item['submitted_by_user_id']==reviewer.id for item in after['items'])
    assert session.scalar(select(ScientificManualEvidence).where(ScientificManualEvidence.status=='draft')).actor_user_id==other.id
    removed=manual.remove_file(session,snapshot(),record['item_key'],file['id'],other.id,actor_name=other.username)
    session.commit()
    if isinstance(removed,FileRef):create_storage().delete(removed)
    elif removed is not None:removed.unlink()
    frozen=h.public_snapshot(session,paper,author,sent['snapshot_id'])['content']
    assert frozen['manual'][0]['reason']=='旧经手人的说明'
    from backend.api.manuscript_handoffs import read_file
    response=read_file(paper.id,sent['snapshot_id'],'manual-file-'+hashlib.sha256(b'Original manual evidence').hexdigest(),user=author,session=session)
    assert Path(response.path).read_bytes()==b'Original manual evidence'
