"""#164：相对面积、共同归一化与实际版本/公开边界。"""
import copy
import json
import pytest
from sqlalchemy.orm import Session
from backend import models
from backend.spectra.dos import calculate_dos
from backend.spectra.context import composition_for
from backend.spectra.contracts import FREQUENCY_FACTORS
from backend.services.spectra import mask_public
from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend.tests.test_spectra_recalculate import recalc_body


def payload():
    curves = []
    for element, amplitude in (("La", 4.), ("H", 5.)):
        curves.append(dict(id=element, projection=element, kind="phonon_dos", unit="pixel",
            physical_definition_confirmed=True, frequency_direction="x",
            axis_calibration={"frequency": {"slope": 1., "intercept": 0.},
                              "amplitude": {"slope": -1., "intercept": 20.}},
            clipped_frequencies_thz=[],
            points=[dict(id=f"{element}-{i}", frequency_thz=f, frequency_pixel=f,
                         amplitude_pixel=20-a, reconstructed_amplitude=a)
                    for i, (f, a) in enumerate(((0., 0.), (.5, 2*amplitude), (1., 0.)))]))
    return dict(curves=curves, calibration=dict(projection_complete=True, projection_scale_confirmed=True,
        curves=[dict(id=c["id"], roi=[0, 0, 1, 20], frequency_direction="x", frequency_unit="THz",
                     frequency_ticks=[[0, 0], [1, 1]]) for c in curves]),
        quality={}, candidates={})


PRIMITIVE = dict(primitive_atoms=3, species_counts={"La": 1, "H": 2}, structure_hash="test-only")


def test_pixel_area_without_n_and_wrong_ratio_not_forced():
    p = payload(); before = copy.deepcopy(p)
    result = calculate_dos(p)
    assert [c["area"] for c in result["relative"]["components"]] == [4., 5.]
    assert result["relative"]["normalization"]["status"] == "unavailable"
    assert result["absolute"]["status"] == "unavailable"
    r = calculate_dos(p, PRIMITIVE)
    norm = r["relative"]["normalization"]
    assert norm["component_mode_integrals"] == {"La": 4., "H": 5.}
    assert norm["expected_modes"] == {"La": 3, "H": 6}
    assert norm["deviations"]["La"]["absolute_difference"] == 1
    assert "absolute_difference" not in norm
    assert p == before


@pytest.mark.parametrize("scale", [.001, 1., 37., 1e6])
def test_common_pixel_scaling_cancels(scale):
    p = payload()
    for c in p["curves"]:
        for point in c["points"]:
            point["amplitude_pixel"] = 20 - point["reconstructed_amplitude"]*scale
            point["reconstructed_amplitude"] *= scale
    r = calculate_dos(p, PRIMITIVE)
    assert r["relative"]["shares"]["fractions"]["La"] == pytest.approx(4/9, rel=1e-9)
    assert r["relative"]["normalization"]["component_mode_integrals"] == pytest.approx({"La": 4, "H": 5}, rel=1e-9)
    assert r["candidate"]["curves"]["La"]["density"] == pytest.approx([0, 8, 0], rel=1e-9)


@pytest.mark.parametrize("problem", ["gap", "backtrack", "negative", "missing"])
def test_bad_curve_preserves_other_area(problem):
    p = payload(); points = p["curves"][0]["points"]
    if problem == "gap": points[1]["breakBefore"] = True
    if problem == "backtrack": points[1]["frequency_thz"] = 2.
    if problem == "negative": points[1]["amplitude_pixel"] = 30.
    if problem == "missing": points[1]["amplitude_pixel"] = None; points[1]["reconstructed_amplitude"] = None
    r = calculate_dos(p, PRIMITIVE)["relative"]
    assert r["components"][0]["status"] == "unavailable"
    assert r["components"][1]["area"] == 5
    assert r["shares"]["status"] == "unavailable"
    assert r["normalization"]["status"] == "unavailable"


