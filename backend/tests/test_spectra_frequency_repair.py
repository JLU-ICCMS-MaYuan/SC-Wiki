"""#166：真实连线上的受限频率修正，保留源幅值和版本。"""
import copy
import json
import time
import pytest

from backend.spectra.frequency_repair import repair_frequencies
from backend.spectra.samples import connected_samples


def data(values=(0., 5., 4.8, 10.), direction="x", kind="phonon_dos"):
    pixels = list(values) if direction == "x" else [20-v for v in values]
    points = [dict(id=f"p{i}",frequency_thz=f,frequency_pixel=p,amplitude_pixel=2.+i,
                   reconstructed_amplitude=2.+i,observed_amplitude=2.+i,segment="s",
                   breakBefore=i==0,status="manual_adjusted",manual=True) for i,(f,p) in enumerate(zip(values,pixels))]
    if kind == "alpha2f":
        points[0].update(reconstructed_amplitude=0.,observed_amplitude=0.,amplitude_pixel=0.)
    doc = dict(id="doc",source={"plot":[0,0,20,20]},
               calibration=dict(direction=direction,frequency=dict(pixels=[0,20] if direction=="x" else [20,0],values=[0,20],unit="THz")),
               curves=[dict(id="a",name="H",pathOrdered=True,points=[dict(id=p["id"],x=p["frequency_pixel"] if direction=="x" else p["amplitude_pixel"],
                   y=p["amplitude_pixel"] if direction=="x" else p["frequency_pixel"],segment="s",breakBefore=i==0,status="人工调整",manual=True)
                   for i,p in enumerate(points)])],zero=dict(pixel=0 if direction=="x" else 20,pointIds=["p0"]),
               operations=[dict(kind="move",at="test",detail="人工调整")])
    curve=dict(id="a",kind=kind,projection="H",unit="pixel",frequency_direction=direction,
               points=points,axis_calibration={"frequency":dict(slope=1 if direction=="x" else -1,intercept=0 if direction=="x" else 20)})
    return dict(curves=[curve],manual_documents={"a":doc})


@pytest.mark.parametrize("direction",["x","y"])
@pytest.mark.parametrize("kind",["phonon_dos","alpha2f"])
def test_small_backtrack_strict_bounded_same_amplitude_and_editor(direction,kind):
    payload=data(direction=direction,kind=kind);before=copy.deepcopy(payload)
    reports=repair_frequencies(payload,kind,"test")
    assert reports[0]["new_point_count"]==2
    assert 0<reports[0]["max_shift_px"]<=.5
    f,a=connected_samples(payload["curves"][0],payload["manual_documents"]["a"])
    assert all(b>a for a,b in zip(f,f[1:]))
    assert f[0]==0 and f[-1]==10
    for i,p in enumerate(payload["curves"][0]["points"]):
        old=before["curves"][0]["points"][i]
        for key in ("id","amplitude_pixel","reconstructed_amplitude","observed_amplitude","segment","breakBefore"):
            assert p[key]==old[key]
        dp=payload["manual_documents"]["a"]["curves"][0]["points"][i]
        assert dp[direction]==p["frequency_pixel"]
    again=copy.deepcopy(payload)
    report=repair_frequencies(payload,kind,"again")[0]
    assert report["new_point_count"]==0 and report["point_count"]==2
    assert payload==again


@pytest.mark.parametrize("values",[(0,5,5,10),(0,5,4.8,4.9,10),(0,5,4.2,4.2,4.2,10)])
def test_duplicates_and_block_bound_clamping(values):
    payload=data(values)
    report=repair_frequencies(payload,"phonon_dos","test")[0]
    assert report["new_point_count"]>0
    f,_=connected_samples(payload["curves"][0])
    assert all(b>a for a,b in zip(f,f[1:]))
    assert max(abs(a-b) for a,b in zip(f,values))<=.5


@pytest.mark.parametrize("values",[(0,8,4,10),(0,10,9.8,9.6,9.4,9.2,9,8.8,8.6,8.4,8.2,8,15)])
def test_large_or_accumulated_backtrack_not_hidden(values):
    payload=data(values);before=copy.deepcopy(payload)
    r=repair_frequencies(payload,"phonon_dos","test")[0]
    assert not r["new_point_count"] and r["skipped"]
    assert payload==before


