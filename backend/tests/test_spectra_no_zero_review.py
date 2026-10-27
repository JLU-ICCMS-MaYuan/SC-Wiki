"""#167：无人工零频状态，按实际采样区间计算。"""
import copy
import math
import pytest
from backend.spectra.recalculate import alpha_integrals, dos_integrals
from backend.tests.test_spectra_recalculate import alpha_payload, dos_payload


def test_positive_start_alpha_integrates_existing_interval_without_confirmation():
    payload=alpha_payload()
    for p in payload["curves"][0]["points"]:
        p["frequency_thz"]+=.2
        p["amplitude_pixel"]=p["reconstructed_amplitude"]=.01*p["frequency_thz"]
    before=copy.deepcopy(payload)
    r=alpha_integrals(payload)
    assert r["status"]=="available"
    assert r["minimum_integrated_thz"]==.2 and r["maximum_integrated_thz"]==6.2
    assert r["pixel_integral"]==pytest.approx(.12)
    expected=math.exp(((6.2*math.log(6.2)-6.2)-(.2*math.log(.2)-.2))/6)*47.99243073366221
    assert r["omega_log_k"]==pytest.approx(expected)
    assert r["positive_frequency_complete"] is False
    assert payload==before


def test_positive_start_dos_keeps_actual_interval():
    payload=dos_payload()
    for p in payload["curves"][0]["points"]:p["frequency_thz"]+=.2
    before=copy.deepcopy(payload)
    result=dos_integrals(payload,{"primitive_atoms":2})
    assert result["status"]=="available" and result["integral"]==6
    assert result["frequency_interval_thz"]==[.2,6.2]
    assert payload==before


@pytest.mark.parametrize("legacy",[None,{},{"pixel":999,"pointIds":["missing"]},"invalid-old-field"])
def test_legacy_zero_state_has_no_effect_on_numeric_samples(legacy):
    from backend.spectra.samples import connected_samples
    curve=dos_payload()["curves"][0]
    for p in curve["points"]:p["frequency_thz"]+=.2
    assert connected_samples(curve,{"zero":legacy})[0]==[.2,3.2,6.2]


def test_real_divergence_is_not_hidden_by_removing_manual_review():
    payload=alpha_payload()
    payload["curves"][0]["points"][0].update(amplitude_pixel=.1,reconstructed_amplitude=.1)
    result=alpha_integrals(payload)
    assert result["status"]=="unavailable" and "发散" in result["reason"]


def test_positive_dos_can_normalize_to_3n_without_zero_gate():
    from backend.tests.test_spectra_dos_relative import payload, PRIMITIVE
    from backend.spectra.dos import calculate_dos
    p=payload()
    for c in p["curves"]:
        for point in c["points"]:point["frequency_thz"]+=.2
    before=copy.deepcopy(p)
    result=calculate_dos(p,PRIMITIVE)
    assert result["relative"]["normalization"]["status"]=="available"
    assert result["relative"]["normalization"]["total_mode_integral"]==pytest.approx(9)
    assert all(c["frequency_interval_thz"]==[.2,1.2] for c in result["relative"]["components"])
    assert p==before


from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend.tests.test_spectra_recalculate import recalc_body


def test_http_save_positive_start_and_recalculate_without_zero(manual_http):
    e=manual_http;client=e["client"];body=copy.deepcopy(e["body"]);doc=body["document"]
    assert "zero" not in doc
    doc["curves"][0]["points"]=doc["curves"][0]["points"][4:]
    doc["curves"][0]["points"][0]["breakBefore"]=True
    doc["operations"].append(dict(kind="delete",at="test",detail="仅保留实际采样区间"))
    url=f"/api/rag/spectra/{e['identity']}"
    response=client.post(url+"/manual",json=body);assert response.status_code==200,response.text
    saved=response.json()["items"][0]
    assert "manual_zero_checks" not in saved["result"]["quality"]
    points=copy.deepcopy(saved["result"]["curves"][0]["points"])
    result=client.post(url+"/recalculate",json=recalc_body(e,saved))
    assert result.status_code==200,result.text
    item=result.json()["items"][0];raw=item["result"]["quality"]["integrals"]["raw"]
    assert raw["status"]=="available"
    assert raw["minimum_integrated_thz"]==pytest.approx(.2)
    assert raw["positive_frequency_complete"] is False
    assert raw["parameters"]["lambda"]["status"]=="available"
    assert item["result"]["curves"][0]["points"]==points
    assert not any(i["kind"] in {"low_endpoint","zero_confirmation"} for c in item["result"]["quality"]["trace_diagnostics"]["alpha2f"]["curves"] for i in c["issues"])


def test_manual_axis_only_removes_machine_cancellation_not_small_positive_frequency():
    from backend.spectra.manual import axis_value
    axis = dict(pixels=[24, 140], values=[.2, 6])
    assert axis_value(axis, 20) == 0
    assert axis_value(axis, 20 + 1e-8) == pytest.approx(5e-10, abs=1e-16)
    assert axis_value(axis, 24) == .2
