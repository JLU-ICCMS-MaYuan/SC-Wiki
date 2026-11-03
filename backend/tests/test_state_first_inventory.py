"""#211：状态规划不靠未知压力生成额外卡，候选与来源必须守恒。"""
import json
import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
from copy import deepcopy
import numpy as np
import pytest

def test_black_curve_samples_real_pixels_and_excludes_frame():
    from backend.spectra.digitize import extract_curve, LinearAxis
    rgb = np.full((100, 140, 3), 255, dtype=np.uint8)
    rgb[10, 10:131] = 0; rgb[90, 10:131] = 0
    rgb[10:91, 10] = 0; rgb[10:91, 130] = 0
    rgb[50, 11:130] = 30
    spec = dict(id="dos", kind="phonon_dos", projection=None, color="black", unit="pixel",
                roi=[10, 10, 130, 90], frequency_direction="x", amplitude_ticks=[[90,0],[10,80]],
                exclude=[], max_gap_px=0)
    curve = extract_curve(rgb, spec, LinearAxis.fit([[10,0],[130,12]]))
    observed = [p for p in curve["points"] if p["observed_amplitude"] is not None]
    assert len(observed) > 100
    assert all(p["amplitude_pixel"] == pytest.approx(50) for p in observed)

def test_inventory_assigns_unknown_dos_to_existing_state_without_extra_card():
    from backend.ingest.state_inventory import apply_inventory
    original = [dict(state_key="old", material="CaH4", pressure_value_gpa=None,
                     property_modules=[dict(module_key="electronic", module_code="electronic_properties",
                     records=[dict(record_key="dos", property_code="dos_fermi", value_number=.02234)])])]
    sources = [dict(source_id="s0", file_id="si", page_start=10, block_id="figs6", content="CaH4 phonon DOS at 50, 150 and 200 GPa.")]
    values = lambda p: dict(material="CaH4", material_name=None, pressure_value_gpa=p,
        reported_space_group_symbol="I4/mmm" if p!=200 else "Cmcm", reported_space_group_number=None,
        state_kind="theoretical", structure_optimization="classical_static")
    plan = dict(states=[dict(values=values(p), source_ids=["s0"], reason="图注条件") for p in [50,150,200]],
        assignments=[dict(candidate_state_key="old", target_index=0, status="uncertain",
                          reason="数值属于50或150 GPa，先放50待查原图", source_ids=["s0"])])
    d = dict(material_states=deepcopy(original))
    apply_inventory(d, sources, plan)
    assert [s["pressure_value_gpa"] for s in d["material_states"]] == [50,150,200]
    assert [r["record_key"] for s in d["material_states"] for m in s["property_modules"] for r in m["records"]] == ["dos"]
    assert d["generation_issues"][0]["code"] == "state_assignment_uncertain"
    assert original[0]["pressure_value_gpa"] is None

def test_inventory_rejects_lost_candidate_and_unknown_source():
    from backend.ingest.state_inventory import apply_inventory
    d = dict(material_states=[dict(state_key="one",material="H",property_modules=[])])
    with pytest.raises(ValueError):
        apply_inventory(d, [], dict(states=[],assignments=[]))

def test_ready_and_timing_are_not_published_until_automatic_spectra_finish(monkeypatch):
    from backend.ingest import upload_jobs
    from backend.spectra import jobs
    events = []
    def update(task, **values):
        events.append(values)
        return values
    def spectra(task):
        assert events[-1]["processing_stage"] == "spectra"
        assert not any(e.get("status") == "ready" for e in events)
        events.append({"spectra_finished": True})
    monkeypatch.setattr(upload_jobs, "update_state", update)
    monkeypatch.setattr(jobs, "run_upload", spectra)
    result = upload_jobs.complete_parsing_state("task", {}, include_spectra=True)
    assert result["status"] == "ready"
    assert events[-2] == {"spectra_finished": True}