def test_alpha_low_frequency_and_zero_are_fixed():
    payload=data((0,.8,.7,10),kind="alpha2f");before=copy.deepcopy(payload)
    assert repair_frequencies(payload,"alpha2f","test")[0]["new_point_count"]==0
    assert payload==before


@pytest.mark.parametrize("problem",["gap","cycle","branch","mismatch","invalid","outside"])
def test_unsafe_graph_or_source_is_not_modified(problem):
    payload=data();curve=payload["curves"][0];doc=payload["manual_documents"]["a"]
    if problem=="gap":curve["points"][1]["breakBefore"]=True
    if problem=="cycle":curve["points"][-1]["joinTo"]="p0"
    if problem=="branch":curve["points"][-1]["joinTo"]="p1"
    if problem=="mismatch":doc["curves"][0]["points"][1]["x"]+=.1
    if problem=="invalid":curve["points"][1]["reconstructed_amplitude"]=None
    if problem=="outside":doc["source"]["plot"][2]=4
    before=copy.deepcopy(payload)
    assert repair_frequencies(payload,"phonon_dos","test")[0]["new_point_count"]==0
    assert payload==before


def test_reverse_path_and_safe_block_next_to_unrepairable_block():
    payload=data((0,3,2.8,6,10,8,15))
    payload["curves"][0]["points"].reverse()
    payload["manual_documents"]["a"]["curves"][0]["points"].reverse()
    for collection in (payload["curves"][0]["points"],payload["manual_documents"]["a"]["curves"][0]["points"]):
        for i,p in enumerate(collection):p["breakBefore"]=i==0
    report=repair_frequencies(payload,"phonon_dos","test")[0]
    assert report["new_point_count"]==2 and report["skipped"]
    byid={p["id"]:p for p in payload["curves"][0]["points"]}
    assert byid["p1"]["frequency_thz"]<byid["p2"]["frequency_thz"]
    assert byid["p4"]["frequency_thz"]==10 and byid["p5"]["frequency_thz"]==8


def test_long_path_no_per_pair_sort_and_operation_chunks_respect_contract():
    values=[float(i) for i in range(20000)]
    values[10001]=9999.8
    payload=data(values);doc=payload["manual_documents"]["a"]
    doc["source"]["plot"]=[0,0,20000,20002]
    doc["calibration"]["frequency"]=dict(pixels=[0,20000],values=[0,20000],unit="THz")
    start=time.perf_counter();r=repair_frequencies(payload,"phonon_dos","test")[0];elapsed=time.perf_counter()-start
    assert r["new_point_count"]>0 and elapsed<5
    assert all(len(o["detail"])<=4000 for o in doc["operations"])
    print(f"20000点受限修正: {elapsed:.4f}s")


def test_undo_intent_blocks_immediate_repair():
    payload=data();doc=payload["manual_documents"]["a"]
    doc["operations"].append(dict(kind="undo-frequency-repair",at="test",detail=json.dumps({"batch_id":"test"})))
    before=copy.deepcopy(payload)
    assert repair_frequencies(payload,"phonon_dos","test")[0]["new_point_count"]==0
    assert payload==before


def test_exact_join_duplicates_stay_coincident_and_zero_does_not_move():
    payload=data()
    p=payload["curves"][0]["points"];dp=payload["manual_documents"]["a"]["curves"][0]["points"]
    clone=copy.deepcopy(p[1]);clone.update(id="dup",breakBefore=True)
    doc_clone=copy.deepcopy(dp[1]);doc_clone.update(id="dup",breakBefore=True)
    p[1]["joinTo"]="dup";dp[1]["joinTo"]="dup"
    p.insert(2,clone);dp.insert(2,doc_clone)
    report=repair_frequencies(payload,"phonon_dos","test")[0]
    assert report["new_point_count"]==3
    assert p[1]["frequency_pixel"]==p[2]["frequency_pixel"]
    assert dp[1]["x"]==dp[2]["x"]
    assert connected_samples(payload["curves"][0])[0][0]==0


