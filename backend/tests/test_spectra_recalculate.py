"""重算数值、真实路由和持久化版本边界；复用当前MySQL授权隔离夹具。"""
import copy
import math

import pytest
from sqlalchemy.orm import Session

from backend import models
from backend.spectra.recalculate import alpha_integrals, connected_samples, dos_integrals
from backend.services.spectra import mask_public
from backend.tests.test_spectra_manual import manual_storage, manual_http


def alpha_payload(unit="dimensionless"):
    curve = dict(id="a",kind="alpha2f",unit=unit,physical_definition_confirmed=True,
                 axis_calibration={"amplitude":{"slope":1.,"intercept":0.}},
                 points=[dict(id=str(i),frequency_thz=f,reconstructed_amplitude=.01*f,amplitude_pixel=.01*f)
                         for i,f in enumerate([0.,3.,6.])])
    return dict(curves=[curve],calibration={"curves":[{"id":"a","amplitude_evidence":"原图零基线及全谱统一线性倍率"}]})


def test_exact_alpha_and_relative_scale_cancel():
    payload=alpha_payload()
    result=alpha_integrals(payload)
    assert result["pixel_integral"]==pytest.approx(.12)
    assert result["parameters"]["omega_log"]["value"]==pytest.approx(6/math.e*47.99243073366221)
    for scale in [1.,37.]:
        relative=alpha_payload("pixel")
        for p in relative["curves"][0]["points"]:p["reconstructed_amplitude"]*=scale;p["amplitude_pixel"]*=scale
        r=alpha_integrals(relative)
        assert r["parameters"]["lambda"]["status"]=="unavailable"
        assert r["lambda_integral"] is None
        assert r["parameters"]["omega_log"]["value"]==pytest.approx(result["omega_log_k"])
    assert payload==alpha_payload()


@pytest.mark.parametrize("problem",["gap","branch","cycle","backtrack","duplicate","nonzero_zero","negative"])
def test_unsafe_spectra_remain_unavailable(problem):
    payload=alpha_payload();curve=payload["curves"][0];points=curve["points"]
    if problem=="gap":points[1]["breakBefore"]=True
    elif problem=="branch":points.append(dict(id="branch",frequency_thz=4.,reconstructed_amplitude=.04,connectTo="1"))
    elif problem=="cycle":points[-1]["joinTo"]="0"
    elif problem=="backtrack":points[1]["frequency_thz"]=7
    elif problem=="duplicate":points[1]["frequency_thz"]=0
    elif problem=="nonzero_zero":points[0]["reconstructed_amplitude"]=.1;points[0]["amplitude_pixel"]=.1
    elif problem=="missing_evidence":payload["calibration"]["curves"][0]["amplitude_evidence"]=""
    elif problem=="unknown_frequency":curve["physical_definition_confirmed"]=False
    elif problem=="negative":points[1]["reconstructed_amplitude"]=-1;points[1]["amplitude_pixel"]=-1
    r=alpha_integrals(payload)
    assert r["status"]=="unavailable"
    assert all(p["status"]=="unavailable" and p["reason"] for p in r["parameters"].values())


def test_join_edge_restores_a_path_without_sorting_or_mutating():
    payload=alpha_payload();points=payload["curves"][0]["points"]
    points[1]["breakBefore"]=True;points[0]["joinTo"]="1"
    before=copy.deepcopy(points)
    assert alpha_integrals(payload)["pixel_integral"]==pytest.approx(.12)
    assert points==before
    points.reverse()
    for p in points:p.pop("joinTo",None);p.pop("breakBefore",None)
    assert connected_samples(payload["curves"][0])[0]==[0,3,6]


def dos_payload():
    payload=alpha_payload();c=payload["curves"][0]
    c.update(kind="phonon_dos",unit="modes/THz/primitive_cell",projection="H")
    for p in c["points"]:p["reconstructed_amplitude"]=1.
    payload["calibration"].update(projection_complete=True,projection_scale_confirmed=True)
    return payload


