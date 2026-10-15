"""#137 隔离 MySQL 事务验收；明确拒绝连接非测试数据库。"""
import os
import uuid
import asyncio
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from backend import models
from backend.database import SessionLocal
from backend.rag.database import async_session_factory
from backend.ingest.scientific_drafts import persist_scientific_draft
from backend.services import spectra as service
from backend.spectra.contracts import state_signature

pytestmark=pytest.mark.skipif(os.environ.get("SCWIKI_SPECTRA_MYSQL_TEST")!="1",reason="只在显式指定的隔离MySQL运行")


def ensure_isolated():
    sync_url = SessionLocal.kw["bind"].url
    async_url = async_session_factory.kw["bind"].url
    for url in (sync_url, async_url):
        assert "issue137_test" in (url.database or ""), "拒绝向实际业务库写测试数据"
    assert (sync_url.host, sync_url.port, sync_url.database) == (async_url.host, async_url.port, async_url.database), "同步和异步测试必须连接同一个隔离库"


async def create_graph(session, owner, suffix):
    paper=models.Paper(title="Issue137 隔离谱验收 "+suffix,year=2026,uploaded_by_user_id=owner.id,
                       review_status="pending",content_revision=1,superconductor_kind="unknown")
    session.add(paper);await session.flush()
    draft=dict(paper=dict(superconductor_kind="unknown"),material_states=[dict(state_key="s1",
        material="",material_name="谱验收材料",state_kind="theoretical",pressure_value_gpa=200,
        material_dimensionality="unknown",crystal_system="unknown",property_modules=[])])
    await persist_scientific_draft(session,paper,draft)
    return paper,draft


def test_mysql_commit_binding_foreign_keys_and_versions():
    ensure_isolated()
    suffix=uuid.uuid4().hex[:10]
    with SessionLocal.begin() as s:
        user=models.User(email=suffix+"@issue137.invalid",username="sp"+suffix,
                         password_hash="test-only",real_name="隔离测试",role="admin",is_approved=True)
        s.add(user);s.flush();uid=user.id
    async def exercise():
        async with async_session_factory() as s:
            async with s.begin():
                owner=await s.get(models.User,uid)
                paper,draft=await create_graph(s,owner,suffix)
                ctx=dict(target="upload",target_id=suffix,owner_id=uid,paper=None,paper_revision=None)
                state=draft["material_states"][0]
                row=await s.run_sync(lambda db:service.collection(db,ctx,"source","panel",dict(source_sha256="0"*64)))
                row.state_key="s1";row.state_signature=state_signature(state)
                run,_=await s.run_sync(lambda db:service.new_run(db,row,dict(panel_id="panel"),state))
                await s.run_sync(lambda db:service.complete_run(run,dict(curves=[],quality={},candidates={})))
                await s.run_sync(lambda db:service.activate(row,run,state))
                await service.bind_to_paper(s,paper,draft,target="upload",target_id=suffix)
                pid,rid,runid=paper.id,row.id,run.id
        with SessionLocal() as db:
            saved=db.get(models.SpectrumCollection,rid)
            assert saved.target=="paper" and saved.paper_id==pid and saved.paper_revision==1
            assert saved.material_state_id is not None
            assert db.get(models.SpectrumRun,runid).status=="succeeded"
        # 单事务异常时不留下新谱身份和正式绑定。
        aborted_id=None
        try:
            async with async_session_factory() as s:
                async with s.begin():
                    paper=await s.get(models.Paper,pid)
                    ctx=dict(target="upload",target_id=suffix+"-rollback",owner_id=uid,paper=None,paper_revision=None)
                    aborted=await s.run_sync(lambda db:service.collection(db,ctx,"other","panel",{}))
                    aborted_id=aborted.id
                    await service.bind_to_paper(s,paper,draft,target="upload",target_id=ctx["target_id"])
                    raise RuntimeError("test rollback")
        except RuntimeError:pass
        with SessionLocal() as db:assert db.get(models.SpectrumCollection,aborted_id) is None
        async with async_session_factory() as s:
            async with s.begin():
                paper=await s.get(models.Paper,pid)
                await service.copy_to_revision(s,paper,"revision-"+suffix)
        with SessionLocal() as db:
            copied=db.scalar(select(models.SpectrumCollection).where(models.SpectrumCollection.target=="revision",
                                models.SpectrumCollection.target_id=="revision-"+suffix))
            assert copied and copied.current_run_id!=runid and copied.review_json=={}
            assert db.get(models.SpectrumRun,copied.current_run_id).result_json==db.get(models.SpectrumRun,runid).result_json
        return pid
    asyncio.run(exercise())


def test_mysql_paper_permission_and_revision_visibility():
    ensure_isolated()
    suffix=uuid.uuid4().hex[:10]
    with SessionLocal.begin() as s:
        owner=models.User(email=suffix+"@issue137.invalid",username="sp"+suffix,
            password_hash="test-only",real_name="隔离测试",role="user")
        s.add(owner);s.flush()
        paper=models.Paper(title="谱权限验收",year=2026,uploaded_by_user_id=owner.id,review_status="pending")
        s.add(paper);s.flush()
        with pytest.raises(Exception) as forbidden:service.context(s,"paper",str(paper.id),None)
        assert forbidden.value.status_code==403
        assert service.context(s,"paper",str(paper.id),owner)["privileged"]
        with pytest.raises(Exception) as forbidden:service.context(s,"paper",str(paper.id),owner,write=True)
        assert forbidden.value.status_code==403
        paper.review_status="approved";paper.approved_revision=paper.content_revision;s.flush()
        assert not service.context(s,"paper",str(paper.id),None)["privileged"]