@pytest.mark.parametrize("condition", ["scale", "projections", "definition", "clipped", "zero"])
def test_normalization_requires_all_evidence(condition):
    p = payload()
    if condition == "scale": p["calibration"]["projection_scale_confirmed"] = False
    if condition == "projections": p["calibration"]["projection_complete"] = False
    if condition == "definition": p["curves"][0]["physical_definition_confirmed"] = False
    if condition == "clipped": p["curves"][0]["clipped_frequencies_thz"] = [.5]
    if condition == "zero":
        for c in p["curves"]:
            for point in c["points"]:
                point.update(amplitude_pixel=20., reconstructed_amplitude=0.)
    r = calculate_dos(p, PRIMITIVE)
    assert all(c["status"] == "available" for c in r["relative"]["components"])
    assert r["relative"]["normalization"]["status"] == "unavailable"
    assert r["candidate"] is None


def test_formula_only_is_proportion_not_cell_count():
    composition = composition_for({"material": "LaH2"})
    r = calculate_dos(payload(), composition=composition)["relative"]
    assert r["shares"]["expected_fractions"] == pytest.approx({"La": 1/3, "H": 2/3})
    assert r["normalization"]["status"] == "unavailable"
    assert r["normalization"].get("primitive_atoms") is None
    assert composition_for({"material": "LaH2-x"}) is None


def test_formula_structure_conflict_blocks_normalization():
    r = calculate_dos(payload(), PRIMITIVE, composition_for({"material": "LaH3"}))
    assert r["relative"]["normalization"]["status"] == "unavailable"
    assert "不一致" in r["relative"]["normalization"]["reason"]


def test_absolute_and_relative_are_separate_and_frequency_units_equivalent():
    # 规范化输入相同；来源单位不同不得重复换算已存 THz。
    p = payload()
    for c in p["curves"]:
        c["unit"] = "modes/THz/primitive_cell"
    a = calculate_dos(p, PRIMITIVE)
    factor = FREQUENCY_FACTORS["cm-1"]
    for c in p["calibration"]["curves"]:
        c["frequency_unit"] = "cm-1"
        c["frequency_ticks"] = [[0, 0], [1, 1/factor]]
    b = calculate_dos(p, PRIMITIVE)
    assert a["absolute"]["integral"] == b["absolute"]["integral"] == 9
    assert a["candidate"]["curves"] == b["candidate"]["curves"]


def test_public_hidden_or_limited_cannot_leak_totals_or_coefficients():
    p = payload(); r = calculate_dos(p, PRIMITIVE)
    p["quality"] = {"dos_relative": r["relative"], "dos_mode_integral": r["absolute"],
                    "dos_normalization": {"scale_factor": 123}, "projection_mode_check": {"hidden": 42}}
    p["candidates"]["dos_relative_normalized"] = r["candidate"]
    for reviews in ({"La": {"status": "accepted"}}, {"La": {"status": "accepted_limited", "frequency_intervals_thz": [[0, .5]]}}):
        out = mask_public(p, reviews)
        assert "dos_relative_normalized" not in out["candidates"]
        assert "dos_normalization" not in out["quality"]
        assert "projection_mode_check" not in out["quality"]
        rel = out["quality"]["dos_relative"]
        assert rel["shares"]["status"] == rel["normalization"]["status"] == "unavailable"
        assert all(c["curve_id"] == "La" for c in rel["components"])
        assert "coefficient" not in json.dumps(rel)
        if reviews["La"]["status"] == "accepted_limited":
            assert not rel["components"]