@pytest.mark.parametrize("limit",["operations","bytes"])
def test_history_limit_does_not_partially_mutate(limit):
    payload=data();doc=payload["manual_documents"]["a"]
    if limit=="operations":doc["operations"]=[dict(kind="move",at="test",detail="")] * 5000
    else:doc["description"]="x"*4_000_000
    before=copy.deepcopy(payload)
    assert repair_frequencies(payload,"phonon_dos","test")[0]["new_point_count"]==0
    assert payload==before


def test_adjacent_repair_blocks_have_no_new_boundary_backtracks():
    payload=data((0,3,2.8,3.4,3.2,10))
    r=repair_frequencies(payload,"phonon_dos","test")[0]
    assert r["new_block_count"]==2
    f,_=connected_samples(payload["curves"][0])
    assert all(b>a for a,b in zip(f,f[1:]))


from sqlalchemy.orm import Session
from backend import models
from backend.tests.test_spectra_manual import manual_storage, manual_http
from backend.tests.test_spectra_recalculate import recalc_body


def test_http_repair_editor_export_history_undo_and_repeat(manual_http):
    import csv, io
    from backend.api.spectra import csv_export
    e=manual_http;client=e["client"];url=f"/api/rag/spectra/{e['identity']}"
    body=copy.deepcopy(e["body"]);doc=body["document"]
    points=doc["curves"][0]["points"]
    points[50]["x"]=70.4;points[51]["x"]=70.2
    doc["zero"]={"pixel":20,"pointIds":[points[0]["id"]]}
    doc["operations"].append(dict(kind="move",at="test",detail="人工频率微调"))
    response=client.post(url+"/manual",json=body);assert response.status_code==200,response.text
    saved=response.json()["items"][0];original=copy.deepcopy(saved["result"])
    response=client.post(url+"/recalculate",json=recalc_body(e,saved));assert response.status_code==200,response.text
    item=response.json()["items"][0];result=item["result"];curve=result["curves"][0]
    assert result["quality"]["frequency_repairs"]["alpha2f"][0]["new_point_count"]==2
    assert result["quality"]["integrals"]["raw"]["parameters"]["omega_log"]["status"]=="available"
    assert [p["amplitude_pixel"] for p in curve["points"]]==[p["amplitude_pixel"] for p in original["curves"][0]["points"]]
    with Session(e["engine"]) as session:
        assert session.get(models.SpectrumRun,saved["run"]["id"]).result_json==original
    assert client.post(url+"/recalculate",json=recalc_body(e,saved)).status_code==409
    params={**e["query"],"kind":"alpha2f","collection_version":item["version"],"run_id":item["run"]["id"]}
    editor=client.get(url+"/manual",params=params).json()["documents"][0]
    for p,dp in zip(curve["points"],editor["curves"][0]["points"]):
        assert p["frequency_pixel"]==dp["x"]
    rows=list(csv.DictReader(io.StringIO(csv_export(item))))
    assert float(rows[50]["frequency_pixel"])==curve["points"][50]["frequency_pixel"]
    response=client.post(url+"/recalculate",json=recalc_body(e,item));assert response.status_code==200,response.text
    repeated=response.json()["items"][0]
    assert repeated["result"]["curves"]==result["curves"]
    assert repeated["result"]["quality"]["frequency_repairs"]["alpha2f"][0]["new_point_count"]==0
    assert repeated["result"]["quality"]["frequency_repairs"]["alpha2f"][0]["point_count"]==2

    batch=json.loads(editor["operations"][-1]["detail"])
    for key,before,after in batch["changes"]:
        dp=next(p for p in editor["curves"][0]["points"] if p["id"]==key)
        assert dp["x"]==after;dp["x"]=before;dp["status"]="撤销自动频率微调"
    editor["operations"].append(dict(kind="undo-frequency-repair",at="test",detail=json.dumps({"batch_id":batch["batch_id"]})))
    response=client.post(url+"/manual",json={**body,"expected_collection_version":repeated["version"],"base_run_id":repeated["run"]["id"],"document":editor})
    assert response.status_code==200,response.text
    undone=response.json()["items"][0]
    response=client.post(url+"/recalculate",json=recalc_body(e,undone));assert response.status_code==200,response.text
    final=response.json()["items"][0]
    assert final["result"]["curves"][0]["points"][50]["frequency_pixel"]==70.4
    assert final["result"]["quality"]["frequency_repairs"]["alpha2f"][0]["new_point_count"]==0
    assert final["result"]["quality"]["integrals"]["raw"]["status"]=="unavailable"
    assert any(i["kind"]=="frequency_backtrack" for i in final["result"]["quality"]["trace_diagnostics"]["alpha2f"]["curves"][0]["issues"])