def test_mysql_navigation_assignment_http_versions_permissions_and_pending_calibration(monkeypatch):
    """归属经正式 HTTP/存储链生成新运行，旧曲线与采纳不能悄悄挪用。"""
    ensure_isolated()
    import copy
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api import spectra as routes
    from backend.database import get_db
    from backend.security import get_current_user, get_current_user_optional
    from backend.ingest import upload_tasks
    from backend.tests.test_spectra import fixture
    from backend.spectra.engine import extract_panel

    suffix = uuid.uuid4().hex
    with SessionLocal.begin() as session:
        owner = models.User(email=suffix+"@issue137.invalid", username="nav"+suffix[:10],
            password_hash="test-only", real_name="归属隔离验证", role="user")
        stranger = models.User(email="other"+suffix+"@issue137.invalid", username="oth"+suffix[:10],
            password_hash="test-only", real_name="无关用户", role="user")
        session.add_all([owner, stranger]); session.flush()
        owner_id, stranger_id = owner.id, stranger.id
    states = [dict(state_key="s1", material="H3S", pressure_value_gpa=150, property_modules=[]),
              dict(state_key="s2", material="H3S", pressure_value_gpa=200, property_modules=[])]
    task = "nav-" + suffix
    monkeypatch.setattr(upload_tasks, "get_state", lambda identity: dict(user_id=owner_id, status="ready",
        files=[dict(file_id="main", role="main", kind="pdf", sha256="source")]) if identity==task else None)
    monkeypatch.setattr(upload_tasks, "get_draft", lambda identity: dict(material_states=states) if identity==task else None)
    monkeypatch.setattr(upload_tasks, "save_llm_config", lambda *_: None)
    monkeypatch.setattr(routes, "get_llm_config", lambda: SimpleNamespace(model="navigation-test"))
    dispatched = []
    monkeypatch.setattr(routes.jobs, "dispatch", lambda job, uid: dispatched.append((job, uid)))
    with SessionLocal.begin() as session:
        ctx = service.context(session, "upload", task, session.get(models.User, owner_id), write=True)
        image, calibration = fixture()
        row = service.collection(session, ctx, "source", "p", dict(source_sha256="source", pdf_page=1))
        run, _ = service.new_run(session, row, calibration, ctx["states"][0])
        service.complete_run(run, extract_panel(image, calibration))
        service.activate(row, run, ctx["states"][0])
        row.review_json = {"a": {"status": "accepted"}}
        collection_id, old_run, old_result, collection_version = row.id, run.id, copy.deepcopy(run.result_json), row.version

    with SessionLocal() as session:
        old_result = copy.deepcopy(session.get(models.SpectrumRun, old_run).result_json)

    actor = [owner_id]
    def database():
        with SessionLocal() as session:
            yield session
    def user():
        with SessionLocal() as session:
            return session.get(models.User, actor[0])
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    app.dependency_overrides[get_current_user_optional] = user
    app.dependency_overrides[routes.request_llm_config] = lambda: None
    query = dict(target="upload", target_id=task)
    with TestClient(app) as client:
        initial = client.get("/api/rag/spectra", params=query)
        assert initial.status_code == 200
        body = dict(**query, expected_version=initial.json()["version"],
                    expected_collection_version=collection_version,
                    calibration={**calibration, "state_key": "s2"})
        changed = client.put("/api/rag/spectra/"+collection_id+"/calibration", json=body)
        assert changed.status_code == 202, changed.text
        assert len(dispatched) == 1 and dispatched[0][1] == owner_id
        fresh = client.get("/api/rag/spectra", params=query).json()
        item = fresh["items"][0]
        assert item["state_key"] == "s2" and item["run"]["status"] == "queued"
        assert item["result"]["curves"] == []
        assert item["result"]["calibration"]["state_key"] == "s2"
        assert item["review"] == {}
        assert client.put("/api/rag/spectra/"+collection_id+"/calibration", json=body).status_code == 409
        foreign = {**body, "expected_collection_version": item["version"],
                   "calibration": {**calibration, "state_key": "foreign"}}
        assert client.put("/api/rag/spectra/"+collection_id+"/calibration", json=foreign).status_code == 422
        actor[0] = stranger_id
        assert client.get("/api/rag/spectra", params=query).status_code == 403
        assert client.put("/api/rag/spectra/"+collection_id+"/calibration", json=foreign).status_code == 403
        actor[0] = owner_id
        states[1]["pressure_value_gpa"] = 210
        assert client.put("/api/rag/spectra/"+collection_id+"/calibration",
            json={**body,"expected_collection_version":item["version"]}).status_code == 409
    with SessionLocal() as session:
        row = session.get(models.SpectrumCollection, collection_id)
        assert row.current_run_id != old_run
        assert session.get(models.SpectrumRun, old_run).result_json == old_result
        assert row.review_json == {}