def test_real_recalculate_persists_partial_results_and_preserves_old_run(manual_http):
    e = manual_http; p = payload()
    with Session(e["engine"]) as session:
        run = session.get(models.SpectrumRun, e["old_run"]); run.result_json = p; session.commit()
    e["draft"]["material_states"][0]["material"] = "H3S"  # 不改变绑定的材料签名。
    body = recalc_body(e); body["kind"] = "phonon_dos"
    response = e["client"].post(f"/api/rag/spectra/{e['identity']}/recalculate", json=body)
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["result"]["curves"] == p["curves"]
    relative = item["result"]["quality"]["dos_relative"]
    assert relative["components"][0]["area"] == 4
    assert relative["normalization"]["status"] == "unavailable"
    assert item["review"] == {}
    assert e["client"].post(f"/api/rag/spectra/{e['identity']}/recalculate", json=body).status_code == 409
    with Session(e["engine"]) as session:
        assert session.get(models.SpectrumRun, e["old_run"]).result_json == p


def test_actual_extraction_converts_frequency_and_density_together():
    from backend.tests.test_spectra import fixture
    from backend.spectra.engine import extract_panel
    image, cal = fixture("phonon_dos")
    c = cal["curves"][0]
    c.update(unit="modes_per_source_frequency")
    cal.update(projection_complete=True, projection_scale_confirmed=True)
    primitive = dict(primitive_atoms=1, species_counts={"H": 1})
    thz = extract_panel(image, cal, primitive=primitive)
    # 同一张图仅改变来源单位的表达，密度与频率需互为倒数转换。
    factor = FREQUENCY_FACTORS["cm-1"]
    c["frequency_unit"] = "cm-1"
    c["frequency_ticks"] = [[p, v/factor] for p, v in c["frequency_ticks"]]
    c["amplitude_ticks"] = [[p, v*factor] for p, v in c["amplitude_ticks"]]
    wave = extract_panel(image, cal, primitive=primitive)
    for result in (thz, wave):
        assert result["quality"]["dos_relative"]["normalization"]["status"] == "available"
    assert thz["quality"]["dos_relative"]["components"][0]["area"] == pytest.approx(
        wave["quality"]["dos_relative"]["components"][0]["area"], rel=1e-9)
    assert thz["quality"]["dos_mode_integral"]["integral"] == pytest.approx(
        wave["quality"]["dos_mode_integral"]["integral"], rel=1e-9)
    assert thz["candidates"]["dos_relative_normalized"]["curves"]["a"]["density"] == pytest.approx(
        wave["candidates"]["dos_relative_normalized"]["curves"]["a"]["density"], rel=1e-9)


@pytest.mark.parametrize("case", ["duplicate", "total", "failed_extraction", "element_mismatch"])
def test_ambiguous_or_incomplete_projection_cannot_normalize(case):
    p = payload()
    if case == "duplicate": p["curves"][1]["projection"] = "La"
    if case == "total": p["curves"][1]["projection"] = "total"
    if case == "failed_extraction": p["calibration"]["curves"].append(dict(id="missing",kind="phonon_dos"))
    if case == "element_mismatch": p["curves"][1]["projection"] = "Sc"
    result = calculate_dos(p, PRIMITIVE)
    assert result["relative"]["normalization"]["status"] == "unavailable"
    assert result["candidate"] is None