def test_dos_integral_and_comparison_are_independent():
    payload=dos_payload()
    result=dos_integrals(payload,None)
    assert result["integral"]==6
    assert result["comparison_status"]=="unavailable"
    result=dos_integrals(payload,{"primitive_atoms":2})
    assert result["comparison_status"]=="available"
    assert result["absolute_difference"]==0 and result["target_modes"]==6
    # 各分波可有自己的采样网格，但频段/密度单位必须一致。
    other=copy.deepcopy(payload["curves"][0]);other.update(id="b",projection="S")
    other["points"]=[other["points"][0],other["points"][-1]]
    payload["curves"].append(other)
    assert dos_integrals(payload,{"primitive_atoms":4})["integral"]==12


@pytest.mark.parametrize("problem",["pixel","incomplete","duplicate","total","gap"])
def test_dos_rejects_invalid_total(problem):
    payload=dos_payload()
    if problem=="pixel":payload["curves"][0]["unit"]="pixel"
    elif problem=="incomplete":payload["calibration"]["projection_complete"]=False
    elif problem=="gap":payload["curves"][0]["points"][1]["breakBefore"]=True
    else:
        other=copy.deepcopy(payload["curves"][0]);other["id"]="b"
        if problem=="total":other["projection"]="total"
        payload["curves"].append(other)
    assert dos_integrals(payload,{"primitive_atoms":2})["status"]=="unavailable"


def recalc_body(env, item=None):
    return {k:v for k,v in env["body"].items() if k!="document"}|{"kind":"alpha2f"}|(
        {"expected_collection_version":item["version"],"base_run_id":item["run"]["id"]} if item else {})


def test_recalculate_http_history_conflicts_and_manual_invalidation(manual_http):
    env=manual_http;client=env["client"];url=f"/api/rag/spectra/{env['identity']}/recalculate"
    before=copy.deepcopy(env["old_result"])
    response=client.post(url,json=recalc_body(env));assert response.status_code==200,response.text
    item=response.json()["items"][0];raw=item["result"]["quality"]["integrals"]["raw"]
    assert raw["parameters"]["lambda"]["status"]=="available"
    assert raw["parameters"]["omega_log"]["status"]=="available"
    assert item["result"]["curves"]==before["curves"]
    assert item["result"]["quality"]["recalculations"]["alpha2f"]["base_run_id"]==env["old_run"]
    assert item["review"]=={} and item["run"]["id"]!=env["old_run"]
    assert client.post(url,json=recalc_body(env)).status_code==409
    with Session(env["engine"]) as session:
        assert session.get(models.SpectrumRun,env["old_run"]).result_json==before
    fresh=client.get("/api/rag/spectra",params=env["query"]).json()["items"][0]
    assert fresh["result"]["quality"]["integrals"]["raw"]==raw
    params={**env["query"],"kind":"alpha2f","collection_version":item["version"],"run_id":item["run"]["id"]}
    doc=client.get(f"/api/rag/spectra/{env['identity']}/manual",params=params).json()
    document=doc["documents"][0]
    document["zero"]={"pixel":20,"pointIds":[document["curves"][0]["points"][0]["id"]]}
    body={**env["body"],"expected_collection_version":item["version"],"base_run_id":item["run"]["id"],"document":document}
    saved=client.post(f"/api/rag/spectra/{env['identity']}/manual",json=body).json()["items"][0]
    assert "recalculations" not in saved["result"]["quality"]
    assert saved["result"]["quality"]["integrals"]["raw"]["status"]=="unavailable"
    recalculated=client.post(url,json=recalc_body(env,saved))
    assert recalculated.status_code==200,recalculated.text
    assert recalculated.json()["items"][0]["result"]["quality"]["integrals"]["raw"]["parameters"]["lambda"]["status"]=="available", recalculated.json()["items"][0]["result"]["quality"]["integrals"]["raw"]


def test_recalculate_http_permission_and_state_guard(manual_http):
    env=manual_http;url=f"/api/rag/spectra/{env['identity']}/recalculate";body=recalc_body(env)
    env["actor"][0].id=999
    assert env["client"].post(url,json=body).status_code==403
    env["actor"][0].id=1
    env["draft"]["material_states"][0]["pressure_value_gpa"]=300
    assert env["client"].post(url,json=body).status_code==409


