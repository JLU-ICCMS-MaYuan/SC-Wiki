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
                     frequency_ticks=[[0, 0], [1, 1]], frequency_range_confirmed=True) for c in curves]),
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


@pytest.mark.parametrize("condition", ["scale", "projections", "definition", "range", "clipped", "shortened", "zero"])
def test_normalization_requires_all_evidence(condition):
    p = payload()
    if condition == "scale": p["calibration"]["projection_scale_confirmed"] = False
    if condition == "projections": p["calibration"]["projection_complete"] = False
    if condition == "definition": p["curves"][0]["physical_definition_confirmed"] = False
    if condition == "range": p["calibration"]["curves"][0]["frequency_range_confirmed"] = False
    if condition == "clipped": p["curves"][0]["clipped_frequencies_thz"] = [.5]
    if condition == "shortened": p["curves"][0]["points"][-1]["frequency_thz"] = .9
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
    c.update(unit="modes_per_source_frequency", frequency_range_confirmed=True)
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