def test_normalization_saved_then_invalidated_by_real_manual_route(manual_http):
    import io
    from ase import Atoms
    from ase.io import write
    from backend.services import spectra as service
    e = manual_http
    buffer = io.BytesIO()
    write(buffer, Atoms("LaH2", scaled_positions=[[.1,.2,.3],[.32,.47,.19],[.76,.63,.87]],
                        cell=[4,5,6], pbc=True), format="cif")
    state = e["draft"]["material_states"][0]
    state.update(material="LaH2", structure=dict(structure_format="cif",structure_text=buffer.getvalue().decode()))
    p = payload()
    for c in p["curves"]:
        c.update(roi=[0,0,1,20], color="green")
    p["calibration"].update(panel_id="p",state_key="s1")
    with Session(e["engine"]) as session:
        run = session.get(models.SpectrumRun, e["old_run"])
        run.result_json = p
        ctx = service.context(session,**e["query"],user=e["actor"][0],write=True)
        e["body"]["expected_version"] = ctx["version"]
        service.activate(session.get(models.SpectrumCollection,e["identity"]),run,ctx["states"][0])
        session.commit()
    body = recalc_body(e); body["kind"] = "phonon_dos"
    url = f"/api/rag/spectra/{e['identity']}"
    response = e["client"].post(url+"/recalculate",json=body)
    assert response.status_code == 200,response.text
    current = response.json()["items"][0]
    assert current["result"]["quality"]["dos_relative"]["normalization"]["status"] == "available"
    params = {**e["query"],"kind":"phonon_dos","collection_version":current["version"],"run_id":current["run"]["id"]}
    response = e["client"].get(url+"/manual",params=params)
    assert response.status_code == 200,response.text
    document = response.json()["documents"][0]
    document["zero"] = {"pixel":0,"pointIds":[document["curves"][0]["points"][0]["id"]]}
    document["curves"][0]["points"][1]["y"] += .1
    saved = e["client"].post(url+"/manual",json={**e["body"],"expected_collection_version":current["version"],
        "base_run_id":current["run"]["id"],"document":document})
    assert saved.status_code == 200,saved.text
    result = saved.json()["items"][0]["result"]
    assert "dos_relative" not in result["quality"]
    assert "dos_relative_normalized" not in result["candidates"]
    with Session(e["engine"]) as session:
        assert session.get(models.SpectrumRun,current["run"]["id"]).result_json["candidates"]["dos_relative_normalized"]


def test_csv_uses_current_per_curve_normalization_and_keeps_original_values():
    import csv
    import io
    from backend.api.spectra import csv_export
    p = payload(); r = calculate_dos(p, PRIMITIVE)
    p["candidates"]["dos_relative_normalized"] = r["candidate"]
    item = dict(id="isolated", state_key="s", run=dict(id="r",algorithm_version="test"), review={},
                source=dict(pdf_page=1,source_sha256="test"),result=p)
    rows = list(csv.DictReader(io.StringIO(csv_export(item))))
    assert rows[1]["reconstructed_amplitude"] == "8.0"
    assert rows[1]["normalized_dos_candidate"] == "8.0"
    assert rows[1]["normalized_dos_unit"] == "modes/THz/primitive_cell"
    assert len(rows) == 6


def test_element_ratio_uses_formula_without_n_or_full_range_confirmation():
    p = payload()
    r = calculate_dos(p, composition=composition_for({"material": "LaH2"}))["relative"]
    ratio = r["shares"]["element_ratio"]
    assert ratio["elements"] == ["La", "H"]
    assert ratio["estimated_ratio"] == pytest.approx([1, 1.25])
    assert ratio["expected_ratio"] == [1, 2]
    assert ratio["formula"] == "LaH2"
    assert ratio["max_share_difference_pp"] == pytest.approx(100/9)
    assert "coverage_note" not in r["shares"]
    assert "缺少可信原胞原子数" in r["normalization"]["reason"]


def test_element_ratio_scaling_does_not_change_comparison():
    original = calculate_dos(payload(), composition=composition_for({"material": "LaH2"}))["relative"]["shares"]["element_ratio"]
    p = payload()
    for c in p["curves"]:
        for point in c["points"]:
            point["amplitude_pixel"] = 20-7*point["reconstructed_amplitude"]
            point["reconstructed_amplitude"] *= 7
    result = calculate_dos(p, composition=composition_for({"material": "LaH2"}))["relative"]["shares"]["element_ratio"]
    assert result == original


def test_element_ratio_prefers_current_formula_when_structure_disagrees():
    r = calculate_dos(payload(), PRIMITIVE, composition_for({"material": "LaH3"}))["relative"]
    assert r["shares"]["element_ratio"]["expected_ratio"] == [1, 3]
    assert r["shares"]["expected_fractions"] == {"La": .25, "H": .75}
    assert r["normalization"]["status"] == "unavailable"


