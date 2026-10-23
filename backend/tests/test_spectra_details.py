"""#154/#155 正式零频像素采样、原始 DOS 核验与历史权限。"""
import copy
import numpy as np
import pytest
from fastapi import HTTPException
from backend.tests.test_spectra import fixture, db_session, setup_collection
from backend.spectra.engine import extract_panel, dos_mode_integral
from backend.spectra.contracts import panel_identity
from backend.services import spectra as service


@pytest.mark.parametrize("direction", ["x", "y"])
def test_zero_tick_extends_roi_and_reads_real_colored_pixel(direction):
    image, panel = fixture()
    panel["curves"][0]["roi"][0] = 21  # 原框漏掉零频像素，刻度与原图仍有证据。
    if direction == "y":
        image = image.transpose(1, 0, 2)
        panel["curves"][0].update(frequency_direction="y", roi=[10, 21, 80, 140])
    before = copy.deepcopy(panel)
    result = extract_panel(image, panel)
    first = result["curves"][0]["points"][0]
    assert first["frequency_thz"] == 0
    assert first["frequency_pixel"] == 20
    assert first["observed_amplitude"] == 0
    assert first["status"] == "observed"
    assert panel == before
    assert result["quality"]["integrals"]["raw"]["minimum_integrated_thz"] == 0


def test_zero_without_colored_pixel_is_missing_not_fabricated():
    image, panel = fixture()
    image[:,20] = 255
    curve = extract_panel(image, panel)["curves"][0]
    assert curve["points"][0]["frequency_thz"] == 0
    assert curve["points"][0]["status"] == "missing"
    assert curve["points"][0]["reconstructed_amplitude"] is None
    result = extract_panel(image, panel)
    assert result["quality"]["integrals"]["raw"]["status"] == "unavailable"


def test_subpixel_zero_samples_image_not_old_first_frequency():
    image, panel = fixture()
    curve = panel["curves"][0]
    curve["frequency_ticks"] = [[20.5, 0], [80.5, 3], [140.5, 6]]
    result = extract_panel(image, panel)
    first = result["curves"][0]["points"][0]
    assert first["frequency_pixel"] == 20.5 and first["frequency_thz"] == 0
    assert first["detection_mode"] == "subpixel_color"
    assert first["observed_amplitude"] == 0


@pytest.mark.parametrize("ticks", [[[20,1],[80,4],[140,7]], [[-1,0],[80,4],[140,7]]])
def test_no_real_zero_evidence_or_out_of_image_does_not_create_curve(ticks):
    image, panel = fixture(); panel["curves"][0]["frequency_ticks"] = ticks
    result = extract_panel(image, panel)
    assert not result["curves"] and result["failures"]


def test_alpha_independent_amplitude_evidence_required():
    image, panel = fixture(); panel["curves"][0].pop("amplitude_evidence")
    assert extract_panel(image, panel)["quality"]["integrals"]["raw"]["status"] == "unavailable"


def test_panel_identity_ignores_model_labels_and_roi_but_keeps_material():
    _, panel = fixture(); changed = copy.deepcopy(panel)
    changed["panel_id"] = "renamed-by-model"
    changed["curves"][0]["roi"][0] += 1
    changed["curves"][0]["frequency_ticks"][-1][-1] = 8
    assert panel_identity(panel) == panel_identity(changed)
    changed["state_key"] = "other-pressure"
    assert panel_identity(panel) != panel_identity(changed)


def test_raw_dos_integral_is_not_forced_to_3n_and_missing_is_unavailable():
    curves = [dict(id="H", projection="H", unit="modes/THz/primitive_cell",
                   points=[dict(frequency_thz=f,reconstructed_amplitude=a) for f,a in [(0,0),(1,2),(2,0)]])]
    result = dos_mode_integral(curves, {"primitive_atoms":1}, True, True)
    assert result["integral"] == 2 and result["target_modes"] == 3
    assert result["absolute_difference"] == 1
    assert result["relative_difference_pct"] == pytest.approx(100/3)
    assert "satisfied" not in result
    relative = copy.deepcopy(curves); relative[0]["unit"] = "pixel"
    assert dos_mode_integral(relative, {"primitive_atoms":1}, True, True)["status"] == "unavailable"
    curves[0]["points"][0]["reconstructed_amplitude"] = None
    assert dos_mode_integral(curves, {"primitive_atoms":1}, True, True)["status"] == "unavailable"


