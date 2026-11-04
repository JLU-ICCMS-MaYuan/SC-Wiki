"""#164 浏览器专用：复用正式路由与隔离 SQLite，不连接业务库。"""
import copy
import os
from pathlib import Path

assert Path(os.environ["FILE_STORAGE_LOCAL_ROOT"]).resolve().is_relative_to(Path(os.environ["SCWIKI_MANUAL_TEST_ROOT"]).resolve())
assert os.environ["FILE_STORAGE_BACKEND"] == "local"
import io
from ase import Atoms
from ase.io import write
from PIL import Image, ImageDraw
from backend.tests import manual_editor_server as base
from backend.tests.test_spectra_dos_relative import payload
from backend import models
from backend.services import spectra as service
from backend.spectra.context import primitive_for
from sqlalchemy.orm import Session

app = base.app
buffer = io.BytesIO()
write(buffer, Atoms("LaH2", scaled_positions=[[.1,.2,.3],[.32,.47,.19],[.76,.63,.87]],
                    cell=[4.,5.,6.], pbc=True), format="cif")
base.states[0].update(material="LaH2", structure=dict(structure_format="cif",structure_text=buffer.getvalue().decode()))
base.states.append(dict(state_key="dos-no-n",material="LaH2",pressure_value_gpa=210,property_modules=[]))
base.states.append({**copy.deepcopy(base.states[0]),"state_key":"dos-total","pressure_value_gpa":220})

with Session(base.engine) as session:
    ctx = service.context(session,"upload",base.task,base.owner,write=True)
    assert primitive_for(ctx["states"][0],ctx["draft"])["primitive_atoms"] == 3
    original = session.get(models.SpectrumCollection,base.identities["phonon_dos"])
    source = copy.deepcopy(original.source_json)
    image = Image.new("RGB",(160,100),"white");draw=ImageDraw.Draw(image)
    draw.rectangle((20,20,140,80),outline="gray")
    data = payload()
    for curve in data["curves"]:
        curve["axis_calibration"]["frequency"] = dict(slope=1/120,intercept=-20/120)
        curve["axis_calibration"]["amplitude"] = dict(slope=-1.,intercept=80.)
        curve.update(roi=[20,20,140,80],color="blue" if curve["id"]=="La" else "green",source_frequency_unit="THz")
        for point in curve["points"]:
            point["frequency_pixel"]=20+120*point["frequency_thz"]
            point["reconstructed_amplitude"]*=4
            point["amplitude_pixel"]=80-point["reconstructed_amplitude"]
            point["observed_amplitude"]=point["reconstructed_amplitude"]
            point["status"]="observed"
        draw.line([(p["frequency_pixel"],p["amplitude_pixel"]) for p in curve["points"]],
                  fill="blue" if curve["id"]=="La" else "green",width=2)
    for c in data["calibration"]["curves"]:
        c.update(kind="phonon_dos",roi=[20,20,140,80],frequency_ticks=[[20,0],[140,1]],
                 amplitude_ticks=[[80,0],[20,60]],unit="pixel",color="blue",frequency_direction="x")
    data["calibration"].update(panel_id="dos-relative",state_key="s1")
    image_buffer=io.BytesIO();image.save(image_buffer,format="PNG");image_buffer.seek(0)
    source["image"]=base.asdict(base.create_storage().put("spectra/dos-relative.png",image_buffer,"image/png"))
    original.source_json=source
    for index,state in enumerate(ctx["states"]):
        row=original if index==0 else service.collection(session,ctx,state["state_key"],state["state_key"],source)
        result=copy.deepcopy(data)
        cal=copy.deepcopy(data["calibration"]);cal["state_key"]=state["state_key"]
        if state["state_key"]=="dos-total":
            result["curves"]=result["curves"][:1]
            result["curves"][0]["projection"]="total"
            cal["curves"]=cal["curves"][:1]
            cal["curves"][0]["projection"]="total"
            cal.update(projection_complete=False,projection_scale_confirmed=False)
        run,_=service.new_run(session,row,cal,state)
        result["calibration"]=cal
        service.complete_run(run,result);service.activate(row,run,state)
    session.commit()


# 可选真实来源夹具只从隔离根读取；没有业务写入或模型调用入口。
if os.environ.get("SCWIKI_TDOS_SOURCE_FIXTURE"):
    import json
    fixture_path=Path(os.environ["SCWIKI_TDOS_SOURCE_FIXTURE"]).resolve()
    assert fixture_path.is_relative_to(Path(os.environ["SCWIKI_MANUAL_TEST_ROOT"]).resolve())
    bundle=json.loads(fixture_path.read_text())
    original_get_state=base.upload_tasks.get_state
    def source_state(identity):
        task_state=original_get_state(identity)
        if task_state:
            task_state["files"].append(dict(file_id="real-supplementary",kind="pdf",role="supplementary",sha256=bundle["source"]["source_sha256"]))
        return task_state
    base.upload_tasks.get_state=source_state
    real_state=copy.deepcopy(bundle["state"])
    real_state["state_key"]="dos-real-source"
    base.states.append(real_state)
    result=copy.deepcopy(bundle["result"])
    result["calibration"]["state_key"]=real_state["state_key"]
    with Session(base.engine) as session:
        ctx=service.context(session,"upload",base.task,base.owner,write=True)
        image_path=fixture_path.parent/"source.png"
        content=io.BytesIO(image_path.read_bytes())
        source={**bundle["source"],"image":base.asdict(base.create_storage().put("spectra/tdos-real-source.png",content,"image/png"))}
        row=service.collection(session,ctx,"tdos-real-source","tdos-real-source",source)
        current_state=next(s for s in ctx["states"] if s["state_key"]==real_state["state_key"])
        run,_=service.new_run(session,row,result["calibration"],current_state)
        service.complete_run(run,result);service.activate(row,run,current_state)
        session.commit()