def test_zero_area_is_not_rounded_into_a_positive_atom_count():
    p = payload()
    for point in p["curves"][0]["points"]:
        point.update(amplitude_pixel=20, reconstructed_amplitude=0)
    ratio = calculate_dos(p, composition=composition_for({"material": "LaH2"}))["relative"]["shares"]["element_ratio"]
    assert ratio["elements"] == ["H", "La"]
    assert ratio["estimated_ratio"] == [1, 0]
    assert ratio["expected_ratio"] == [1, .5]


def test_element_mismatch_does_not_generate_an_approximate_formula():
    p = payload();p["curves"][1]["projection"] = "Sc"
    r = calculate_dos(p, composition=composition_for({"material": "LaH2"}))["relative"]
    assert r["shares"]["status"] == "available"
    assert r["shares"]["element_ratio"]["status"] == "unavailable"


@pytest.mark.parametrize("marker", [None, False, True])
@pytest.mark.parametrize("upper", [None, .1, 100.])
def test_frequency_metadata_cannot_block_current_samples(marker, upper):
    p = payload()
    for c in p["calibration"]["curves"]:
        if marker is not None:
            c["frequency_range_confirmed"] = marker
        c["zero_boundaries_thz"] = [None, upper]
    # 末点未到来源图框/刻度上限，同样只使用保存的实际样本积分。
    p["curves"][0]["points"][-1]["frequency_thz"] = .9
    before = copy.deepcopy(p)
    result = calculate_dos(p, PRIMITIVE)
    relative = result["relative"]
    assert relative["method"] == "dos-relative-v5"
    assert relative["normalization"]["status"] == "available"
    assert relative["normalization"]["total_mode_integral"] == pytest.approx(9)
    assert relative["components"][0]["frequency_interval_thz"] == [0., .9]
    assert "coverage_note" not in relative["shares"]
    assert p == before


def test_retired_confirmation_is_ignored_without_loosening_other_schema_checks():
    from backend.spectra.contracts import PanelCalibration
    from backend.tests.test_spectra import fixture
    from pydantic import ValidationError
    _, cal = fixture("phonon_dos")
    cal["curves"][0]["frequency_range_confirmed"] = False
    before = copy.deepcopy(cal)
    parsed = PanelCalibration.model_validate(cal).model_dump()
    assert "frequency_range_confirmed" not in parsed["curves"][0]
    assert cal == before
    cal["curves"][0]["unexpected_key"] = True
    with pytest.raises(ValidationError):
        PanelCalibration.model_validate(cal)


# TDOS 与元素分波必须分别决定计算条件，不能因只有一条线就猜总谱。
def total_payload(projection="total"):
    p = payload()
    p["curves"] = p["curves"][:1]
    p["curves"][0]["projection"] = projection
    p["calibration"]["curves"] = p["calibration"]["curves"][:1]
    p["calibration"].update(projection_complete=False, projection_scale_confirmed=False)
    return p


@pytest.mark.parametrize("projection", ["total", "TDOS", " Total "])
@pytest.mark.parametrize("complete,scale", [(False, False), (False, True), (True, False), (True, True)])
def test_confirmed_tdos_normalizes_independently_of_element_flags(projection, complete, scale):
    p = total_payload(projection)
    p["calibration"].update(projection_complete=complete, projection_scale_confirmed=scale)
    before = copy.deepcopy(p)
    primitive = dict(primitive_atoms=7, species_counts={"Ca": 1, "H": 6})
    r = calculate_dos(p, primitive)
    rel = r["relative"]
    assert rel["normalization"]["status"] == "available"
    assert rel["spectrum_type"] == "total"
    assert rel["components"][0]["frequency_interval_thz"] == [0., 1.]
    assert rel["components"][0]["area"] == 4
    assert rel["normalization"]["status"] == "available"
    assert rel["normalization"]["coefficient"] == pytest.approx(5.25)
    assert rel["normalization"]["total_mode_integral"] == pytest.approx(21)
    assert rel["normalization"]["expected_modes"] == rel["normalization"]["deviations"] == {}
    assert rel["shares"]["status"] == "unavailable"
    assert not any(k in rel["shares"] for k in ("fractions", "expected_fractions", "element_ratio"))
    assert r["absolute"]["status"] == "unavailable"
    assert "独立绝对密度刻度" in r["absolute"]["reason"]
    assert p == before


