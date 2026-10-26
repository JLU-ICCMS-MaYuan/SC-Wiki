"""正式路由 + 真实SQLite文件存储；身份由测试依赖提供，权限由正式context校验。"""
import copy
import json
import os
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend import models
from backend.api import spectra as routes
from backend.database import get_db
from backend.security import get_current_user, get_current_user_optional
from backend.ingest import upload_tasks
from backend.services import spectra as service
from backend.spectra.engine import extract_panel
from backend.spectra.contracts import state_signature
from backend.tests.test_spectra import fixture


@pytest.fixture
def manual_http(tmp_path, monkeypatch):
    engine=create_engine(os.environ.get("SCWIKI_MANUAL_TEST_DATABASE_URL") or "sqlite:///"+str(tmp_path/"manual.sqlite"))
    if engine.dialect.name == "mysql":
        assert "issue161_test_" in engine.url.database, "拒绝向非隔离测试库写入"
        with engine.begin() as connection:
            # 只为谱表外键准备隔离空父表；业务父表路径不属于本测试。
            for name in ("papers","paper_files","material_states"):
                sql_type=models.Base.metadata.tables[name].c.id.type.compile(dialect=engine.dialect)
                connection.execute(text(f"CREATE TABLE IF NOT EXISTS `{name}` (id {sql_type} PRIMARY KEY)"))
        models.Base.metadata.create_all(engine,tables=[models.SpectrumCollection.__table__,models.SpectrumRun.__table__])
        with engine.begin() as connection:
            connection.execute(models.SpectrumRun.__table__.delete())
            connection.execute(models.SpectrumCollection.__table__.delete())
    models.Base.metadata.create_all(engine,tables=[models.SpectrumCollection.__table__,models.SpectrumRun.__table__])
    actor=[SimpleNamespace(id=1,role="user",is_approved=True)]
    draft={"material_states":[dict(state_key="s1",material="H3S",pressure_value_gpa=200,property_modules=[])]}
    monkeypatch.setattr(upload_tasks,"get_state",lambda identity:dict(user_id=1,status="ready",files=[dict(file_id="main",kind="pdf",role="main",sha256="source")]) if identity=="manual-task" else None)
    monkeypatch.setattr(upload_tasks,"get_draft",lambda _:draft)
    def db():
        with Session(engine) as session:yield session
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[get_db]=db
    app.dependency_overrides[get_current_user]=lambda:actor[0]
    app.dependency_overrides[get_current_user_optional]=lambda:actor[0]
    query=dict(target="upload",target_id="manual-task")
    with Session(engine) as session:
        ctx=service.context(session,**query,user=actor[0],write=True)
        rgb,panel=fixture();row=service.collection(session,ctx,"source","panel",dict(source_sha256="source",size_px=[160,100],pdf_page=1))
        run,_=service.new_run(session,row,panel,ctx["states"][0]);service.complete_run(run,extract_panel(rgb,panel));service.activate(row,run,ctx["states"][0])
        row.review_json={"a":{"status":"accepted"}};session.commit()
        identity,old_run,old_result=row.id,run.id,copy.deepcopy(run.result_json)
    with TestClient(app) as client:
        listing=client.get("/api/rag/spectra",params=query).json();item=listing["items"][0]
        params={**query,"kind":"alpha2f","collection_version":item["version"],"run_id":item["run"]["id"]}
        response=client.get(f"/api/rag/spectra/{identity}/manual",params=params)
        assert response.status_code==200,response.text
        seed=response.json()
        body={**query,"expected_version":seed["version"],"expected_collection_version":seed["collection_version"],"base_run_id":seed["base_run_id"],"document":seed["documents"][0]}
        yield dict(client=client,engine=engine,actor=actor,draft=draft,query=query,params=params,body=body,identity=identity,old_run=old_run,old_result=old_result)
    engine.dispose()


