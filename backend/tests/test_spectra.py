"""共享谱数学、模型标定合同、物理对照与独立审核边界。"""
import copy
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
import io
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from fastapi import HTTPException
from backend import models
from backend.storage import FileNotFound
from backend.spectra.engine import extract_panel, comparison
from backend.spectra.contracts import PanelCalibration, state_signature
from backend.spectra.discovery import calibrate, pdf_figures
from backend.services import spectra as service
from backend.spectra.context import references_for
from backend.spectra.context import primitive_for


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    engine=create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine, tables=[models.SpectrumCollection.__table__, models.SpectrumRun.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def fixture(kind="alpha2f", unit="THz"):
    rgb=np.full((100,160,3),255,dtype=np.uint8)
    rgb[79:82,20:141]=0
    for x in range(20,141):
        # 原频率0–6，α²F=0.01ν，零频端来自实际有色像素。
        y=80-round((x-20)/20*2)
        rgb[y,x]=[0,128,0]
    c=dict(id="a",kind=kind,projection="H" if kind=="phonon_dos" else None,color="green",
           roi=[20,10,140,80],frequency_direction="x",frequency_ticks=[[20,0],[80,3],[140,6]],
           amplitude_ticks=[[80,0],[60,.1]],frequency_unit=unit,unit="dimensionless" if kind!="phonon_dos" else "pixel",
           physical_definition_confirmed=True,amplitude_evidence="合成原图独立幅值刻度",exclude=[],zero_boundaries_thz=[None,None])
    panel=dict(panel_id="p",state_key="s1",caption="",curves=[c],projection_scale_confirmed=False,projection_complete=False)
    return rgb,panel


def test_alpha_only_has_integral_without_cumulative_or_reference():
    image,p=fixture()
    result=extract_panel(image,p)
    assert result["quality"]["integrals"]["raw"]["pixel_integral"]>0
    assert "lambda" not in result["quality"]["comparisons"]["raw"]
    assert "joint" not in result["candidates"]
    assert result["curves"][0]["point_counts"]["observed"]==121


def test_unknown_absolute_scale_does_not_block_relative_omega():
    image,p=fixture();p["curves"][0]["physical_definition_confirmed"]=False
    r=extract_panel(image,p)
    assert r["quality"]["integrals"]["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert r["quality"]["integrals"]["raw"]["lambda_integral"] is None


def test_lambda_reference_only_normalizes_source_shape_and_condition_mismatch_not_compared():
    image,p=fixture()
    before=extract_panel(image,p)
    refs={"lambda":dict(value=999.,source={"page":1,"quote":"λ=999"},same_conditions=True)}
    after=extract_panel(image,p,references=refs)
    assert after["curves"]==before["curves"]
    assert after["quality"]["integrals"]["raw"]["omega_log_k"]==before["quality"]["integrals"]["raw"]["omega_log_k"]
    assert after["quality"]["integrals"]["raw"]["normalization"]["lambda_normalized"]==pytest.approx(999.)
    assert "lambda" not in after["quality"]["comparisons"]["raw"]
    assert comparison(2,3,{"page":1},False)["status"]=="unavailable"
    assert comparison(2,0,{"page":1},True)["relative_difference_pct"] is None


def test_density_frequency_conversion_has_jacobian():
    image,p=fixture("phonon_dos","cm-1")
    p["curves"][0]["unit"]="modes_per_source_frequency"
    r=extract_panel(image,p)
    c=r["curves"][0]
    assert c["points"][0]["frequency_thz"]==pytest.approx(0.)
    assert c["points"][50]["observed_amplitude"]==pytest.approx(.025/.0299792458)
    assert c["unit"]=="modes/THz/primitive_cell"


def test_unsupported_scale_and_duplicate_ids_rejected():
    _,p=fixture();p["curves"][0]["frequency_scale"]="log"
    with pytest.raises(ValueError):PanelCalibration.model_validate(p)
    _,p=fixture();p["curves"].append(copy.deepcopy(p["curves"][0]))
    with pytest.raises(ValueError):PanelCalibration.model_validate(p)


def test_model_only_proposes_calibration_unknown_material_is_unassigned():
    image,p=fixture();p["state_key"]="foreign"
    def complete(system,prompt,**kwargs):
        assert "原图像素" in system and kwargs["images"][0].startswith("data:image/png;base64,")
        assert "人工坐标" not in prompt
        return dict(panels=[p],issues=[])
    png=io.BytesIO();Image.fromarray(image).save(png,format="PNG")
    panels,issues=calibrate(dict(size_px=[160,100],text="Eliashberg spectrum",image=png.getvalue()),
                            [{"state_key":"s1"}],complete=complete)
    assert panels[0]["state_key"] is None and not issues


def test_independent_vector_pdf_discovery_has_coordinate_transform(tmp_path):
    import pymupdf
    doc=pymupdf.open();page=doc.new_page(width=400,height=300)
    page.insert_text((20,20),"Phonon density of states",fontsize=12)
    page.draw_line((40,250),(350,250));page.draw_line((40,250),(40,60))
    page.draw_polyline([(40,230),(150,100),(350,220)],color=(0,0,1))
    path=tmp_path/"known-spectrum.pdf";doc.save(path);doc.close()
    figures=list(pdf_figures(path))
    assert figures and figures[0]["source_mode"]=="rendered"
    f=figures[0];assert f["render_dpi"]==160
    assert f["pixel_to_pdf"]["scale_x"]==pytest.approx(400/f["size_px"][0])


def setup_collection(session):
    image,p=fixture();state=dict(state_key="s1",material="H3S",pressure_value_gpa=200,property_modules=[])
    ctx=dict(target="upload",target_id="task",owner_id=1,paper=None,paper_revision=None,states=[state],
             privileged=True,can_edit=True,can_review=True,version="target-version")
    row=service.collection(session,ctx,"source","panel",dict(source_sha256="source",pdf_page=1))
    run,pending=service.new_run(session,row,p,state)
    service.complete_run(run,extract_panel(image,p));service.activate(row,run,state);session.flush()
    return ctx,row,run,p,state


def test_versioned_runs_cache_without_overwriting_old_observations(db_session):
    ctx,row,run,p,state=setup_collection(db_session)
    cached,pending=service.new_run(db_session,row,p,state)
    assert cached.id==run.id and not pending
    old=copy.deepcopy(run.result_json)
    p["curves"][0]["amplitude_ticks"][1][1]=.12
    fresh,pending=service.new_run(db_session,row,p,state)
    assert fresh.id!=run.id and pending
    service.activate(row,fresh,state)
    assert run.result_json==old and row.review_json=={}
    with pytest.raises(HTTPException):service.assert_version(row.version,row.version-1)


def test_per_curve_acceptance_and_public_frequency_mask(db_session):
    ctx,row,run,p,state=setup_collection(db_session)
    actor=SimpleNamespace(id=7)
    with pytest.raises(HTTPException):service.review_curve(db_session,{**ctx,"can_review":False},row,"a","accepted",[],"",actor)
    with pytest.raises(HTTPException):service.review_curve(db_session,ctx,row,"a","accepted_limited",[],"",actor)
    service.review_curve(db_session,ctx,row,"a","accepted_limited",[(2.,4.)],"该频段可辨认",actor)
    db_session.flush()
    public=service.listing(db_session,{**ctx,"privileged":False})["items"]
    assert public and all(2<=p["frequency_thz"]<=4 for p in public[0]["result"]["curves"][0]["points"])
    state["pressure_value_gpa"]=100
    assert service.listing(db_session,{**ctx,"privileged":False})["items"]==[]
    assert service.listing(db_session,ctx)["items"][0]["stale"]


def test_state_hash_ignores_storage_ids_but_tracks_conditions():
    a=dict(state_key="s1",material="H3S",pressure_value_gpa=200,property_modules=[dict(records=[dict(value_number=2.1)])])
    b=copy.deepcopy(a);b["property_modules"][0]["records"][0]["id"]=8
    assert state_signature(a)==state_signature(b)
    b["pressure_value_gpa"]=100
    assert state_signature(a)!=state_signature(b)


def test_reference_ambiguity_and_explicit_conditions_are_not_guessed():
    record=dict(record_key="tc1",method_code="allen_dynes",evidences=[dict(page=3,quote="lambda=2.1")],
                payload=dict(parameters=dict(lambda_ep=dict(value_number=2.1)),calculation_conditions=dict(pressure_value_gpa=100)))
    state=dict(pressure_value_gpa=200,property_modules=[dict(records=[record])])
    assert references_for(state)=={}
    record["payload"]["calculation_conditions"]={}
    assert references_for(state)["lambda"]["value"]==2.1
    other=copy.deepcopy(record);other["payload"]["parameters"]["lambda_ep"]["value_number"]=2.2
    state["property_modules"][0]["records"].append(other)
    assert references_for(state)=={}


def test_public_hides_unapproved_curves_and_candidate_arrays():
    image,p=fixture();r=extract_panel(image,p)
    second=copy.deepcopy(r["curves"][0]);second["id"]="private";second["kind"]="phonon_dos";second["projection"]="S"
    r["curves"].append(second);r["calibration"]["curves"].append({**p["curves"][0],"id":"private"})
    r["candidates"]["dos_normalization"]=dict(frequency_thz=[1.,2.],components={"S":[3.,4.]},total=[3.,4.])
    public=service.mask_public(r,{"a":dict(status="accepted",reason="valid")})
    assert [c["id"] for c in public["curves"]]==["a"]
    assert [c["id"] for c in public["calibration"]["curves"]]==["a"]
    assert "dos_normalization" not in public["candidates"]


def test_invalid_calibration_pixels_are_reported_per_curve():
    image,p=fixture();p["curves"][0]["frequency_ticks"][0][0]=-50
    result=extract_panel(image,p)
    assert result["curves"]==[] and "超出原图" in result["failures"][0]["reason"]


def test_replaced_source_invalidates_public_acceptance(db_session):
    ctx,row,run,p,state=setup_collection(db_session)
    service.review_curve(db_session,ctx,row,"a","accepted",[],"valid",SimpleNamespace(id=1))
    assert service.listing(db_session,{**ctx,"privileged":False,"files":[dict(sha256="source")]})["items"]
    assert service.listing(db_session,{**ctx,"privileged":False,"files":[dict(sha256="new-source")]})["items"]==[]


def test_confirmed_structure_candidate_provides_primitive_count():
    from ase import Atoms
    from ase.io import write
    atoms=Atoms("Si",positions=[[0,0,0]],cell=[3,3,3],pbc=True)
    out=io.BytesIO();write(out,atoms,format="cif")
    candidate=dict(confirmation="confirmed",material_state_ref="material_states[0]",
                   representations=dict(conventional=dict(cif=dict(text=out.getvalue().decode()))))
    state=dict(state_key="s1")
    draft=dict(material_states=[state],structure_candidates=[candidate])
    primitive=primitive_for(state,draft)
    assert primitive["primitive_atoms"]==1 and primitive["species_counts"]=={"Si":1}
    signature=state_signature(state)
    hashes=service.structure_dependencies(draft,0)
    assert hashes and state_signature({**state,"_spectrum_structure_hashes":hashes})!=signature


@pytest.mark.parametrize("tables", [[], ["spectrum_collections"], ["spectrum_runs"],
                                   ["spectrum_collections", "spectrum_runs"]])
def test_schema_readiness_requires_both_tables(tables):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine, tables=[models.Base.metadata.tables[name] for name in tables])
    with Session(engine) as session:
        assert service.available(session) == (len(tables) == 2)
        if len(tables) != 2:
            with pytest.raises(HTTPException) as failure:
                service.require_tables(session)
            assert failure.value.status_code == 503
            assert failure.value.detail["code"] == "spectra_migration_required"
    engine.dispose()


def test_archived_collection_is_not_listed_or_public(db_session):
    ctx, row, run, panel, state = setup_collection(db_session)
    service.review_curve(db_session, ctx, row, "a", "accepted", [], "", SimpleNamespace(id=7))
    row.panel_key = "history-" + row.id
    db_session.flush()
    assert service.listing(db_session, ctx)["items"] == []
    assert service.listing(db_session, {**ctx, "privileged": False})["items"] == []


@pytest.mark.parametrize("missing_type", [FileNotFoundError, FileNotFound])
def test_legacy_upload_without_ir_still_discovers_original_pdf(tmp_path, monkeypatch, missing_type):
    import hashlib
    import pymupdf
    from backend.spectra import jobs, vision, discovery
    from backend.ingest import upload_tasks
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((20, 20), "Phonon density of states")
    page.draw_polyline([(40, 230), (150, 100), (350, 220)], color=(0, 0, 1))
    path = tmp_path / "original.pdf"
    doc.save(path)
    doc.close()
    def missing_ir(*args):
        raise missing_type("可选历史 IR 不存在")
    seen = []
    def model(figure, states):
        seen.append(figure)
        return [], []
    monkeypatch.setattr(upload_tasks, "artifact_directory", lambda task: tmp_path)
    monkeypatch.setattr(upload_tasks, "available_published_path", missing_ir)
    monkeypatch.setattr(vision, "verify_image_capability", lambda: True)
    monkeypatch.setattr(discovery, "calibrate", model)
    result = jobs.discover(dict(target="upload", target_id="legacy", states=[], files=[dict(
        stored_path=str(path), file_id="main", size=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())]), 1, "version")
    assert seen and seen[0]["source_mode"] == "rendered"
    assert seen[0]["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["image_capability_verified"]


@pytest.mark.parametrize("legacy", [False, True])
def test_incomplete_discovery_is_needs_review_and_retryable(db_session, legacy):
    ctx, row, old, panel, state = setup_collection(db_session)
    calibration = dict(discovery_version="v1")
    run, _ = service.new_run(db_session, row, calibration, None)
    outcome = dict(collections=5, extracted_collections=0, curve_count=0,
                   issues=[dict(reason="自动标定失败：HTTP 503")], status="needs_review")
    service.complete_run(run, outcome)
    assert run.status == "needs_review" and run.error_code
    if legacy:
        run.status = "succeeded"
        run.result_json = {**outcome, "status": "completed"}
    retry, pending = service.new_run(db_session, row, calibration, None)
    assert pending and retry.id == run.id and retry.status == "queued"
    # 重试失败的发现运行不能改写此前的数值运行。
    assert old.status == "succeeded" and old.result_json["curves"]


def test_unavailable_panel_cannot_claim_success_or_hit_success_cache(db_session):
    ctx, row, old, panel, state = setup_collection(db_session)
    calibration = dict(issues=["HTTP 503"])
    run, _ = service.new_run(db_session, row, calibration, None)
    service.complete_run(run, dict(curves=[], candidates={}, quality={}, failures=["HTTP 503"]))
    assert run.status == "needs_review"
    assert service.new_run(db_session, row, calibration, None)[1]



def test_olive_spectrum_is_extracted_without_confusing_green_or_axes():
    from backend.spectra.digitize import color_mask, chromatic_mask
    samples = np.array([[[128,128,0],[55,55,3],[128,128,128],[0,128,0],[255,128,0]]], dtype=np.uint8)
    assert color_mask(samples, "olive").tolist() == [[True, True, False, False, False]]
    assert chromatic_mask(samples, "olive").tolist() == [[True, True, False, False, False]]
    image, panel = fixture()
    green = color_mask(image, "green")
    image[green] = [128,128,0]
    panel["curves"][0]["color"] = "olive"
    result = extract_panel(image, panel)
    assert result["curves"][0]["point_counts"]["observed"] == 121
    assert result["quality"]["integrals"]["raw"]["pixel_integral"] > 0


def test_split_native_figure_is_composed_and_text_only_methods_skipped(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=360)
    for index, color in enumerate(["blue", "green"]):
        image = Image.new("RGB", (180,120), color)
        content = io.BytesIO(); image.save(content, format="PNG")
        page.insert_image(pymupdf.Rect(40,50+index*120,220,170+index*120), stream=content.getvalue())
    page.insert_text((20,325), "Figure S1 | Phonon density of states and Eliashberg function")
    methods = doc.new_page(width=400, height=360)
    methods.insert_text((20,20), "Eliashberg spectral function was calculated in Methods.")
    methods.draw_line((20,100),(380,100))
    path = tmp_path / "fragmented.pdf"
    doc.save(path); doc.close()
    figures = list(pdf_figures(path))
    assert len(figures) == 1
    figure = figures[0]
    assert figure["source_mode"] == "rendered_composite"
    assert len(figure["native_fragment_boxes_pdf_pt"]) == 2
    assert figure["bbox_pdf_pt"] == pytest.approx([40,50,220,290])
    assert figure["render_dpi"] == 160
    assert figure["pixel_to_pdf"]["scale_y"] == pytest.approx(240/figure["size_px"][1])


def test_vector_spectral_caption_crops_graph_instead_of_full_text_page(tmp_path):
    import pymupdf
    doc = pymupdf.open();page = doc.new_page(width=400,height=360)
    page.insert_text((20,20), "Unrelated full page manuscript text")
    page.draw_line((40,250),(350,250));page.draw_line((40,250),(40,60))
    page.draw_polyline([(40,230),(150,100),(350,220)],color=(0,0,1))
    page.insert_text((20,290), "Fig. 1. Phonon density of states")
    path = tmp_path / "vector.pdf";doc.save(path);doc.close()
    figure = list(pdf_figures(path))[0]
    x0,y0,x1,y1 = figure["bbox_pdf_pt"]
    assert x0 <= 40 and x1 >= 350 and 20 < y0 <= 60 and 250 <= y1 < 290
    assert figure["pixel_to_pdf"]["offset_y"] == y0



def test_legacy_empty_success_is_displayed_as_pending_without_rewriting_run(db_session):
    ctx, row, run, panel, state = setup_collection(db_session)
    run.result_json = dict(curves=[], candidates={}, quality={}, failures=["HTTP 503"])
    assert run.status == "succeeded"
    assert service.listing(db_session, ctx)["items"][0]["run"]["status"] == "needs_review"
    assert run.status == "succeeded"



@pytest.mark.parametrize("empty", [None, []])
def test_empty_model_zero_evidence_stays_unknown(empty):
    image, panel = fixture()
    panel["curves"][0]["zero_boundaries_thz"] = empty
    panel["curves"][0]["zero_reference_band_thz"] = empty
    result = extract_panel(image, panel)
    calibration = result["calibration"]["curves"][0]
    assert list(calibration["zero_boundaries_thz"]) == [None, None]
    assert calibration["zero_reference_band_thz"] is None
    assert all(p["status"] == "observed" for p in result["curves"][0]["points"])


@pytest.mark.parametrize("invalid", [[0], [0, 1, 2]])
def test_malformed_nonempty_zero_evidence_is_still_rejected(invalid):
    image, panel = fixture()
    panel["curves"][0]["zero_boundaries_thz"] = invalid
    with pytest.raises(ValueError):
        extract_panel(image, panel)
