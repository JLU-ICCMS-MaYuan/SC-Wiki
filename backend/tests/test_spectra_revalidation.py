"""真实HTTP/存储的材料恢复；保留点与历史，独立验证拒绝边界。"""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend import models
from backend.services import spectra as service
from backend.spectra.engine import extract_panel
from backend.tests.test_spectra import fixture
from backend.tests.test_spectra_manual import manual_storage, manual_http


def snapshot(env):
    response=env["client"].get("/api/rag/spectra",params=env["query"])
    assert response.status_code==200,response.text
    return response.json()


def make_stale(env):
    env["draft"]["material_states"][0]["pressure_value_gpa"]=210
    current=snapshot(env)
    item=current["items"][0]
    return current,item


def body(env, listing, item, kind="alpha2f"):
    return {**env["query"],"expected_version":listing["version"],"expected_collection_version":item["version"],
            "base_run_id":item["run"]["id"],"kind":kind,"state_key":"s1","confirmed":True}


def url(env):
    return f"/api/rag/spectra/{env['identity']}/revalidate"


@pytest.mark.parametrize("kind",["alpha2f","phonon_dos"])
def test_revalidation_preserves_points_documents_and_old_run_and_unlocks(manual_http,kind):
    env=manual_http
    # 先生成有人工记录的真实保存文档，DOS使用其自身提取结果。
    if kind=="phonon_dos":
        rgb,panel=fixture(kind)
        with Session(env["engine"]) as session:
            run=session.get(models.SpectrumRun,env["old_run"])
            run.result_json=extract_panel(rgb,panel);run.calibration_json=panel;session.commit()
        params={**env["params"],"kind":kind}
        doc=env["client"].get(f"/api/rag/spectra/{env['identity']}/manual",params=params).json()["documents"][0]
    else:
        doc=copy.deepcopy(env["body"]["document"])
    doc["curves"][0]["points"][20]["y"]-=1
    doc["operations"].append(dict(kind="move",at="2026-10-27T00:00:00Z",detail="用户已有人工修订"))
    saved=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json={**env["body"],"document":doc})
    assert saved.status_code==200,saved.text
    old=saved.json()["items"][0]
    listing,item=make_stale(env)
    assert item["stale_reasons"]==["state_changed"]
    response=env["client"].post(url(env),json=body(env,listing,item,kind))
    assert response.status_code==200,response.text
    fresh=response.json()["items"][0]
    assert fresh["stale"] is False and fresh["stale_reasons"]==[]
    assert fresh["version"]==old["version"]+1 and fresh["run"]["id"]!=old["run"]["id"]
    assert fresh["result"]["curves"]==old["result"]["curves"]
    assert fresh["result"]["calibration"]==old["result"]["calibration"]
    assert fresh["result"]["manual_documents"]==old["result"]["manual_documents"]
    assert fresh["review"]=={} and fresh["result"]["candidates"]=={}
    assert fresh["result"]["quality"]["integrals"]["raw"]["status"]=="unavailable"
    provenance=fresh["result"]["state_revalidation"]
    assert provenance["base_run_id"]==old["run"]["id"] and provenance["author_id"]==1
    assert provenance["material_summary"]["pressure_value_gpa"]==210
    assert provenance["previous_state_signature"]!=provenance["state_signature"]
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumRun,old["run"]["id"]).result_json["curves"]==old["result"]["curves"]
    params={**env["params"],"kind":kind,"collection_version":fresh["version"],"run_id":fresh["run"]["id"]}
    assert env["client"].get(f"/api/rag/spectra/{env['identity']}/manual",params=params).status_code==200
    refreshed=snapshot(env)["items"][0]
    assert refreshed["run"]["id"]==fresh["run"]["id"] and not refreshed["stale"]
    recalculation={k:v for k,v in body(env,snapshot(env),fresh,kind).items() if k not in ("confirmed","state_key")}
    assert env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalculation).status_code==200


@pytest.mark.parametrize("problem",["unconfirmed","missing_confirmation","wrong_state","old_context","source_changed","state_missing","wrong_owner","already_current"])
def test_revalidation_refuses_without_conditions_and_never_changes_run(manual_http,problem):
    env=manual_http
    if problem=="already_current":
        listing=snapshot(env);item=listing["items"][0]
    else:listing,item=make_stale(env)
    request=body(env,listing,item)
    if problem=="unconfirmed":request["confirmed"]=False
    elif problem=="missing_confirmation":request.pop("confirmed")
    elif problem=="wrong_state":request["state_key"]="other"
    elif problem=="old_context":env["draft"]["material_states"][0]["pressure_value_gpa"]=220
    elif problem=="source_changed":
        with Session(env["engine"]) as session:
            row=session.get(models.SpectrumCollection,env["identity"]);row.source_json={**row.source_json,"source_sha256":"different"};session.commit()
    elif problem=="state_missing":
        env["draft"]["material_states"]=[]
        request["expected_version"]=snapshot(env)["version"]
    elif problem=="wrong_owner":env["actor"][0].id=999
    response=env["client"].post(url(env),json=request)
    assert response.status_code in {403,409,422},response.text
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumCollection,env["identity"]).current_run_id==env["old_run"]
        assert session.scalar(select(func.count()).select_from(models.SpectrumRun).where(models.SpectrumRun.collection_id==env["identity"]))==1


def test_revalidation_refuses_history_collection(manual_http):
    env=manual_http
    with Session(env["engine"]) as session:
        ctx=service.context(session,**env["query"],user=env["actor"][0])
        old=session.get(models.SpectrumCollection,env["identity"])
        image,panel=fixture()
        row=service.collection(session,ctx,"new-source","new-panel",copy.deepcopy(old.source_json))
        run,_=service.new_run(session,row,panel,ctx["states"][0]);service.complete_run(run,extract_panel(image,panel));service.activate(row,run,ctx["states"][0])
        from datetime import timedelta
        run.created_at=session.get(models.SpectrumRun,env["old_run"]).created_at+timedelta(minutes=1)
        session.commit()
    listing,_=make_stale(env)
    item=next(i for i in listing["items"] if i["id"]==env["identity"])
    response=env["client"].post(url(env),json=body(env,listing,item))
    assert response.status_code==409 and "历史谱集合" in response.text


def test_revalidation_provenance_is_private(manual_http):
    env=manual_http;listing,item=make_stale(env)
    fresh=env["client"].post(url(env),json=body(env,listing,item)).json()["items"][0]
    public=service.mask_public(fresh["result"],{"a":{"status":"accepted"}})
    assert "state_revalidation" not in public


def test_mysql_revalidation_row_lock_only_one_confirmation(manual_http):
    env=manual_http
    if env["engine"].dialect.name!="mysql":pytest.skip("行锁竞争仅当前MySQL验证")
    listing,item=make_stale(env);request=body(env,listing,item);barrier=Barrier(2)
    def post(_):
        barrier.wait(timeout=10)
        return env["client"].post(url(env),json=request).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(post,[1,2]))==[200,409]
    with Session(env["engine"]) as session:
        assert session.scalar(select(func.count()).select_from(models.SpectrumRun).where(models.SpectrumRun.collection_id==env["identity"]))==2