def test_spectra_technical_failure_does_not_publish_ready(monkeypatch):
    from backend.ingest import upload_jobs
    from backend.spectra import jobs
    published = []
    monkeypatch.setattr(upload_jobs, "update_state", lambda *a, **k: published.append(k))
    def fail(*args):
        raise RuntimeError("读图服务不可用")
    monkeypatch.setattr(jobs, "run_upload", fail)
    with pytest.raises(RuntimeError):
        upload_jobs.complete_parsing_state("task", {}, include_spectra=True)
    assert not any(e.get("status") == "ready" for e in published)

def test_target_identity_survives_no_calibrated_curve():
    from backend.spectra.contracts import PanelCalibration
    panel = PanelCalibration.model_validate(dict(panel_id="S15-150", state_key="150", kind="phonon_dos",
        caption="CaH6 150 GPa", curves=[]))
    assert panel.state_key == "150" and panel.kind == "phonon_dos"
    with pytest.raises(ValueError):
        PanelCalibration.model_validate(dict(panel_id="electronic", curves=[]))

def test_deleting_upload_removes_its_spectra_and_preserves_other_tasks():
    from sqlalchemy import create_engine,select
    from sqlalchemy.orm import Session
    from backend import models
    from backend.workdraft_models import ScientificWorkDraft,ScientificFieldSourceUse
    from backend.ingest.scientific_evidence import delete_target
    engine=create_engine("sqlite:///:memory:")
    tables=[models.ScientificEvidenceCheck,models.ScientificStructureOrigin,models.ScientificUploadDraft,
            ScientificWorkDraft,ScientificFieldSourceUse,models.SpectrumCollection,models.SpectrumRun]
    models.Base.metadata.create_all(engine,tables=[t.__table__ for t in tables])
    with Session(engine) as session:
        for key,target in [("a","cah6"),("b","h3s")]:
            session.add(models.SpectrumCollection(id=key,target="upload",target_id=target,owner_id=1,
                state_signature="sig",source_key=key,panel_key="p",source_json={},current_run_id=key))
            session.flush()
            session.add(models.SpectrumRun(id=key,collection_id=key,input_hash=key,algorithm_version="test",status="needs_review"))
        session.commit()
        delete_target(session,"upload","cah6");session.commit()
        assert list(session.scalars(select(models.SpectrumCollection.id))) == ["b"]
        assert list(session.scalars(select(models.SpectrumRun.id))) == ["b"]
    engine.dispose()

def test_completed_field_review_resumes_only_spectra(monkeypatch):
    from backend.ingest import upload_resume,upload_tasks,upload_jobs
    state=dict(status='queued',reading_state="extracting_spectra")
    draft=dict(_form_contract_version=1,material_states=[{"state_key":"kept"}],
               form_filling_report={"status":"completed"},
               model_review_report={"unfinished_fields":0,"errors":[]})
    monkeypatch.setattr(upload_tasks,"get_state",lambda _:state)
    monkeypatch.setattr(upload_tasks,"get_draft",lambda _:draft)
    monkeypatch.setattr(upload_tasks,"update_state",lambda *a,**k:k)
    calls=[]
    monkeypatch.setattr(upload_jobs,"complete_parsing_state",lambda task,body,**kw:calls.append((body,kw)) or {"status":"ready"})
    monkeypatch.setattr(upload_jobs,"_schedule_terminal_cleanup",lambda _:None)
    assert upload_resume.resume_spectra("task")["status"]=="ready"
    assert calls==[(draft,{"include_spectra":True})]
    state["_field_baselines"]={"changed":{"value_origin":"human_input"}}
    assert upload_resume.resume_spectra("task") is None
    assert len(calls)==1

