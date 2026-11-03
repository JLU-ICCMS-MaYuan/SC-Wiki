"""#211：数值标定失败不能丢失已识别的目标类型和材料状态。"""
import io
from PIL import Image
from backend.spectra.discovery import calibrate

def test_invalid_axis_retains_target_identity_without_adopting_bad_curve():
    buffer=io.BytesIO()
    Image.new("RGB",(100,100),"white").save(buffer,format="PNG")
    image=dict(size_px=[100,100],text="CaH6 phonon DOS at 150 GPa",image=buffer.getvalue())
    raw=dict(panel_id="S15-150",kind="phonon_dos",state_key="150",caption="150 GPa",curves=[
        dict(id="dos",kind="phonon_dos",color="black",roi=[10,10,90,90],frequency_direction="x",
             frequency_ticks=[[10,0],[90,0]],amplitude_ticks=[[90,0],[10,1]],unit="pixel")])
    panels,issues=calibrate(image,[dict(state_key="150")],complete=lambda *a,**k:dict(panels=[raw],issues=[]))
    assert len(panels)==1
    assert panels[0]["state_key"]=="150" and panels[0]["kind"]=="phonon_dos"
    assert panels[0]["curves"]==[]
    assert any("校验" in issue for issue in issues)
