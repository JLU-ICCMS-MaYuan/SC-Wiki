"""#163 相对积分、论文λ归一化与无文字门槛的真实接口验收。"""
import copy
import math
import pytest
from sqlalchemy.orm import Session
from backend import models
from backend.spectra.relative import calculate_alpha
from backend.spectra.digitize import spectral_integrals
from backend.spectra.context import reference_choices
from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend.tests.test_spectra import fixture
from backend.spectra.engine import extract_panel


def reference(value):
    return dict(value=value,source=dict(quote="合成同条件参考",page_start=1,source_name="fixture.pdf"),same_conditions=True)


def spectrum():
    values=[0.,3.,6.]
    points=[dict(id=f"p{i}",frequency_thz=f,frequency_pixel=80-10*f,amplitude_pixel=20+10*f,
                 reconstructed_amplitude=.03125*10*f,segment="s",breakBefore=i==0) for i,f in enumerate(values)]
    curve=dict(id="a",kind="alpha2f",unit="unknown",physical_definition_confirmed=False,frequency_direction="y",
               axis_calibration={"frequency":{"slope":-.1,"intercept":8.},"amplitude":{"slope":.03125,"intercept":-.625}},
               roi=[10,20,90,80],points=points)
    doc=dict(source={"plot":[10,20,90,80]},calibration={
        "direction":"y","frequency":{"pixels":[80,20],"values":[0,6],"unit":"THz"},
        "amplitude":{"pixels":[20,84],"values":[0,2],"unit":"unknown"}},
        curves=[dict(id="a",name="α²F",points=[dict(id=p["id"],x=p["amplitude_pixel"],y=p["frequency_pixel"]) for p in points])],
        zero={"pixel":80,"pointIds":["p0"]},operations=[])
    return dict(curves=[curve],manual_documents={"a":doc},calibration={})


def test_no_text_no_absolute_scale_no_lambda_still_has_omega():
    data=spectrum();original=copy.deepcopy(data)
    result=calculate_alpha(data)
    assert result["raw"]["omega_log_k"]==pytest.approx(6/math.e*47.99243073366221)
    assert result["raw"]["pixel_integral"]==pytest.approx(120.)
    assert result["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert result["raw"]["normalization"]["status"]=="unavailable"
    assert result["candidate"] is None and data==original


def test_pixel_amplitude_double_leaves_omega_and_normalized_curve_unchanged():
    data=spectrum();refs={"lambda":reference(2.)}
    first=calculate_alpha(data,refs)
    doc=data["manual_documents"]["a"]
    for p in data["curves"][0]["points"]:p["amplitude_pixel"]*=2
    for p in doc["curves"][0]["points"]:p["x"]*=2
    doc["calibration"]["amplitude"]["pixels"]=[40,168]
    data["curves"][0]["axis_calibration"]["amplitude"]={"slope":.015625,"intercept":-.625}
    second=calculate_alpha(data,refs)
    assert second["raw"]["pixel_integral"]==pytest.approx(2*first["raw"]["pixel_integral"])
    assert second["raw"]["omega_log_k"]==pytest.approx(first["raw"]["omega_log_k"],rel=1e-10)
    assert second["raw"]["normalization"]["coefficient"]==pytest.approx(first["raw"]["normalization"]["coefficient"]/2,rel=1e-10)
    assert second["candidate"]["alpha2f"]==pytest.approx(first["candidate"]["alpha2f"],rel=1e-10)
    assert spectral_integrals(second["candidate"]["frequency_thz"],second["candidate"]["alpha2f"])["lambda_integral"]==pytest.approx(2.,rel=1e-10,abs=1e-12)


@pytest.mark.parametrize("lambda_value",[0.,2.,4.])
def test_lambda_only_sets_normalization_does_not_change_omega(lambda_value):
    result=calculate_alpha(spectrum(),{"lambda":reference(lambda_value),"omega_log":reference(1.)})
    raw=result["raw"];norm=raw["normalization"]
    assert norm["status"]=="available" and norm["coefficient"]==pytest.approx(lambda_value/120)
    assert norm["lambda_normalized"]==pytest.approx(lambda_value,rel=1e-10,abs=1e-12)
    assert raw["omega_log_k"]==pytest.approx(6/math.e*47.99243073366221)
    assert result["comparison"]["relative_difference_pct"]>100
    assert result["candidate"]["label"]=="依据论文 λ 归一化"


@pytest.mark.parametrize("refs",[{},{"lambda":reference(2)},{"omega_log":reference(100)}])
def test_missing_one_reference_does_not_hide_other_results(refs):
    result=calculate_alpha(spectrum(),refs)
    assert result["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert (result["raw"]["normalization"]["status"]=="available")==("lambda" in refs)
    assert (result["comparison"]["status"]=="available")==("omega_log" in refs)


@pytest.mark.parametrize("value",[-1.,float("nan"),float("inf")])
def test_invalid_lambda_does_not_cancel_omega(value):
    result=calculate_alpha(spectrum(),{"lambda":reference(value)})
    assert result["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert result["raw"]["normalization"]["status"]=="unavailable"


def test_zero_pixel_integral_and_zero_reference_have_separate_states():
    data=spectrum()
    for p in data["curves"][0]["points"]:p.update(amplitude_pixel=20.,reconstructed_amplitude=0.)
    for p in data["manual_documents"]["a"]["curves"][0]["points"]:p["x"]=20.
    result=calculate_alpha(data,{"lambda":reference(2),"omega_log":reference(0)})
    assert result["raw"]["pixel_integral"]==0
    assert result["raw"]["parameters"]["omega_log"]["status"]=="unavailable"
    assert result["raw"]["normalization"]["lambda_reference"]==2
    assert result["comparison"]["reference"]==0
    result=calculate_alpha(spectrum(),{"omega_log":reference(0)})
    assert result["comparison"]["status"]=="available" and result["comparison"]["relative_difference_pct"] is None


def test_frequency_not_adjusted_to_match_paper_and_recompute_not_cumulative():
    data=spectrum();before=copy.deepcopy(data)
    first=calculate_alpha(data,{"lambda":reference(2),"omega_log":reference(10000)})
    second=calculate_alpha(data,{"lambda":reference(2),"omega_log":reference(1)})
    assert first["raw"]["omega_log_k"]==second["raw"]["omega_log_k"]
    assert first["candidate"]["coefficient"]==second["candidate"]["coefficient"]
    assert first["candidate"]["frequency_thz"]==[0,3,6] and data==before


def test_ambiguous_references_are_reported_not_selected_by_closeness():
    state={"property_modules":[{"records":[
        dict(property_code="lambda",value_number=v,method_code="test",evidences=[{"quote":"source","page":1}])
        for v in [2.,4.]
    ]}]}
    refs,reasons=reference_choices(state)
    assert "lambda" not in refs and "多个" in reasons["lambda"]
    assert calculate_alpha(spectrum(),refs,reasons)["raw"]["parameters"]["omega_log"]["status"]=="available"


@pytest.mark.parametrize("explanation",["missing",None,""])
def test_manual_http_missing_text_saves_and_normalizes_current_version(manual_http,explanation):
    env=manual_http;body=copy.deepcopy(env["body"]);doc=body["document"]
    if explanation=="missing":doc["calibration"].pop("amplitudeEvidence",None)
    else:doc["calibration"]["amplitudeEvidence"]=explanation
    doc["calibration"]["amplitude"]["values"]=[0,.5]
    first=doc["curves"][0]["points"][0]
    doc["zero"]={"pixel":first["x"],"pointIds":[first["id"]]}
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body)
    assert response.status_code==200,response.text
    item=response.json()["items"][0];points=copy.deepcopy(item["result"]["curves"])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json={
        **env["query"],"expected_version":response.json()["version"],"expected_collection_version":item["version"],"base_run_id":item["run"]["id"],"kind":"alpha2f"})
    assert response.status_code==200,response.text
    fresh=response.json()["items"][0];raw=fresh["result"]["quality"]["integrals"]["raw"]
    assert raw["parameters"]["omega_log"]["status"]=="available"
    assert raw["normalization"]["status"]=="available"
    assert fresh["result"]["curves"]==points
    assert "lambda" not in fresh["result"]["quality"]["comparisons"]["raw"]
    assert fresh["result"]["candidates"]["alpha2f_lambda_normalized"]["base_run_id"]==item["run"]["id"]
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumRun,item["run"]["id"]).result_json["curves"]==points