def test_worker_failure_closes_only_its_owned_automatic_spectrum(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend import models
    from backend.spectra import jobs
    engine=create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine,tables=[models.SpectrumCollection.__table__,models.SpectrumRun.__table__])
    sessions=sessionmaker(engine)
    monkeypatch.setattr(jobs,"SessionLocal",sessions)
    with sessions.begin() as db:
        for key,owner in [("auto","parent"),("manual",None),("other","different-parent")]:
            db.add(models.SpectrumCollection(id=key,target="upload",target_id="task",owner_id=1,
                state_signature="sig",source_key=key,panel_key=key,source_json={}))
            db.flush()
            db.add(models.SpectrumRun(id=key,collection_id=key,input_hash=key,algorithm_version="test",
                status="running",calibration_json={"automatic_upload_job_id":owner}))
    jobs.fail_upload_runs("task","parent","父任务中断")
    with sessions() as db:
        assert db.get(models.SpectrumRun,"auto").status=="failed"
        assert db.get(models.SpectrumRun,"manual").status=="running"
        assert db.get(models.SpectrumRun,"other").status=="running"
    engine.dispose()

def test_late_worker_failure_cannot_stop_new_attempt(monkeypatch):
    from types import SimpleNamespace
    from backend.ingest import upload_tasks
    key="a"*32
    monkeypatch.setattr(upload_tasks,"get_state",lambda _:{"status":"summarizing","job_id":"new"})
    writes=[]
    monkeypatch.setattr(upload_tasks,"update_state",lambda *a,**k:writes.append(k))
    assert upload_tasks.handle_upload_job_failure(SimpleNamespace(args=(key,),id="old"),RuntimeError,RuntimeError("old"),None)
    assert not writes

def test_black_border_ticks_cannot_become_curve_observations():
    from backend.spectra.digitize import extract_curve,LinearAxis
    rgb=np.full((100,140,3),255,dtype=np.uint8)
    rgb[10,10:131]=0;rgb[90,10:131]=0
    rgb[10:91,10]=0;rgb[10:91,130]=0
    rgb[10:19,30:32]=0  # 边缘刻度
    rgb[12,70]=0       # 裁切后只剩一像素的刻度端点也不是曲线证据
    rgb[12:24,11]=0     # 贴轴不可分辨，不能拿刻度补位
    rgb[24:89,50]=0
    spec=dict(id="alpha",kind="alpha2f",projection=None,color="black",unit="pixel",
        roi=[10,10,130,90],frequency_direction="y",amplitude_ticks=[[10,0],[130,120]],exclude=[])
    curve=extract_curve(rgb,spec,LinearAxis.fit([[10,8],[90,0]]))
    assert all(p["observed_amplitude"] is None for p in curve["points"] if 12<=p["frequency_pixel"]<=18)
    assert next(p for p in curve["points"] if p["frequency_pixel"]==50)["amplitude_pixel"]==50

def test_fixed_form_uses_owned_field_values_instead_of_condition_packages(monkeypatch):
    from backend.ingest import model_review,property_evidence as ev
    from backend.ingest.fixed_form_contract import parameter_paths
    assert dict(parameter_paths({}))["qe.q_grid"] is None
    def rebuild(draft):
        row=dict(key="year",item_key="year",field="paper.year",kind="field",current_value=draft["paper"]["year"],
            claim={"value":draft["paper"]["year"]},required=True,evidences=[],label="年份")
        return ev.complete_snapshot("upload","fixed",[row],[dict(file_id="main",content="Published in 2012.")],{})
    def review(rows,chunks,**kwargs):
        assert kwargs["allow_condition_additions"] is False
        return {r["key"]:model_review.bind_result(r,dict(status="supported",reason="原文报告",
            evidences=[{"file_id":"main","quote":"Published in 2012."}],
            proposal=dict(values={"":2012},unique=True,final_verified=True,evidences=[{"file_id":"main","quote":"Published in 2012."}])),chunks) for r in rows}
    monkeypatch.setattr(model_review,"review_fields",review)
    monkeypatch.setattr(model_review,"_add_conditions",lambda *a:(_ for _ in ()).throw(AssertionError("不能走旧整包旁路")))
    updated,_,_,report=model_review.review_draft(dict(_form_contract_version=1,paper={"year":None},material_states=[]),rebuild)
    assert updated["paper"]["year"]==2012 and not report["errors"]
