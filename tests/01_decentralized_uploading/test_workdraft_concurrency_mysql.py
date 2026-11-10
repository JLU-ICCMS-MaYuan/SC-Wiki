"""真实RR事务：等到行锁以后必须读最新稿和交接，不能复用旧身份映射。"""
import os,uuid
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from backend import models
from backend.services import manuscript_handoffs as h,workdrafts as w
from backend.ingest.field_drafts import save_fields

pytestmark=pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL')!='1',reason='显式隔离MySQL')
@pytest.fixture
def data():
    url=make_url(os.environ['DATABASE_URL'])
    assert (url.database or '').startswith('scwiki_issue139_test_six_')
    engine=create_engine(url,isolation_level='REPEATABLE READ')
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory.begin() as session:
        users=[]
        for role in ['user','admin']:
            key=uuid.uuid4().hex
            user=models.User(username='rr'+key[:12],email=key+'@rr.invalid',real_name='隔离事务验证',password_hash='isolated',role=role,is_approved=True)
            session.add(user);users.append(user)
        session.flush()
        paper=models.Paper(title='Before',year=2026,uploaded_by_user_id=users[0].id,review_status='pending',paper_type='review')
        session.add(paper);session.flush()
        h.record_handoff(session,paper,users[0],action='submit',operation_id=uuid.uuid4().hex,initial=True,
            draft={'paper':{'title':'Before','year':2026},'material_states':[]},records=[])
        lease=w.open_draft(session,'paper',str(paper.id),users[1])
        identity=paper.id
        actor=SimpleNamespace(id=users[1].id,username=users[1].username,role='admin')
        epoch=lease.write_epoch
    yield factory,identity,actor,epoch
    engine.dispose()

def test_stale_orm_draft_does_not_overwrite_other_pages_latest_field(data):
    factory,paper_id,actor,epoch=data
    with factory() as old:
        cached=old.get(models.ScientificReviewDraft,paper_id)
        assert cached.draft['paper']['year']==2026
        with factory.begin() as current:
            save_fields(current,'paper',str(paper_id),actor,epoch+':old',[
                {'path':['paper','year'],'before':2026,'value':2027}])
        save_fields(old,'paper',str(paper_id),actor,epoch+':old',[
            {'path':['paper','title'],'before':'Before','value':'Latest title'}])
        old.commit()
    with factory() as session:
        value=session.get(models.ScientificReviewDraft,paper_id).draft['paper']
        assert value['year']==2027 and value['title']=='Latest title'

def test_old_repeatable_read_view_cannot_hide_new_handoff(data):
    factory,paper_id,actor,epoch=data
    with factory() as old:
        paper=old.get(models.Paper,paper_id)
        assert h.latest(old,paper_id)['holder']=='review'
        with factory.begin() as current:
            p=current.get(models.Paper,paper_id)
            h.record_handoff(current,p,actor,action='return',holder='author',operation_id=uuid.uuid4().hex,
                draft={'paper':{'title':'Before','year':2026},'material_states':[]},records=[])
        with pytest.raises(HTTPException):h.require_writer(old,paper,actor,lock=True)  # #226：保存前写门禁必须取当前行，普通读不抢写锁。
