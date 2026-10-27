"""预检查/真实截止/精确修复；不补造数值，使用正式HTTP与存储。"""
import copy
import pytest

from backend.spectra.preflight import prepare_repairs, endpoint_valid
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
             highEndpoint=None,zero={"pixel":0,"pointIds":["p0"]},operations=[])
    return dict(curves=[curve],manual_documents={"a":doc},calibration={"curves":[]})


def proof(doc):
    p=max(doc["curves"][0]["points"],key=lambda p:p["x"])
    doc["highEndpoint"]=dict(pointId=p["id"],x=p["x"],y=p["y"],frequencyTHz=p["x"],evidence="原图红线在此截止，图框上沿为额外留白")


def test_real_endpoint_below_frame_can_be_confirmed_without_moving_or_extending():
    data=payload()
    issues=diagnose(data,"alpha2f")["curves"][0]["issues"]
    high=next(i for i in issues if i["kind"]=="high_endpoint")
    assert high["points"][0]["point_id"]=="p2"
    assert high["meta"]["actual_thz"]==6 and high["meta"]["frame_thz"]==10 and high["meta"]["difference_px"]==4
    assert alpha_integrals(data)["status"]=="unavailable"
    original=copy.deepcopy(data["curves"])
    proof(data["manual_documents"]["a"])
    assert endpoint_valid(data["manual_documents"]["a"])
    assert not diagnose(data,"alpha2f")["curves"][0]["issues"]
    assert alpha_integrals(data)["parameters"]["lambda"]["value"]==pytest.approx(.12)
    assert data["curves"]==original


@pytest.mark.parametrize("change",["move","delete","new_higher","calibration","empty_evidence"])
def test_endpoint_evidence_invalidates_on_relevant_changes(change):
    data=payload();doc=data["manual_documents"]["a"];proof(doc)
    if change=="move":doc["curves"][0]["points"][-1]["y"]+=1
    elif change=="delete":doc["curves"][0]["points"].pop()
    elif change=="new_higher":doc["curves"][0]["points"].append(dict(id="new",x=7,y=.07))
    elif change=="calibration":doc["calibration"]["frequency"]["values"]=[0,20]
    else:doc["highEndpoint"]["evidence"]=""
    assert not endpoint_valid(doc)
    assert alpha_integrals(data)["status"]=="unavailable"


def test_precheck_reports_all_numerical_boundaries_instead_of_only_first_error():
    data=payload();curve=data["curves"][0];doc=data["manual_documents"]["a"]
    curve["points"][0]["frequency_thz"]=.5
    curve["points"][1]["frequency_thz"]=7
    curve["points"][1]["reconstructed_amplitude"]=-.1
    doc["zero"]=None
    kinds={i["kind"] for i in diagnose(data,"alpha2f")["curves"][0]["issues"]}
    assert {"frequency_backtrack","negative_amplitude","low_endpoint","high_endpoint","zero_confirmation"}<=kinds
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
    assert alpha_integrals(data)["lambda_integral"]==pytest.approx(.12)
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


def test_endpoint_confirmation_http_persists_and_unlocks_actual_frequency_range(manual_http):
    env=manual_http;body=copy.deepcopy(env["body"]);doc=body["document"]
    end=doc["curves"][0]["points"].pop()
    last=doc["curves"][0]["points"][-1]
    first=doc["curves"][0]["points"][0]
    doc["zero"]=dict(pixel=first["x"],pointIds=[first["id"]])
    doc["highEndpoint"]=dict(pointId=last["id"],x=last["x"],y=last["y"],frequencyTHz=5.95,evidence="合成原图在此截止，上沿留白")
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=body)
    assert response.status_code==200,response.text
    item=response.json()["items"][0]
    assert len(item["result"]["curves"][0]["points"])==len(doc["curves"][0]["points"])
    response=env["client"].post(f"/api/rag/spectra/{env['identity']}/recalculate",json=recalc_body(env,item))
    assert response.status_code==200,response.text
    fresh=response.json()["items"][0]
    assert fresh["result"]["quality"]["integrals"]["raw"]["maximum_integrated_thz"]==pytest.approx(5.95)
    assert fresh["result"]["quality"]["integrals"]["raw"]["parameters"]["lambda"]["status"]=="available"
    assert fresh["result"]["manual_documents"]["a"]["highEndpoint"]==doc["highEndpoint"]
    assert not any(i["kind"]=="high_endpoint" for i in fresh["result"]["quality"]["trace_diagnostics"]["alpha2f"]["curves"][0]["issues"])


def test_server_rejects_forged_endpoint_and_does_not_save(manual_http):
    env=manual_http;request=copy.deepcopy(env["body"]);doc=request["document"]
    p=doc["curves"][0]["points"][10]
    doc["highEndpoint"]=dict(pointId=p["id"],x=p["x"],y=p["y"],frequencyTHz=.5,evidence="不是最高频点")
    r=env["client"].post(f"/api/rag/spectra/{env['identity']}/manual",json=request)
    assert r.status_code==422 and "高频末端确认" in r.text


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


def test_dos_confirmed_individual_cutoffs_integrate_without_padding():
    from backend.spectra.recalculate import dos_integrals
    data=payload(frame=10);first=data["curves"][0]
    first.update(kind="phonon_dos",projection="H",unit="modes/THz/primitive_cell")
    proof(data["manual_documents"]["a"])
    other=copy.deepcopy(first);other.update(id="b",projection="S")
    other["points"][-1].update(frequency_thz=5.,frequency_pixel=5.)
    doc=copy.deepcopy(data["manual_documents"]["a"])
    doc["curves"][0]["id"]="b";doc["curves"][0]["points"][-1]["x"]=5.
    doc["highEndpoint"]=None
    data["curves"].append(other);data["manual_documents"]["b"]=doc
    data["calibration"].update(projection_complete=True,projection_scale_confirmed=True)
    assert any(i["kind"]=="projection_range" for r in diagnose(data,"phonon_dos")["curves"] for i in r["issues"])
    proof(doc)
    assert not any(i["kind"]=="projection_range" for r in diagnose(data,"phonon_dos")["curves"] for i in r["issues"])
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