def test_recalculate_http_unavailable_is_persisted_without_changing_points(manual_http):
    env=manual_http
    body=copy.deepcopy(env["body"]);body["document"]["curves"][0]["points"][10]["breakBefore"]=True
    saved=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body).json()["items"][0]
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalc_body(env,saved))
    assert response.status_code==200,response.text
    result=response.json()["items"][0]["result"]
    assert result["quality"]["integrals"]["raw"]["status"]=="unavailable"
    assert "缺口" in result["quality"]["integrals"]["raw"]["reason"]
    assert result["curves"]==saved["result"]["curves"]


def test_public_limited_spectrum_cannot_expose_full_integral():
    payload=alpha_payload();payload["quality"]={"integrals":{"raw":alpha_integrals(payload)},"comparisons":{"raw":{}},"recalculations":{"alpha2f":{"author_id":1}}};payload["candidates"]={}
    output=mask_public(payload,{"a":{"status":"accepted_limited","frequency_intervals_thz":[[0,3]]}})
    assert "integrals" not in output["quality"]
    assert "recalculations" not in output["quality"]


def test_recalculate_dos_http_integral_without_primitive(manual_http):
    env=manual_http
    with Session(env["engine"]) as session:
        run=session.get(models.SpectrumRun,env["old_run"])
        run.result_json=dos_payload()
        session.commit()
    before=dos_payload()["curves"]
    body=recalc_body(env);body["kind"]="phonon_dos"
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=body)
    assert response.status_code==200,response.text
    result=response.json()["items"][0]["result"]
    assert result["curves"]==before
    assert result["quality"]["dos_mode_integral"]["integral"]==6
    assert result["quality"]["dos_mode_integral"]["comparison_status"]=="unavailable"
    assert "phonon_dos" in result["quality"]["recalculations"]


def test_recalculate_roundoff_only_not_real_nonzero_baseline():
    payload=alpha_payload()
    curve=payload["curves"][0]
    curve["axis_calibration"]={"amplitude":{"slope":-.005,"intercept":.4}}
    curve["points"][0].update(amplitude_pixel=80.,reconstructed_amplitude=5e-17)
    assert alpha_integrals(payload)["parameters"]["omega_log"]["status"]=="available"
    curve["points"][0]["reconstructed_amplitude"]=1e-10
    curve["points"][0]["amplitude_pixel"]=79.99999998
    assert alpha_integrals(payload)["status"]=="unavailable"


def test_mysql_concurrent_recalculations_only_one_commits(manual_http):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import select, func
    env=manual_http
    if env["engine"].dialect.name!="mysql":
        pytest.skip("重算行锁竞争仅在明确授权的MySQL上验证")
    barrier=Barrier(2)
    def calculate(_):
        barrier.wait(timeout=10)
        return env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalc_body(env)).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(calculate,[1,2]))==[200,409]
    with Session(env["engine"]) as session:
        assert session.scalar(select(func.count()).select_from(models.SpectrumRun).where(models.SpectrumRun.collection_id==env["identity"]))==2
        assert session.get(models.SpectrumRun,env["old_run"]).result_json==env["old_result"]


def test_topology_distinguishes_parts_isolated_cycle_and_branch():
    from backend.spectra.topology import diagnose_curve
    payload=alpha_payload();curve=payload["curves"][0]
    curve.update(frequency_direction="y",axis_calibration={"frequency":{"slope":-2,"intercept":20},"amplitude":{"slope":1,"intercept":-30}})
    for point in curve["points"]:point.pop("amplitude_pixel",None)
    curve["points"][1]["breakBefore"]=True
    report=diagnose_curve(curve)
    assert report["component_count"]==2
    assert [i["kind"] for i in report["issues"]]==["isolated","disconnected"]
    point=report["issues"][0]["points"][0]
    assert point==dict(point_id="0",frequency_thz=0.,amplitude=0.,x=30.,y=10.)
    # 同一曲线可能同时含闭环和分叉，回边两端确实在环中。
    curve["points"][1].pop("breakBefore")
    curve["points"][-1]["joinTo"]="0"
    curve["points"].append(dict(id="tail",frequency_thz=7.,reconstructed_amplitude=.07,connectTo="2"))
    report=diagnose_curve(curve)
    assert {i["kind"] for i in report["issues"]}=={"branch","cycle"}
    cycle=next(i for i in report["issues"] if i["kind"]=="cycle")
    assert {p["point_id"] for p in cycle["points"]} <= {"0","1","2"}
    assert "tail" not in {p["point_id"] for p in cycle["points"]}


