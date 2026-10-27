"""浏览器集成验证专用：正式谱路由、隔离SQLite与本地文件；不连接业务服务。"""
import copy
import io
import os
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from PIL import Image

test_root=Path(os.environ["SCWIKI_MANUAL_TEST_ROOT"]).resolve()
assert str(test_root).startswith("/tmp/scwiki-manual-test-") or str(test_root).startswith("/private/tmp/scwiki-manual-test-")
assert os.environ["DATABASE_URL"].startswith("sqlite:") and "scwiki-manual-test-" in os.environ["DATABASE_URL"]
from backend import models
from backend.api.spectra import router
from backend.database import get_db
from backend.security import get_current_user, get_current_user_optional
from backend.ingest import upload_tasks
from backend.storage import create_storage
from backend.services import spectra as service
from backend.spectra.engine import extract_panel
from backend.tests.test_spectra import fixture

engine=create_engine(os.environ["DATABASE_URL"])
models.Base.metadata.create_all(engine,tables=[models.SpectrumCollection.__table__,models.SpectrumRun.__table__])
owner=SimpleNamespace(id=161,role="user",is_approved=True)
states=[dict(state_key="s1",material="H3S",material_name="隔离浏览器验证",pressure_value_gpa=200,property_modules=[])]
task="manual-test"
upload_tasks.get_state=lambda identity: dict(user_id=owner.id,status="ready",files=[dict(file_id="main",kind="pdf",role="main",sha256="synthetic-source")]) if identity==task else None
upload_tasks.get_draft=lambda identity:dict(material_states=states) if identity==task else None
identities={}
with Session(engine) as session:
    ctx=service.context(session,"upload",task,owner,write=True)
    rgb,panel=fixture();content=io.BytesIO();Image.fromarray(rgb).save(content,format="PNG");content.seek(0)
    image=create_storage().put("spectra/test.png",content,"image/png")
    for kind in ("alpha2f","phonon_dos"):
        rgb,panel=fixture(kind)
        if os.environ.get("SCWIKI_REVALIDATE_TEST_FIXTURES")=="1" and kind=="alpha2f":
            panel["curves"][0]["amplitude_evidence"]=None
            panel["caption"]="合成原图：H3S，200 GPa"
        if kind=="phonon_dos" and os.environ.get("SCWIKI_RECALCULATE_TEST_FIXTURES")=="1":
            panel["curves"][0]["unit"]="modes/THz/primitive_cell"
            panel.update(projection_complete=True,projection_scale_confirmed=True)
        if kind=="phonon_dos":
            prototype=panel["curves"][0];panel["curves"]=[]
            for name in ["La","Sc","H"]:
                curve=copy.deepcopy(prototype);curve.update(id=name,projection=name);panel["curves"].append(curve)
        row=service.collection(session,ctx,kind,kind,dict(source_sha256="synthetic-source",image=asdict(image),size_px=[160,100],pdf_page=1,source_name="人工编辑隔离测试图"))
        run,_=service.new_run(session,row,panel,ctx["states"][0]);service.complete_run(run,extract_panel(rgb,panel));service.activate(row,run,ctx["states"][0])
        identities[kind]=row.id
    session.commit()

if os.environ.get("SCWIKI_REVALIDATE_TEST_FIXTURES")=="1":
    # 模拟材料模块更新、来源原图不变；仅浏览器专用服务，未提供业务写入入口。
    states[0]["property_modules"]=[dict(module_code="superconductive_properties",records=[])]

def database():
    with Session(engine) as session:yield session

def actor(request:Request):
    return SimpleNamespace(id=999,role="user",is_approved=True) if request.headers.get("authorization")=="Bearer stranger" else owner

app=FastAPI();app.include_router(router)
app.dependency_overrides[get_db]=database
app.dependency_overrides[get_current_user]=actor
app.dependency_overrides[get_current_user_optional]=actor

@app.get("/test-info")
def info():
    return dict(target="upload",target_id=task,identities=identities)

@app.get("/api/rag/upload-tasks/{identity}/draft")
def draft(identity:str):
    assert identity==task
    return dict(data=dict(material_states=states))

@app.get("/api/auth/me")
def auth():
    return dict(user=dict(id=owner.id,username="isolated_validation",role="user",is_approved=True,account_status="active",is_email_verified=True))

@app.get("/api/{rest:path}")
def unrelated_read(rest:str):
    return dict(items=[],count=0,unread_count=0)
