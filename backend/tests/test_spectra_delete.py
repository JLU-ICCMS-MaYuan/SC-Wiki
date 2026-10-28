"""草稿谱删除走正式 HTTP/事务；隔离 SQLite 不写当前业务库。"""
import copy
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.tests.test_spectra import fixture, db_session, setup_collection
from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend import models
from backend.services import spectra as service


def prepare(env, *, empty=False, state_key=None):
    with Session(env["engine"]) as session:
        row = session.get(models.SpectrumCollection, env["identity"])
        row.state_key = state_key
        run = session.get(models.SpectrumRun, row.current_run_id)
        if empty:
            run.result_json = dict(curves=[], failures=["HTTP 503"], quality={}, candidates={})
            run.calibration_json = None
        # 两次运行都必须删除，另一个已归属集合复用来源但必须保留。
        extra = models.SpectrumRun(id="previous", collection_id=row.id, input_hash="previous",
            algorithm_version="test", status="failed", result_json={})
        session.add(extra)
        ctx = service.context(session, **env["query"], user=env["actor"][0])
        other = service.collection(session, ctx, row.source_key, "keep", copy.deepcopy(row.source_json))
        other.state_key = "s1"
        kept, _ = service.new_run(session, other, {}, ctx["states"][0])
        service.complete_run(kept, copy.deepcopy(env["old_result"]))
        service.activate(other, kept, ctx["states"][0])
        session.commit()
        env["keep"] = other.id
    listing = env["client"].get("/api/rag/spectra", params=env["query"]).json()
    item = next(i for i in listing["items"] if i["id"] == env["identity"])
    return {**env["query"], "expected_version": listing["version"], "expected_collection_version": item["version"]}


def remove(env, params):
    return env["client"].delete(f"/api/rag/spectra/{env['identity']}", params=params)


@pytest.mark.parametrize("empty,state_key", [(False, None), (True, None), (False, "removed-state")])
def test_delete_persists_removes_all_runs_and_preserves_other_spectra(manual_http, empty, state_key):
    env = manual_http
    params = prepare(env, empty=empty, state_key=state_key)
    response = remove(env, params)
    assert response.status_code == 200, response.text
    assert [i["id"] for i in response.json()["items"]] == [env["keep"]]
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumCollection, env["identity"]) is None
        assert session.scalar(select(func.count()).select_from(models.SpectrumRun).where(
            models.SpectrumRun.collection_id == env["identity"])) == 0
        kept = session.get(models.SpectrumCollection, env["keep"])
        assert session.get(models.SpectrumRun, kept.current_run_id).result_json == env["old_result"]
    assert remove(env, params).status_code == 404
    for suffix in ("history", "export", "image"):
        assert env["client"].get(f"/api/rag/spectra/{env['identity']}/{suffix}", params=env["query"]).status_code == 404


@pytest.mark.parametrize("problem,status", [("owner", 403), ("target", 404), ("context", 409),
    ("version", 409), ("assigned", 409), ("running", 409), ("discovery", 409), ("paper", 422), ("submitted", 409)])
def test_delete_rejects_unauthorized_stale_assigned_or_busy_without_changes(manual_http, monkeypatch, problem, status):
    env = manual_http
    params = prepare(env)
    if problem == "owner": env["actor"][0].id = 999
    elif problem == "target": params["target_id"] = "foreign"
    elif problem == "context": params["expected_version"] = "old"
    elif problem == "version": params["expected_collection_version"] += 1
    elif problem == "paper": params["target"] = "paper"
    elif problem == "submitted":
        from backend.ingest import upload_tasks
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: dict(user_id=1, status="submitted", paper_id=10))
    else:
        with Session(env["engine"]) as session:
            row = session.get(models.SpectrumCollection, env["identity"])
            if problem == "assigned": row.state_key = "s1"
            elif problem == "running": session.get(models.SpectrumRun, row.current_run_id).status = "running"
            else:
                ctx = service.context(session, **env["query"], user=env["actor"][0])
                job = service.collection(session, ctx, "all", "__discovery__", {})
                service.new_run(session, job, {}, None)
            session.commit()
    response = remove(env, params)
    assert response.status_code == status, response.text
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumCollection, env["identity"])
        assert session.get(models.SpectrumRun, env["old_run"])
        assert session.get(models.SpectrumRun, "previous")


def test_revision_delete_and_transaction_rollback(db_session):
    ctx, row, run, _, _ = setup_collection(db_session)
    ctx["target"] = row.target = "revision"
    row.state_key = None
    db_session.commit()
    identity, run_id = row.id, run.id
    service.delete_unassigned(db_session, ctx, identity, row.version)
    db_session.rollback()
    assert db_session.get(models.SpectrumCollection, identity)
    assert db_session.get(models.SpectrumRun, run_id)
    service.delete_unassigned(db_session, ctx, identity, row.version)
    db_session.commit()
    assert db_session.get(models.SpectrumCollection, identity) is None


def test_submit_binds_kept_records_but_cannot_bind_deleted_record(db_session, monkeypatch):
    # 用同步会话承载相同 SQL，异步适配只桥接执行；实际运行正式 bind_to_paper。
    ctx, row, run, _, state = setup_collection(db_session)
    row.state_key = None
    deleted_id, deleted_run = row.id, run.id
    keep = service.collection(db_session, ctx, "source", "keep-unassigned", {})
    keep_id = keep.id
    db_session.commit()
    service.delete_unassigned(db_session, ctx, deleted_id, row.version)
    db_session.commit()
    models.Base.metadata.create_all(db_session.get_bind(), tables=[models.MaterialState.__table__, models.PaperFile.__table__])
    from backend.services import paper_revisions
    monkeypatch.setattr(paper_revisions, "current_draft", lambda *_: {"material_states": [state]})

    class AsyncSessionAdapter:
        async def run_sync(self, callback): return callback(db_session)
        async def scalars(self, query): return db_session.scalars(query)
        async def scalar(self, query): return db_session.scalar(query)
        async def flush(self): db_session.flush()

    asyncio.run(service.bind_to_paper(AsyncSessionAdapter(), SimpleNamespace(id=10, content_revision=1), {},
        target=ctx["target"], target_id=ctx["target_id"]))
    db_session.commit()
    assert db_session.get(models.SpectrumCollection, deleted_id) is None
    assert db_session.get(models.SpectrumRun, deleted_run) is None
    retained = db_session.get(models.SpectrumCollection, keep_id)
    assert (retained.target, retained.paper_id, retained.material_state_id) == ("paper", 10, None)