def test_topology_legacy_ids_match_editor_and_no_close_point_autojoin():
    from backend.spectra.topology import diagnose_curve
    curve=alpha_payload()["curves"][0]
    for p in curve["points"]:p.pop("id")
    curve["points"][1]["breakBefore"]=True
    curve["points"][1]["frequency_thz"]=1e-9
    report=diagnose_curve(curve)
    assert report["component_count"]==2
    assert report["issues"][0]["points"][0]["point_id"]=="a:p0"
    assert report["issues"][1]["points"][0]["point_id"]=="a:p1"


def test_topology_long_curve_no_recursion_or_pairwise_distance():
    from backend.spectra.topology import diagnose_curve
    curve=alpha_payload()["curves"][0]
    curve["points"]=[dict(id=str(i),frequency_thz=i,reconstructed_amplitude=0) for i in range(20000)]
    before=copy.deepcopy(curve)
    assert diagnose_curve(curve)["issues"]==[]
    curve["points"][-1]["joinTo"]="0"
    report=diagnose_curve(curve)
    assert len(report["issues"])==1 and report["issues"][0]["kind"]=="cycle"
    curve["points"][-1].pop("joinTo")
    assert curve==before


def test_topology_http_versioned_and_invalidated_on_save(manual_http):
    env=manual_http;client=env["client"];url=f"/api/rag/spectra/{env['identity']}"
    body=copy.deepcopy(env["body"])
    pts=body["document"]["curves"][0]["points"]
    pts[50]["breakBefore"]=True;pts[51]["breakBefore"]=True
    saved=client.post(url+"/manual",json=body).json()["items"][0]
    response=client.post(url+"/recalculate",json=recalc_body(env,saved))
    assert response.status_code==200,response.text
    item=response.json()["items"][0]
    report=item["result"]["quality"]["trace_diagnostics"]["alpha2f"]["curves"][0]
    isolated=next(i for i in report["issues"] if i["kind"]=="isolated")
    point=isolated["points"][0]
    assert point["point_id"]==pts[50]["id"] and point["x"]==pts[50]["x"] and point["y"]==pts[50]["y"]
    assert not any(i["kind"]=="cycle" for i in report["issues"])
    assert item["result"]["curves"]==saved["result"]["curves"]
    params={**env["query"],"kind":"alpha2f","collection_version":item["version"],"run_id":item["run"]["id"]}
    seed=client.get(url+"/manual",params=params).json()
    assert any(p["id"]==point["point_id"] for p in seed["documents"][0]["curves"][0]["points"])
    body={**body,"expected_collection_version":item["version"],"base_run_id":item["run"]["id"],"document":seed["documents"][0]}
    fresh=client.post(url+"/manual",json=body).json()["items"][0]
    assert "trace_diagnostics" not in fresh["result"]["quality"]
    assert client.get(url+"/manual",params=params).status_code==409
    public=mask_public(item["result"],{"a":{"status":"accepted"}})
    assert "trace_diagnostics" not in public["quality"]


def test_topology_dos_reports_all_projections_even_if_units_unavailable():
    from backend.spectra.topology import diagnose
    payload=dos_payload()
    other=copy.deepcopy(payload["curves"][0]);other.update(id="Sc",projection="Sc")
    other["points"][1]["breakBefore"]=True
    payload["curves"].append(other)
    report=diagnose(payload,"phonon_dos")
    assert report["curves"][0]["issues"]==[]
    assert report["curves"][1]["curve_id"]=="Sc" and report["curves"][1]["issues"]
