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
        row=original if index==0 else service.collection(session,ctx,"dos-no-n","dos-no-n",source)
        cal=copy.deepcopy(data["calibration"]);cal["state_key"]=state["state_key"]
        run,_=service.new_run(session,row,cal,state)
        result=copy.deepcopy(data);result["calibration"]=cal
        service.complete_run(run,result);service.activate(row,run,state)
    session.commit()
