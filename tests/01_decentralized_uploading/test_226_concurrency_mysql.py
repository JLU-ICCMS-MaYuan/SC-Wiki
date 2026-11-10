"""真实MySQL：持有保存锁时普通读取不抢锁，后台字段结果不能另开会话等待自己。"""
import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,text
from backend import models,database
from backend.api import evidence as api
from backend.ingest import property_evidence as ev,scientific_evidence as science
from backend.ingest.field_drafts import authorized_draft,save_fields
from backend.ingest.field_input import select_field,binding
from test_workdraft_concurrency_mysql import data

pytestmark=pytest.mark.skipif(os.environ.get("SCWIKI_CURRENT_MYSQL")!="1",reason="显式隔离MySQL")

@pytest.mark.parametrize("role",["admin","superadmin"])
def test_reader_does_not_wait_for_writer_and_sees_committed_data(data,monkeypatch,role):
    factory,identity,actor,epoch=data;actor.role=role
    monkeypatch.setattr(api,"SessionLocal",factory)
    with factory.begin() as db:db.get(models.User,actor.id).role=role
    with factory() as writer:
        writer.execute(text("SET SESSION innodb_lock_wait_timeout=2"))
        draft,staged=authorized_draft(writer,"paper",str(identity),actor,lock=True)
        assert staged.owner_id==actor.id
        def read():
            snapshot,_=api.snapshot_for(api.Target(target="paper",target_id=str(identity)),actor)
            return next(r["current_value"] for r in snapshot["records"] if r["field"]=="paper.title")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(read)
            assert future.result(timeout=5)=="Before"
        save_fields(writer,"paper",str(identity),actor,epoch+":before",
            [{"path":["paper","title"],"before":"Before","value":"Writer committed"}])
        writer.commit()
    with factory() as db:assert db.get(models.ScientificReviewDraft,identity).draft["paper"]["title"]=="Writer committed"

@pytest.mark.parametrize("role",["admin","superadmin"])
def test_field_worker_persistence_reuses_transaction_and_does_not_wait_itself(data,monkeypatch,role):
    factory,identity,actor,epoch=data;actor.role=role
    with factory.begin() as db:db.get(models.User,actor.id).role=role
    monkeypatch.setattr(api,"SessionLocal",factory);monkeypatch.setattr(database,"SessionLocal",factory)
    # 每个测试连接只在隔离库内使用短锁超时，回退会抛异常，不靠延长超时掩盖。
    from sqlalchemy import event
    @event.listens_for(factory.kw["bind"],"checkout")
    def timeout(connection,record,proxy):
        cursor=connection.cursor();cursor.execute("SET SESSION innodb_lock_wait_timeout=2");cursor.close()
    snapshot,_=api.snapshot_for(api.Target(target="paper",target_id=str(identity)),actor)
    r=next(r for r in snapshot["records"] if r["field"]=="paper.title")
    snapshot=select_field(snapshot,r["item_key"]);snapshot["field_review_input"]=binding(snapshot)
    ev.persist_completed_results(snapshot,{r["key"]:{"status":"supported","reason":"隔离任务结果","evidences":[]}},actor.id)
    with factory() as db:
        saved=db.scalar(select(models.ScientificEvidenceCheck).where(models.ScientificEvidenceCheck.target=="paper",
            models.ScientificEvidenceCheck.target_id==str(identity),models.ScientificEvidenceCheck.item_key==r["item_key"]))
        assert saved and saved.result["reason"]=="隔离任务结果"