def test_manual_http_persistent_new_run_zero_history_and_conflict(manual_http):
    env=manual_http;body=copy.deepcopy(env["body"]);doc=body["document"]
    doc["curves"][0]["points"][10]["y"]-=2
    zero=next(p for p in doc["curves"][0]["points"] if p["x"]==20)
    doc["zero"]={"pixel":20,"pointIds":[zero["id"]]}
    doc["operations"].append(dict(kind="zero-point-confirm",at="2026-10-26T00:00:00Z",detail="用户明确确认"))
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body)
    assert response.status_code==200,response.text
    item=response.json()["items"][0];new_run=item["run"]["id"]
    assert new_run!=env["old_run"] and item["version"]==body["expected_collection_version"]+1
    assert item["review"]=={} and item["result"]["candidates"]=={}
    assert item["result"]["quality"]["integrals"]["raw"]["status"]=="unavailable"
    assert item["result"]["quality"]["manual_zero_checks"]["a"]["complete"]
    assert item["result"]["curves"][0]["points"][10]["status"]=="manual_adjusted"
    assert item["result"]["curves"][0]["points"][10]["observed_amplitude"] is None
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumRun,env["old_run"]).result_json==env["old_result"]
        assert session.get(models.SpectrumRun,new_run).result_json["manual_provenance"]["author_id"]==1
        assert session.get(models.SpectrumCollection,env["identity"]).current_run_id==new_run
    fresh=env["client"].get("/api/rag/spectra",params=env["query"]).json()["items"][0]
    assert fresh["result"]["manual_documents"]["a"]["curves"][0]["points"]==doc["curves"][0]["points"]
    history=env["client"].get(f"/api/rag/spectra/{env['identity']}/history",params=env["query"]).json()["items"]
    assert len(history)==2 and next(h for h in history if h["id"]==new_run)["current"]
    assert env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body).status_code==409
    assert env["client"].get(f"/api/rag/spectra/{env['identity']}/manual",params=env["params"]).status_code==409


@pytest.mark.parametrize("mutation",["pixel","identity","source","axis","zero","unknown_field","duplicate","unit","shape","missing_zero","overflow"])
def test_manual_invalid_input_rolls_back(manual_http,mutation):
    env=manual_http;body=copy.deepcopy(env["body"]);doc=body["document"]
    if mutation=="pixel":doc["curves"][0]["points"][0]["x"]=-5
    if mutation=="identity":doc["curves"][0]["id"]="foreign"
    if mutation=="source":doc["source"]["width"]=999
    if mutation=="axis":doc["calibration"]["frequency"]["pixels"]=[20,20]
    if mutation=="zero":doc["zero"]={"pixel":20,"pointIds":["fake-point"]}
    if mutation=="unknown_field":doc["quality"]={"accepted":True}
    if mutation=="duplicate":doc["curves"][0]["points"].append(doc["curves"][0]["points"][0])
    if mutation=="unit":doc["calibration"]["frequency"]["unit"]="GHz"
    if mutation=="shape":doc["curves"]=[42]
    if mutation=="missing_zero":del doc["zero"]
    if mutation=="overflow":
        doc["calibration"]["frequency"]["values"]=[-1e308,1e308]
        doc["curves"][0]["points"]=[]
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body)
    assert response.status_code==422,response.text
    with Session(env["engine"]) as session:
        assert session.scalar(select(func.count()).select_from(models.SpectrumRun))==1
        assert session.get(models.SpectrumCollection,env["identity"]).current_run_id==env["old_run"]


def test_manual_permissions_target_and_stale_context(manual_http):
    e=manual_http;url=f"/api/rag/spectra/{e['identity']}/manual"
    e["actor"][0]=SimpleNamespace(id=2,role="user",is_approved=True)
    assert e["client"].get(url,params=e["params"]).status_code==403
    assert e["client"].post(url,json=e["body"]).status_code==403
    e["actor"][0]=SimpleNamespace(id=1,role="user",is_approved=True)
    e["draft"]["material_states"][0]["pressure_value_gpa"]=210
    assert e["client"].post(url,json=e["body"]).status_code==409
    assert e["client"].get(url,params=e["params"]).status_code==409


def test_manual_public_mask_removes_private_edit_documents(manual_http):
    e=manual_http;res=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=e["body"])
    assert res.status_code==200
    payload=res.json()["items"][0]["result"]
    public=service.mask_public(payload,{"a":{"status":"accepted_limited","frequency_intervals_thz":[[1,2]]}})
    assert "manual_documents" not in public and "manual_provenance" not in public
    assert "manual_zero_checks" not in public["quality"]
    assert all(1<=p["frequency_thz"]<=2 for p in public["curves"][0]["points"])
    assert service.mask_public(payload,{})["curves"]==[]


def test_manual_units_are_recomputed_and_other_curves_preserved(manual_http):
    e=manual_http
    with Session(e["engine"]) as session:
        run=session.get(models.SpectrumRun,e["old_run"])
        payload=copy.deepcopy(run.result_json);other=copy.deepcopy(payload["curves"][0]);other.update(id="lambda",kind="cumulative_lambda")
        payload["curves"].append(other);run.result_json=payload;session.commit()
    body=copy.deepcopy(e["body"]);axis=body["document"]["calibration"]["frequency"]
    axis["unit"]="meV";axis["values"]=[0,60]
    result=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body)
    assert result.status_code==200,result.text
    payload=result.json()["items"][0]["result"]
    assert payload["curves"][0]["points"][-1]["frequency_thz"]==pytest.approx(60*.2417989242084918)
    assert payload["curves"][1]==other