def test_public_internal_report_is_removed():
    from backend.services.spectra import mask_public
    from backend.tests.test_spectra_recalculate import alpha_payload
    payload=alpha_payload();payload.update(quality={"frequency_repairs":{"alpha2f":[{"private":123}]}},candidates={})
    assert "frequency_repairs" not in mask_public(payload,{"a":{"status":"accepted"}})["quality"]


def test_randomized_blocks_preserve_valid_boundaries_and_all_bounds():
    import random
    rng=random.Random(166)
    for _ in range(80):
        values=[0]+[i*.2+rng.uniform(-.4,.4) for i in range(4,70)]+[20]
        payload=data(values)
        payload["manual_documents"]["a"]["source"]["plot"]=[0,0,20,100]
        before=copy.deepcopy(payload)
        repair_frequencies(payload,"phonon_dos","test")
        current=[p["frequency_thz"] for p in payload["curves"][0]["points"]]
        changed={i for i,(a,b) in enumerate(zip(values,current)) if a!=b}
        assert current[0]==values[0] and current[-1]==values[-1]
        assert all(abs(a-b)<=.5 for a,b in zip(values,current))
        for i,(a,b) in enumerate(zip(values,values[1:])):
            if b>a or i in changed or i+1 in changed:
                assert current[i+1]>current[i]
        assert [p["reconstructed_amplitude"] for p in payload["curves"][0]["points"]]==[
            p["reconstructed_amplitude"] for p in before["curves"][0]["points"]]


@pytest.mark.parametrize("direction",["x","y"])
def test_locked_endpoint_preserved_exactly_when_previous_point_is_repaired(direction):
    payload=data((0,5.123456789+.2,5.123456789),direction=direction)
    before=copy.deepcopy(payload)
    r=repair_frequencies(payload,"phonon_dos","test")[0]
    assert r["new_point_count"]==1
    for key in ("frequency_pixel","frequency_thz"):
        assert payload["curves"][0]["points"][-1][key]==before["curves"][0]["points"][-1][key]


@pytest.mark.parametrize("pair",[(145.900448,146.368578),(142.838537,142.857483),(116.317469,117.),(113.,113.070219)])
def test_readable_screenshot_pairs_as_independent_geometric_cases(pair):
    # 只复用截图的原图y差值；不是实际业务曲线或全部12段的复现。
    extent=450
    payload=data((0,extent-pair[0],extent-pair[1],extent))
    curve=payload["curves"][0];doc=payload["manual_documents"]["a"]
    curve["frequency_direction"]="y"
    curve["axis_calibration"]["frequency"]=dict(slope=-1,intercept=extent)
    doc["source"]["plot"]=[0,0,700,extent]
    doc["calibration"]=dict(direction="y",frequency=dict(pixels=[extent,0],values=[0,extent],unit="THz"))
    doc["zero"]["pixel"]=extent
    for p,dp in zip(curve["points"],doc["curves"][0]["points"]):
        p["frequency_pixel"]=extent-p["frequency_thz"]
        dp.update(x=p["amplitude_pixel"],y=p["frequency_pixel"])
    r=repair_frequencies(payload,"phonon_dos","test")[0]
    assert r["new_point_count"]==2 and r["max_shift_px"]<=.5
    f,_=connected_samples(curve)
    assert all(b>a for a,b in zip(f,f[1:]))