def test_dos_http_physical_calibration_without_explanation(manual_http):
    env=manual_http;rgb,panel=fixture("phonon_dos")
    with Session(env["engine"]) as session:
        run=session.get(models.SpectrumRun,env["old_run"]);run.result_json=extract_panel(rgb,panel);run.calibration_json=panel;session.commit()
    input=env["client"].get(f"/api/rag/spectra/{env['identity']}/manual",params={**env["params"],"kind":"phonon_dos"}).json()
    doc=input["documents"][0];doc["calibration"].pop("amplitudeEvidence",None)
    doc["calibration"]["amplitude"]["unit"]="modes/THz";doc["calibration"]["amplitude"]["values"]=[0,1]
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json={**env["body"],"document":doc})
    assert response.status_code==200,response.text


def test_overflow_of_one_result_does_not_poison_serialization_or_other_result():
    import json
    data={"curves":[{"id":"a","kind":"alpha2f","unit":"pixel","points":[
        dict(id=str(i),frequency_thz=f,reconstructed_amplitude=a)
        for i,(f,a) in enumerate([(0,0),(3,5e307),(6,1e308)])]}]}
    result=calculate_alpha(data,{"lambda":reference(2)})
    assert result["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert result["raw"]["pixel_integral"] is None
    json.dumps(result,allow_nan=False)
    for p,f in zip(data["curves"][0]["points"],[0,1e307,1e308]):p["frequency_thz"]=f
    for p,a in zip(data["curves"][0]["points"],[0,1,2]):p["reconstructed_amplitude"]=a
    result=calculate_alpha(data)
    assert result["raw"]["parameters"]["omega_log"]["status"]=="unavailable"
    json.dumps(result,allow_nan=False)


def test_public_normalized_candidate_is_not_exposed_outside_accepted_full_curve():
    from backend.services.spectra import mask_public
    data=spectrum();computed=calculate_alpha(data,{"lambda":reference(2)})
    data["calibration"]={"curves":[{"id":"a","kind":"alpha2f"}]}
    data["quality"]={"integrals":{"raw":computed["raw"]},"comparisons":{"raw":{}}}
    data["candidates"]={"alpha2f_lambda_normalized":computed["candidate"]}
    limited=mask_public(data,{"a":{"status":"accepted_limited","frequency_intervals_thz":[[0,3]]}})
    assert "alpha2f_lambda_normalized" not in limited["candidates"]
    assert "alpha2f_lambda_normalized" not in mask_public(data,{})["candidates"]
    assert mask_public(data,{"a":{"status":"accepted"}})["candidates"]["alpha2f_lambda_normalized"]["status"]=="available"
