"""#167 浏览器隔离夹具：正频起点α²F及有结构依据的DOS，无人工zero状态。"""
import io
import copy
import os
from pathlib import Path
assert os.environ["FILE_STORAGE_BACKEND"]=="local"
assert Path(os.environ["FILE_STORAGE_LOCAL_ROOT"]).resolve().is_relative_to(Path(os.environ["SCWIKI_MANUAL_TEST_ROOT"]).resolve())
from backend.tests import manual_editor_server as base
from backend.tests.test_spectra import fixture
from backend.tests.test_spectra_dos_relative import payload
from backend.spectra.engine import extract_panel
from backend.spectra.context import references_for
from backend.services import spectra as service
from backend import models
from sqlalchemy.orm import Session
from ase import Atoms
from ase.io import write
from PIL import Image,ImageDraw

app=base.app
buffer=io.BytesIO()
write(buffer,Atoms("LaH2",scaled_positions=[[.1,.2,.3],[.32,.47,.19],[.76,.63,.87]],cell=[4,5,6],pbc=True),format="cif")
base.states.append(dict(state_key="dos-positive",material="LaH2",pressure_value_gpa=210,
                       structure=dict(structure_format="cif",structure_text=buffer.getvalue().decode()),property_modules=[]))
with Session(base.engine) as session:
    ctx=service.context(session,"upload",base.task,base.owner,write=True)
    state=ctx["states"][0]
    row=session.get(models.SpectrumCollection,base.identities["alpha2f"])
    rgb,cal=fixture();cal["curves"][0]["roi"][0]=24
    # 不含0的可见刻度，实际ROI从0.2 THz开始。
    cal["curves"][0]["frequency_ticks"]=[[40,1],[80,3],[140,6]]
    run,_=service.new_run(session,row,cal,state)
    service.complete_run(run,extract_panel(rgb,cal,references=references_for(state)))
    service.activate(row,run,state)

    state=ctx["states"][-1];row=session.get(models.SpectrumCollection,base.identities["phonon_dos"])
    data=payload()
    image=Image.new("RGB",(160,100),"white");draw=ImageDraw.Draw(image)
    draw.rectangle((20,10,140,80),outline="gray")
    for c in data["curves"]:
        c.update(roi=[20,10,140,80],source_frequency_unit="THz",frequency_direction="x",color="blue" if c["id"]=="La" else "green")
        c["axis_calibration"]={"frequency":dict(slope=.01,intercept=0.),"amplitude":dict(slope=-1.,intercept=80.)}
        for p in c["points"]:
            f=p["frequency_thz"]+.2;p.update(frequency_thz=f,frequency_pixel=f*100,amplitude_pixel=80-p["reconstructed_amplitude"],observed_amplitude=p["reconstructed_amplitude"],status="observed")
        draw.line([(p["frequency_pixel"],p["amplitude_pixel"]) for p in c["points"]],fill=c["color"],width=2)
    for c in data["calibration"]["curves"]:
        c.update(kind="phonon_dos",roi=[20,10,140,80],frequency_direction="x",frequency_ticks=[[20,.2],[140,1.4]],amplitude_ticks=[[80,0],[10,70]],unit="pixel",color="green")
    data["calibration"].update(panel_id="dos-positive",state_key=state["state_key"])
    content=io.BytesIO();image.save(content,format="PNG");content.seek(0)
    source=copy.deepcopy(row.source_json);source["image"]=base.asdict(base.create_storage().put("spectra/positive-dos.png",content,"image/png"));row.source_json=source
    run,_=service.new_run(session,row,data["calibration"],state)
    service.complete_run(run,data);service.activate(row,run,state)
    session.commit()
