"""预检查/真实截止/精确修复；不补造数值，使用正式HTTP与存储。"""
import copy
import pytest

from backend.spectra.preflight import prepare_repairs
from backend.spectra.topology import diagnose
from backend.spectra.recalculate import alpha_integrals
from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend.tests.test_spectra_recalculate import recalc_body


def payload(frame=10):
    values=[(0,0),(3,.03),(6,.06)]
    points=[dict(id=f"p{i}",frequency_thz=f,reconstructed_amplitude=a,frequency_pixel=f,amplitude_pixel=a,
                 breakBefore=i==0,segment="one") for i,(f,a) in enumerate(values)]
    curve=dict(id="a",kind="alpha2f",unit="dimensionless",physical_definition_confirmed=True,
               frequency_direction="x",roi=[0,0,frame,10],
               axis_calibration={"frequency":{"slope":1.,"intercept":0.},"amplitude":{"slope":1.,"intercept":0.}},
               points=points)
    doc=dict(source={"plot":[0,0,frame,10]},
             calibration={"direction":"x","frequency":{"pixels":[0,frame],"values":[0,frame],"unit":"THz"},
                          "amplitude":{"pixels":[0,10],"values":[0,10],"unit":"dimensionless"},"amplitudeEvidence":"原图有独立尺度"},
             curves=[dict(id="a",name="α²F",points=[dict(id=p["id"],x=p["frequency_pixel"],y=p["amplitude_pixel"],
                                              breakBefore=p["breakBefore"],segment=p["segment"]) for p in points])],
             zero={"pixel":0,"pointIds":["p0"]},operations=[])
    return dict(curves=[curve],manual_documents={"a":doc},calibration={"curves":[]})


@pytest.mark.parametrize("frame",[6.000002,10.,1000.])
def test_saved_maximum_is_used_without_any_frame_comparison(frame):
    data=payload(frame=frame);original=copy.deepcopy(data["curves"])
    result=alpha_integrals(data)
    assert result["pixel_integral"]==pytest.approx(.12)
    assert result["maximum_integrated_thz"]==6.
    assert not diagnose(data,"alpha2f")["curves"][0]["issues"]
    assert data["curves"]==original


@pytest.mark.parametrize("legacy",[None,{},{"pointId":"missing","frequencyTHz":999,"evidence":""},"old-invalid-field"])
def test_legacy_endpoint_confirmation_is_completely_ignored(legacy):
    data=payload();data["manual_documents"]["a"]["highEndpoint"]=legacy
    assert alpha_integrals(data)["parameters"]["omega_log"]["status"]=="available"
    assert not diagnose(data,"alpha2f")["curves"][0]["issues"]


def test_precheck_reports_all_numerical_boundaries_instead_of_only_first_error():
    data=payload();curve=data["curves"][0];doc=data["manual_documents"]["a"]
    curve["points"][0]["frequency_thz"]=.5
    curve["points"][1]["frequency_thz"]=7
    curve["points"][1]["reconstructed_amplitude"]=-.1
    doc["zero"]=None
    kinds={i["kind"] for i in diagnose(data,"alpha2f")["curves"][0]["issues"]}
    assert {"frequency_backtrack","negative_amplitude"}<=kinds
    for issue in diagnose(data,"alpha2f")["curves"][0]["issues"]:
        assert issue["points"] and issue["points"][0]["point_id"]


def exact_gap():
    data=payload(frame=6);curve=data["curves"][0];doc=data["manual_documents"]["a"]
    a=curve["points"][1];b=copy.deepcopy(a);b.update(id="duplicate",breakBefore=True,segment="two")
    curve["points"].insert(2,b)
    db=copy.deepcopy(doc["curves"][0]["points"][1]);db.update(id="duplicate",breakBefore=True,segment="two")
    doc["curves"][0]["points"].insert(2,db)
    return data


def test_exact_unique_gap_is_automatically_connected_all_points_remain():
    data=exact_gap();before=copy.deepcopy(data["curves"][0]["points"])
    repairs=prepare_repairs(data,"alpha2f","2026-10-27T00:00:00Z")
    assert len(repairs)==1
    assert not diagnose(data,"alpha2f")["curves"][0]["issues"]
    assert alpha_integrals(data)["pixel_integral"]==pytest.approx(.12)
    after=data["curves"][0]["points"]
    assert len(after)==len(before)
    assert [{k:v for k,v in p.items() if k!="joinTo"} for p in after]==before
    assert data["manual_documents"]["a"]["operations"][-1]["kind"]=="auto-connect-exact-endpoints"
    assert prepare_repairs(data,"alpha2f","again")==[]


@pytest.mark.parametrize("problem",["near_pixel","different_value","ambiguous","frequency_overlap","cycle","missing_doc"])
def test_auto_repair_never_guesses_near_or_ambiguous_connections(problem):
    data=exact_gap();points=data["curves"][0]["points"];doc=data["manual_documents"]["a"]
    if problem=="near_pixel":points[2]["amplitude_pixel"]+=1e-9;doc["curves"][0]["points"][2]["y"]+=1e-9
    elif problem=="different_value":points[2]["reconstructed_amplitude"]+=1e-9
    elif problem=="ambiguous":
        extra=copy.deepcopy(points[2]);extra["id"]="third";points.insert(2,extra)
        dp=copy.deepcopy(doc["curves"][0]["points"][2]);dp["id"]="third";doc["curves"][0]["points"].insert(2,dp)
    elif problem=="frequency_overlap":points[-1]["frequency_thz"]=1
    elif problem=="cycle":
        data=payload(frame=6);data["curves"][0]["points"][-1]["joinTo"]="p0"
    else:data["manual_documents"]={}
    before=copy.deepcopy(data)
    assert prepare_repairs(data,"alpha2f","test")==[]
    assert data==before


