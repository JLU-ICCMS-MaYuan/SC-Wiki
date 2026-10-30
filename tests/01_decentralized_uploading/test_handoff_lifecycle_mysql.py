"""仅隔离MySQL：公开稿交还→返修送审→审核接手→批准，持续读取旧公开版。"""
import os,asyncio,uuid
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.engine import make_url
from backend import models
from backend.services import manuscript_handoffs as h,workdrafts as w,paper_revisions as revisions
from backend.ingest import property_evidence as ev,scientific_evidence as science
from backend.ingest.field_drafts import save_fields

pytestmark=pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL')!='1',reason='仅显式隔离MySQL')

def test_published_revision_handoff_cycle_and_private_owner():
    asyncio.run(exercise())

async def exercise():
    url=make_url(os.environ['DATABASE_URL'])
    assert (url.database or '').startswith('scwiki_issue139_test_six_')
    engine=create_async_engine(url.set(drivername='mysql+asyncmy'))
    factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
      async with factory() as db:
        users=[]
        for role in ['user','admin','superadmin']:
            key=uuid.uuid4().hex
            user=models.User(username='cycle'+key[:10],email=key+'@cycle.invalid',real_name='隔离测试',password_hash='isolated',role=role,is_approved=True)
            db.add(user);users.append(user)
        await db.flush()
        author,first,other=users
        family=await db.scalar(select(models.MaterialFamily).limit(1))
        assert family is not None
        paper=models.Paper(title='公开原稿',year=2026,paper_type='review',superconductor_kind='unknown',uploaded_by_user_id=author.id,
            review_status='approved',content_revision=1,approved_revision=1)
        db.add(paper);await db.flush()
        db.add(models.PaperMaterialFamily(paper_id=paper.id,paper_revision=1,material_family_id=family.id));await db.flush()
        def initial(session):
            snapshot=ev.paper_snapshot(session,paper.id,first.id,first.role)
            checks={r['key']:{'status':'supported','reason':'隔离测试预置当前结果','source_kind':'paper_quote'} for r in snapshot['records']}
            science.save_results(session,snapshot,checks,first.id);session.flush()
            cached=science.load_results(session,snapshot,first.id)
            content=h.capture(session,paper,revisions.current_draft(session,paper),snapshot,ev.public_snapshot(snapshot,cached)['records'])
            return h.record_handoff(session,paper,first,action='approve',holder='published',initial=True,operation_id=uuid.uuid4().hex,**content)
        published=await db.run_sync(initial);await db.commit()
        from backend.api.manuscript_handoffs import return_to_author,ReturnRevision
        returned=await db.run_sync(lambda session:return_to_author(paper.id,ReturnRevision(operation_id=uuid.uuid4().hex,
            expected_snapshot_id=published['snapshot_id']),user=other,session=session))
        assert returned['handoff']['reused']
        saved=await db.get(models.PaperRevisionDraft,paper.id)
        lease=await db.run_sync(lambda session:w.open_draft(session,'revision',saved.revision_id,author))
        await db.run_sync(lambda session:save_fields(session,'revision',saved.revision_id,author,lease.write_epoch+':old',
            [{'path':['paper','title'],'before':'公开原稿','value':'修订新稿'}]))
        await db.commit()
        await db.refresh(paper)
        assert paper.title=='公开原稿' and paper.review_status=='approved'
        snapshot=await db.run_sync(lambda session:revisions.revision_snapshot(session,saved.revision_id,author.id))
        checks={r['key']:{'status':'supported','reason':'隔离测试预置当前结果','source_kind':'paper_quote'} for r in snapshot['records']}
        await db.run_sync(lambda session:science.save_results(session,snapshot,checks,author.id));await db.flush()
        payload=SimpleNamespace(revision_id=saved.revision_id,draft_version=saved.draft_version,
            evidence_job_id=None,expected_evidence_version=snapshot['version'])
        await revisions.submit_draft(db,paper.id,author,payload);await db.commit()
        await db.refresh(paper)
        assert paper.title=='公开原稿' and paper.review_status=='approved'
        assert (await db.run_sync(lambda session:h.latest(session,paper.id)))['published_snapshot_id']==published['snapshot_id']
        await db.run_sync(lambda session:w.open_draft(session,'paper',str(paper.id),first));await db.commit()
        from fastapi import HTTPException
        from backend.ingest.field_drafts import authorized_draft
        with pytest.raises(HTTPException):
            await db.run_sync(lambda session:authorized_draft(session,'paper',str(paper.id),other))
        snapshot=await db.run_sync(lambda session:__import__('backend.services.manuscript_handoffs',fromlist=['current_review_content']).current_review_content(session,paper,first))
        from backend.api.evidence import snapshot_for,Target,FieldReviewCommit
        # 使用同一会话内的暂存稿构建当前提交检查，避免连接读取旧事务。
        draft,_=await db.run_sync(lambda session:authorized_draft(session,'paper',str(paper.id),first))
        formal=await db.run_sync(lambda session:ev.paper_snapshot(session,paper.id,first.id,first.role))
        current={**formal,**ev.complete_snapshot('paper',str(paper.id),ev.draft_records(draft,{}),formal['chunks'],draft)}
        from backend.ingest.field_review import bind_support_versions
        await db.run_sync(lambda session:bind_support_versions(current,session))
        checks={r['key']:{'status':'supported','reason':'隔离测试预置当前结果','source_kind':'paper_quote'} for r in current['records']}
        await db.run_sync(lambda session:science.save_results(session,current,checks,first.id));await db.flush()
        from backend.services.field_review_commit import commit_review
        await commit_review(db,FieldReviewCommit(paper_id=paper.id,expected_evidence_version=current['version'],review_request_id=uuid.uuid4().hex),first)
        await db.commit();await db.refresh(paper)
        assert paper.title=='修订新稿' and paper.review_status=='approved'
        events=await db.run_sync(lambda session:h.event_headers(session,paper.id))
        assert events[-1]['reused'] and events[-1]['snapshot_id']==events[-2]['snapshot_id']
        frozen=await db.run_sync(lambda session:h.public_snapshot(session,paper,author,published['snapshot_id']))
        assert frozen['content']['draft']['paper']['title']=='公开原稿'
    finally:await engine.dispose()