def test_history_is_scoped_private_and_keeps_old_observations(db_session):
    ctx,row,old,cal,state = setup_collection(db_session)
    old_points = copy.deepcopy(old.result_json["curves"])
    cal["curves"][0]["amplitude_ticks"][1][1] = .12
    new,_ = service.new_run(db_session,row,cal,state)
    image,_ = fixture(); service.complete_run(new,extract_panel(image,cal)); service.activate(row,new,state)
    db_session.flush()
    history = service.history(db_session,ctx,row.id)
    assert {run["id"] for run in history} == {old.id,new.id}
    data = service.listing(db_session,ctx,run_override=(row.id,old.id))["items"][0]
    assert data["historical"] and data["stale"] and not data["review"]
    assert data["result"]["curves"] == old_points
    with pytest.raises(HTTPException) as e:
        service.history(db_session,{**ctx,"privileged":False},row.id)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        service.history(db_session,{**ctx,"target_id":"unrelated"},row.id)
    assert old.result_json["curves"] == old_points


def test_same_input_does_not_overwrite_incomplete_numeric_history(db_session):
    ctx,row,run,cal,state = setup_collection(db_session)
    run.result_json = {**run.result_json, "status":"needs_review", "failures":[{"reason":"部分曲线未完成"}]}
    run.status = "needs_review"
    before = copy.deepcopy(run.result_json)
    db_session.flush()
    cached,pending = service.new_run(db_session,row,cal,state)
    assert cached.id == run.id and not pending
    assert cached.result_json == before


def test_partial_public_dos_hides_whole_integral():
    image,cal = fixture("phonon_dos")
    result = extract_panel(image,cal)
    second = copy.deepcopy(result["curves"][0]); second["id"] = "hidden"
    result["curves"].append(second)
    result["quality"]["dos_mode_integral"] = dict(status="available",integral=81)
    public = service.mask_public(result,{"a":{"status":"accepted"}})
    assert public["quality"]["dos_mode_integral"]["status"] == "unavailable"
    assert "integral" not in public["quality"]["dos_mode_integral"]


def test_history_http_permissions_old_export_and_cross_collection(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "spectra-isolated-http-test-only")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from types import SimpleNamespace
    from backend import models
    from backend.api.spectra import router
    from backend.database import get_db
    from backend.security import get_current_user_optional
    from backend.ingest import upload_tasks
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine, tables=[models.SpectrumCollection.__table__,models.SpectrumRun.__table__])
    with Session(engine) as session:
        ctx,row,old,cal,state = setup_collection(session)
        cal["curves"][0]["amplitude_ticks"][1][1] = .12
        new,_ = service.new_run(session,row,cal,state)
        image,_ = fixture(); service.complete_run(new,extract_panel(image,cal)); service.activate(row,new,state)
        session.commit()
        monkeypatch.setattr(upload_tasks,"get_state",lambda target: {"user_id":1,"status":"completed","files":[]} if target=="task" else None)
        monkeypatch.setattr(upload_tasks,"get_draft",lambda target: {"material_states":[state]})
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_user_optional] = lambda: SimpleNamespace(id=1,role="user",is_approved=True)
        with TestClient(app) as client:
            query = "?target=upload&target_id=task"
            response = client.get(f"/api/rag/spectra/{row.id}/history"+query)
            assert response.status_code == 200 and len(response.json()["items"]) == 2
            response = client.get(f"/api/rag/spectra/{row.id}/runs/{old.id}"+query)
            assert response.status_code == 200 and response.json()["historical"]
            response = client.get(f"/api/rag/spectra/{row.id}/export"+query+f"&format=csv&run_id={old.id}")
            assert response.status_code == 200 and old.id in response.text
            assert client.get(f"/api/rag/spectra/{row.id}/runs/nonexistent"+query).status_code == 404
            assert client.get(f"/api/rag/spectra/{row.id}/history?target=upload&target_id=other").status_code == 404
            app.dependency_overrides[get_current_user_optional] = lambda: None
            assert client.get(f"/api/rag/spectra/{row.id}/history"+query).status_code == 403
            assert client.get(f"/api/rag/spectra/{row.id}/runs/{old.id}"+query).status_code == 403
    engine.dispose()