@pytest.mark.parametrize("problem", ["n", "definition", "clipped", "gap", "backtrack", "negative", "zero", "hidden", "counts", "formula"])
def test_tdos_keeps_independent_safety_checks(problem):
    p = total_payload()
    primitive = copy.deepcopy(PRIMITIVE)
    composition = None
    c = p["curves"][0]
    if problem == "n": primitive = None
    if problem == "definition": c["physical_definition_confirmed"] = False
    if problem == "clipped": c["clipped_frequencies_thz"] = [.5]
    if problem == "gap": c["points"][1]["breakBefore"] = True
    if problem == "backtrack": c["points"][1]["frequency_thz"] = 2
    if problem == "negative": c["points"][1]["amplitude_pixel"] = 30
    if problem == "zero":
        for point in c["points"]: point.update(amplitude_pixel=20, reconstructed_amplitude=0)
    if problem == "hidden": p["calibration"]["curves"].append(dict(id="missing", kind="phonon_dos"))
    if problem == "counts": primitive["species_counts"]["H"] = 3
    if problem == "formula": composition = composition_for({"material": "LaH3"})
    r = calculate_dos(p, primitive, composition)
    assert r["relative"]["normalization"]["status"] == "unavailable"
    assert r["candidate"] is None


@pytest.mark.parametrize("projection", [None, "La"])
def test_single_unknown_or_element_curve_is_not_inferred_to_be_tdos(projection):
    p = total_payload(projection)
    # ID 中出现 total 也不是总谱的物理依据。
    p["curves"][0]["id"] = "source_total_phonon_dos"
    p["calibration"]["curves"][0]["id"] = "source_total_phonon_dos"
    r = calculate_dos(p, PRIMITIVE)
    assert r["relative"]["spectrum_type"] == "projected"
    assert r["relative"]["normalization"]["status"] == "unavailable"
    assert "元素投影完整性" in r["relative"]["normalization"]["reason"]


@pytest.mark.parametrize("projection", ["total", "TDOS"])
def test_total_and_projected_curves_cannot_be_added(projection):
    p = payload()
    p["curves"][0]["projection"] = projection
    r = calculate_dos(p, PRIMITIVE)
    assert r["candidate"] is None
    assert "不能相加" in r["relative"]["normalization"]["reason"]


def test_tdos_absolute_integral_stays_independent_and_requires_absolute_units():
    p = total_payload()
    p["curves"][0]["unit"] = "modes/THz/primitive_cell"
    r = calculate_dos(p, PRIMITIVE)
    assert r["relative"]["normalization"]["total_mode_integral"] == pytest.approx(9)
    assert r["absolute"]["integral"] == pytest.approx(4)
    assert r["absolute"]["absolute_difference"] == pytest.approx(5)
    p["curves"][0]["physical_definition_confirmed"] = False
    assert calculate_dos(p, PRIMITIVE)["absolute"]["status"] == "unavailable"