def test_manual_rejects_old_collection_even_with_matching_version(manual_http):
    e=manual_http
    from datetime import datetime, timedelta, timezone
    with Session(e["engine"]) as session:
        ctx=service.context(session,**e["query"],user=e["actor"][0],write=True)
        row=service.collection(session,ctx,"new-source","new-panel",dict(source_sha256="source",size_px=[160,100]))
        image,panel=fixture();run,_=service.new_run(session,row,panel,ctx["states"][0]);service.complete_run(run,extract_panel(image,panel));service.activate(row,run,ctx["states"][0])
        run.created_at=datetime.now(timezone.utc)+timedelta(minutes=1);session.commit()
    assert e["client"].get(f"/api/rag/spectra/{e['identity']}/manual",params=e["params"]).status_code==409
    assert e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=e["body"]).status_code==409


def test_manual_trace_frequency_return_can_save_but_not_be_accepted(manual_http):
    e=manual_http;body=copy.deepcopy(e["body"])
    body["document"]["curves"][0]["points"][10]["x"]=60
    result=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body)
    assert result.status_code==200
    with Session(e["engine"]) as session:
        ctx=service.context(session,**e["query"],user=e["actor"][0],write=True);ctx["can_review"]=True
        row=session.get(models.SpectrumCollection,e["identity"])
        with pytest.raises(Exception) as exc:service.review_curve(session,ctx,row,"a","accepted",[],"",e["actor"][0])
        assert exc.value.status_code==422


def test_manual_zero_candidate_not_auto_confirmed_and_deleted_point_invalidates(manual_http):
    e=manual_http;body=copy.deepcopy(e["body"]);doc=body["document"]
    doc["zero"]={"pixel":20,"pointIds":[]}
    response=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body)
    assert response.status_code==200
    item=response.json()["items"][0]
    assert item["result"]["quality"]["manual_zero_checks"]["a"]["curves"][0]["status"]=="needs_confirmation"
    doc=copy.deepcopy(item["result"]["manual_documents"]["a"])
    doc["zero"]["pointIds"]=[doc["curves"][0]["points"][0]["id"]]
    body.update(document=doc,base_run_id=item["run"]["id"],expected_collection_version=item["version"])
    confirmed=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body).json()["items"][0]
    assert confirmed["result"]["quality"]["manual_zero_checks"]["a"]["complete"]
    doc["curves"][0]["points"][0]["x"]+=.1
    body.update(document=doc,base_run_id=confirmed["run"]["id"],expected_collection_version=confirmed["version"])
    moved=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body).json()["items"][0]
    assert not moved["result"]["quality"]["manual_zero_checks"]["a"]["complete"]


def test_manual_export_contains_current_pixels_and_provenance(manual_http):
    import csv, io
    e=manual_http;body=copy.deepcopy(e["body"]);body["document"]["curves"][0]["points"][10]["y"]-=2
    result=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=body)
    assert result.status_code==200
    exported=e["client"].get(f"/api/rag/spectra/{e['identity']}/export",params={**e["query"],"format":"csv"})
    assert exported.status_code==200
    rows=list(csv.DictReader(io.StringIO(exported.text)))
    assert rows[10]["manual"]=="True" and rows[10]["point_id"]==body["document"]["curves"][0]["points"][10]["id"]
    assert rows[10]["base_run_id"]==e["old_run"] and float(rows[10]["amplitude_pixel"])==body["document"]["curves"][0]["points"][10]["y"]


def test_manual_revision_copy_rebinds_identity_without_touching_saved_document(manual_http):
    from backend.spectra.manual import editor_document
    e=manual_http
    response=e["client"].post(f"/api/rag/spectra/{e['identity']}/manual",json=e["body"])
    payload=response.json()["items"][0]["result"];before=copy.deepcopy(payload)
    copied=editor_document(SimpleNamespace(id="new-revision-collection"),SimpleNamespace(result_json=payload),payload["curves"][0])
    assert copied["id"]=="new-revision-collection:a" and copied["source"]["id"]=="new-revision-collection"
    assert copied["recognizedAxes"]["sourceId"]=="new-revision-collection"
    assert copied["curves"]==payload["manual_documents"]["a"]["curves"] and payload==before