@pytest.mark.parametrize("pixel",[139.999998,139.,100.])
def test_saved_endpoint_http_needs_no_confirmation_and_does_not_add_points(manual_http,pixel):
    env=manual_http;body=copy.deepcopy(env["body"]);doc=body["document"]
    # 截短有效路径，仅保留频率小于目标末点的前驱，避免引入回折。
    doc["curves"][0]["points"]=[p for p in doc["curves"][0]["points"] if p["x"]<pixel]+[{
        **doc["curves"][0]["points"][-1],"id":"last-saved","x":pixel}]
    first=doc["curves"][0]["points"][0]
    doc["zero"]=dict(pixel=first["x"],pointIds=[first["id"]])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body)
    assert response.status_code==200,response.text
    item=response.json()["items"][0];original=copy.deepcopy(item["result"]["curves"])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalc_body(env,item))
    assert response.status_code==200,response.text
    fresh=response.json()["items"][0]
    assert fresh["result"]["quality"]["integrals"]["raw"]["maximum_integrated_thz"]==pytest.approx((pixel-20)*.05)
    assert fresh["result"]["quality"]["integrals"]["raw"]["parameters"]["lambda"]["status"]=="available"
    assert fresh["result"]["curves"]==original
    assert not any(i["kind"] in {"high_endpoint","projection_range"} for i in fresh["result"]["quality"]["trace_diagnostics"]["alpha2f"]["curves"][0]["issues"])


def test_old_client_endpoint_field_does_not_block_save_and_is_not_returned(manual_http):
    env=manual_http;request=copy.deepcopy(env["body"]);doc=request["document"]
    doc["highEndpoint"]={"pointId":"does-not-exist","evidence":""}
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=request)
    assert response.status_code==200,response.text
    item=response.json()["items"][0]
    assert "highEndpoint" not in item["result"]["manual_documents"]["a"]
    params={**env["params"],"collection_version":item["version"],"run_id":item["run"]["id"]}
    result=env["client"].get(f"/api/rag/spectra/{env['identity']}/manual",params=params)
    assert result.status_code==200 and "highEndpoint" not in result.json()["documents"][0]


def test_http_exact_gap_repair_is_persisted_without_dropping_source_points(manual_http):
    env=manual_http;request=copy.deepcopy(env["body"]);doc=request["document"];points=doc["curves"][0]["points"]
    duplicate=copy.deepcopy(points[60]);duplicate.update(id="same-source-endpoint",breakBefore=True)
    points.insert(61,duplicate)
    doc["zero"]=dict(pixel=points[0]["x"],pointIds=[points[0]["id"]])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=request)
    assert response.status_code==200,response.text
    old=response.json()["items"][0];before=copy.deepcopy(old["result"]["curves"][0]["points"])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalc_body(env,old))
    assert response.status_code==200,response.text
    result=response.json()["items"][0]["result"]
    assert len(result["quality"]["automatic_repairs"]["alpha2f"])==1
    assert result["quality"]["integrals"]["raw"]["parameters"]["lambda"]["status"]=="available"
    assert [{k:v for k,v in p.items() if k!="joinTo"} for p in result["curves"][0]["points"]]==before
    assert result["manual_documents"]["a"]["operations"][-1]["kind"]=="auto-connect-exact-endpoints"
    from backend.services.spectra import mask_public
    assert "automatic_repairs" not in mask_public(result,{"a":{"status":"accepted"}})["quality"]


def test_dos_different_saved_maxima_integrate_without_confirmation_or_padding():
    from backend.spectra.recalculate import dos_integrals
    data=payload(frame=10);first=data["curves"][0]
    first.update(kind="phonon_dos",projection="H",unit="modes/THz/primitive_cell")
    other=copy.deepcopy(first);other.update(id="b",projection="S")
    other["points"][-1].update(frequency_thz=5.,frequency_pixel=5.)
    doc=copy.deepcopy(data["manual_documents"]["a"])
    doc["curves"][0]["id"]="b";doc["curves"][0]["points"][-1]["x"]=5.
    data["curves"].append(other);data["manual_documents"]["b"]=doc
    data["calibration"].update(projection_complete=True,projection_scale_confirmed=True)
    assert not any(i["kind"] in {"high_endpoint","projection_range"} for r in diagnose(data,"phonon_dos")["curves"] for i in r["issues"])
    original=copy.deepcopy(data["curves"])
    result=dos_integrals(data,None)
    assert result["status"]=="available"
    assert result["component_intervals"]=={"a":[0.,6.],"b":[0.,5.]}
    assert result["integral"]==pytest.approx(.18+.135)
    assert data["curves"]==original


def test_unlinked_duplicate_samples_are_not_silently_folded():
    from backend.spectra.preflight import coincident
    a=dict(frequency_pixel=3,amplitude_pixel=.03,frequency_thz=3,reconstructed_amplitude=.03)
    assert not coincident(a,copy.deepcopy(a))


def test_explicitly_undone_auto_connection_is_not_reapplied():
    import json
    data=exact_gap()
    prepare_repairs(data,"alpha2f","first")
    doc=data["manual_documents"]["a"]
    edge=json.loads(doc["operations"][-1]["detail"])
    for p in data["curves"][0]["points"]+doc["curves"][0]["points"]:
        if p["id"]==edge["from_id"]:p.pop("joinTo",None)
    doc["operations"].append(dict(kind="undo-auto-connect",at="user",detail=json.dumps({"edges":[edge]})))
    before=copy.deepcopy(data)
    assert prepare_repairs(data,"alpha2f","second")==[]
    assert data==before