@pytest.mark.parametrize("calibrated", [False, True])
def test_tdos_real_recalculate_persists_rereads_exports_and_preserves_history(manual_http, calibrated):
    import csv
    import io
    from ase import Atoms
    from ase.io import write
    from backend.services import spectra as service
    e = manual_http
    buffer = io.BytesIO()
    write(buffer, Atoms("H", scaled_positions=[[.1,.2,.3]], cell=[4,5,6], pbc=True), format="cif")
    state = e["draft"]["material_states"][0]
    state.update(material="H", structure=dict(structure_format="cif",structure_text=buffer.getvalue().decode()))
    p = calibrated_payload() if calibrated else total_payload()
    p["curves"][0].update(roi=[0,0,1,20], color="green")
    p["calibration"].update(panel_id="p",state_key="s1")
    with Session(e["engine"]) as session:
        run = session.get(models.SpectrumRun, e["old_run"])
        run.result_json = p
        ctx = service.context(session,**e["query"],user=e["actor"][0],write=True)
        e["body"]["expected_version"] = ctx["version"]
        service.activate(session.get(models.SpectrumCollection,e["identity"]),run,ctx["states"][0])
        session.commit()
    body = recalc_body(e); body["kind"] = "phonon_dos"
    url = f"/api/rag/spectra/{e['identity']}"
    response = e["client"].post(url+"/recalculate",json=body)
    assert response.status_code == 200,response.text
    current = response.json()["items"][0]
    norm = current["result"]["quality"]["dos_relative"]["normalization"]
    assert norm["status"] == "available"
    assert norm["total_mode_integral"] == pytest.approx(3)
    assert current["result"]["curves"] == p["curves"]
    assert current["run"]["id"] != e["old_run"]
    assert current["review"] == {}
    reread = e["client"].get("/api/rag/spectra",params=e["query"])
    assert reread.status_code == 200,reread.text
    assert reread.json()["items"][0]["result"] == current["result"]
    exported = e["client"].get(url+"/export",params={**e["query"],"format":"csv"})
    assert exported.status_code == 200,exported.text
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert float(rows[1]["normalized_dos_candidate"]) == pytest.approx(6)
    assert float(rows[1]["reconstructed_amplitude"]) == pytest.approx(8)
    assert float(rows[1]["dos_integral"]) == pytest.approx(.4 if calibrated else 4)
    assert rows[1]["dos_integral_unit"] == ("arbitrary_units·THz" if calibrated else "pixel·THz")
    assert rows[1]["dos_amplitude_basis"] == ("calibrated_values" if calibrated else "source_pixels")
    with Session(e["engine"]) as session:
        assert session.get(models.SpectrumRun,e["old_run"]).result_json == p
        assert session.get(models.SpectrumRun,current["run"]["id"]).result_json == current["result"]
    public = mask_public(current["result"],{"La":{"status":"accepted_limited","frequency_intervals_thz":[[0,.5]]}})
    assert "dos_relative_normalized" not in public["candidates"]



def test_real_source_identity_replay_and_saved_manual_trace_are_distinct():
    from pathlib import Path
    from PIL import Image
    import io
    import numpy as np
    from backend.spectra.discovery import calibrate
    from backend.spectra.engine import extract_panel
    evidence = Path(__file__).resolve().parents[2]/"docs/specs/164-dos-relative-normalization/validation/tdos"
    report = json.loads((evidence/"source-report.json").read_text())
    response = json.loads((evidence/"fresh-model-response.json").read_text())
    bundle = json.loads((evidence/"source-fixture.json").read_text())
    image = (evidence/"source.png").read_bytes()
    import hashlib
    assert hashlib.sha256(image).hexdigest() == report["source_image_sha256"]
    states = [dict(state_key=p["state_key"]) for p in report["panels"]]
    panels, _ = calibrate(dict(image=image,size_px=list(Image.open(io.BytesIO(image)).size),text=report["context"]),
                          states,complete=lambda *args,**kwargs: copy.deepcopy(response))
    assert panels
    for panel in panels:
        assert panel["curves"][0]["projection"] == "total"
        assert panel["curves"][0]["physical_definition_confirmed"]
        panel.update(projection_complete=False,projection_scale_confirmed=False)
        result = extract_panel(np.asarray(Image.open(io.BytesIO(image)).convert("RGB")),panel,primitive=report["primitive"])
        rel = result["quality"]["dos_relative"]
        assert rel["spectrum_type"] == "total"
        # 真实提取失败原因不能被元素完整性或尺度门槛取代。
        assert "元素投影完整性" not in rel["normalization"].get("reason","")
        assert "共同幅值尺度" not in rel["normalization"].get("reason","")
    saved = copy.deepcopy(bundle["result"])
    normalized = calculate_dos(saved,report["primitive"])["relative"]
    assert normalized["normalization"]["total_mode_integral"] == pytest.approx(21)
    assert normalized["normalization"]["coefficient"] == pytest.approx(3.32876370919475)
    assert normalized["components"][0]["frequency_interval_thz"] == pytest.approx([3.6556,58.648],rel=1e-4)
    assert saved == bundle["result"]



