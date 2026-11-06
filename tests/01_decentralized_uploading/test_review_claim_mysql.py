"""#100 隔离MySQL两位审核员竞争：只允许一位接手，另一位不能批准或拒绝。"""
import os,uuid,asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,select,func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from backend import models
from backend.services import manuscript_handoffs as h,workdrafts as w
from backend.api.evidence import FieldReviewCommit
from backend.services.field_review_commit import commit_review

pytestmark=pytest.mark.skipif(os.environ.get("SCWIKI_CURRENT_MYSQL")!="1",reason="显式隔离MySQL")

def test_review_queue_first_claim_serializes_and_only_owner_can_review():
    url=make_url(os.environ["DATABASE_URL"])
    assert (url.database or "").startswith("scwiki_issue139_test_six_100_")
    engine=create_engine(url,isolation_level="REPEATABLE READ")
    factory=sessionmaker(engine,expire_on_commit=False)
    try:
        with factory.begin() as db:
            users=[]
            for role in ("user","admin","superadmin"):
                key=uuid.uuid4().hex
                u=models.User(username="claim"+key[:10],email=key+"@isolated.invalid",
                    real_name="隔离用户",password_hash="test",role=role,is_approved=True)
                db.add(u);users.append(u)
            db.flush()
            paper=models.Paper(title="等待领取",year=2026,paper_type="review",review_status="pending",uploaded_by_user_id=users[0].id)
            db.add(paper);db.flush()
            h.record_handoff(db,paper,users[0],action="submit",initial=True,operation_id=uuid.uuid4().hex,
                draft={"paper":{"title":paper.title,"year":2026},"material_states":[]},records=[])
            identity=paper.id
            actors=[SimpleNamespace(id=u.id,role=u.role,username=u.username) for u in users]
        barrier=Barrier(2)
        def claim(actor):
            barrier.wait()
            try:
                with factory.begin() as db:
                    lease=w.open_draft(db,"paper",str(identity),actor)
                    return actor.id,lease.write_epoch
            except HTTPException as error:return actor.id,error.detail["code"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(claim,actors[1:]))
        winners=[(uid,value) for uid,value in results if value!="workdraft_claimed"]
        assert len(winners)==1,results
        winner=next(a for a in actors if a.id==winners[0][0])
        loser=next(a for a in actors[1:] if a.id!=winner.id)
        with factory() as db:
            p=db.get(models.Paper,identity)
            assert h.latest(db,identity)["holder"]=="review"
            assert w.row(db,"paper",str(identity)).owner_id==winner.id
            for actor in actors[1:]:
                assert h.public_snapshot(db,p,actor,h.latest(db,identity)["snapshot_id"])["content"]["draft"]["paper"]["title"]=="等待领取"
            count=db.scalar(select(func.count()).select_from(models.PaperHistoryEvent).where(models.PaperHistoryEvent.paper_id==identity))
        async def denied(actor,status):
            async_engine=create_async_engine(url.set(drivername="mysql+asyncmy"))
            try:
                async with async_sessionmaker(async_engine)() as db,db.begin():
                    with pytest.raises(HTTPException):
                        await commit_review(db,FieldReviewCommit(paper_id=identity,status=status,review_request_id=uuid.uuid4().hex),actor)
            finally:await async_engine.dispose()
        for actor in (loser,actors[0]):
            for status in ("approved","rejected"):asyncio.run(denied(actor,status))
        with factory() as db:
            assert db.get(models.Paper,identity).review_status=="pending"
            assert db.scalar(select(func.count()).select_from(models.PaperHistoryEvent).where(models.PaperHistoryEvent.paper_id==identity))==count
            assert w.row(db,"paper",str(identity)).owner_id==winner.id
    finally:engine.dispose()