def calibrated_payload():
    p = total_payload()
    p["curves"][0]["unit"] = "arbitrary_units"
    p["curves"][0]["axis_calibration"]["amplitude"] = dict(slope=-.1,intercept=2.)
    # 重算必须用当前标定；旧数值故意与新标定不一致。
    return p


def test_calibrated_arbitrary_units_precede_pixels_without_n_or_identity():
    p = calibrated_payload();p["curves"][0].update(projection=None,physical_definition_confirmed=False)
    before = copy.deepcopy(p)
    r = calculate_dos(p)["relative"]
    c = r["components"][0]
    assert c["area"] == pytest.approx(.4)
    assert c["unit"] == "arbitrary_units·THz"
    assert c["amplitude_basis"]["kind"] == "calibrated_values"
    assert r["normalization"]["status"] == "unavailable"
    assert p == before


def test_current_manual_calibration_overrides_stored_axis_for_integral():
    p = calibrated_payload()
    p["manual_documents"]={"La":{"calibration":{"amplitude":{
        "pixels":[20,10],"values":[0,2],"unit":"arbitrary_units"}}}}
    c = calculate_dos(p)["relative"]["components"][0]
    assert c["area"] == pytest.approx(.8)
    assert c["amplitude_basis"]["source"] == "manual_calibration"


def test_calibrated_and_pixel_normalization_are_equivalent_with_distinct_coefficients():
    p = calibrated_payload();cal = calculate_dos(p,PRIMITIVE)
    p["curves"][0]["unit"]="pixel";pix=calculate_dos(p,PRIMITIVE)
    assert cal["relative"]["normalization"]["coefficient"] == pytest.approx(22.5)
    assert pix["relative"]["normalization"]["coefficient"] == pytest.approx(2.25)
    assert cal["candidate"]["curves"]["La"]["density"] == pytest.approx(pix["candidate"]["curves"]["La"]["density"],rel=1e-9)


def test_incompatible_amplitude_units_keep_independent_areas_only():
    p = payload();p["curves"][0]["unit"]="arbitrary_units"
    r = calculate_dos(p,PRIMITIVE)["relative"]
    assert all(c["status"]=="available" for c in r["components"])
    assert r["shares"]["status"] == r["normalization"]["status"] == "unavailable"
    assert "幅值单位" in r["normalization"]["reason"]


def test_real_saved_calibration_integral_is_not_relabelled_pixel_area():
    from pathlib import Path
    evidence=Path(__file__).resolve().parents[2]/"docs/specs/164-dos-relative-normalization/validation/tdos"
    p=json.loads((evidence/"source-fixture.json").read_text())["result"]
    before=copy.deepcopy(p)
    r=calculate_dos(p,dict(primitive_atoms=7,species_counts={"Ca":1,"H":6}))
    assert r["relative"]["components"][0]["area"] == pytest.approx(6.308648445665745,rel=1e-9)
    assert r["relative"]["components"][0]["unit"] == "arbitrary_units·THz"
    assert r["relative"]["normalization"]["coefficient"] == pytest.approx(3.32876370919475,rel=1e-9)
    assert r["relative"]["normalization"]["total_mode_integral"] == pytest.approx(21)
    assert p==before



def test_no_numeric_axis_keeps_stored_pixel_integral_available():
    p=total_payload()
    p["curves"][0].pop("axis_calibration")
    r=calculate_dos(p)["relative"]
    assert r["components"][0]["area"] == pytest.approx(4)
    assert r["components"][0]["unit"] == "pixel·THz"
    assert r["components"][0]["amplitude_basis"]["kind"] == "stored_pixels"
    assert r["normalization"]["status"] == "unavailable"
