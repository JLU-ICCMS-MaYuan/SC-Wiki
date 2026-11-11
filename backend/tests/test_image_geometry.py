"""像素候选只描述几何，不能决定科学标签；缩放及图例保留可核验。"""
from PIL import Image,ImageDraw
import pytest
from backend.ingest.image_geometry import geometry_observations


def test_multiple_narrow_colored_plot_frames_are_measured_without_scientific_labels():
    image=Image.new('RGB',(1000,1000),'white');draw=ImageDraw.Draw(image)
    for left,right in [(50,600),(620,780),(800,960)]:
        for top,bottom in [(50,450),(530,950)]:
            draw.rectangle((left,top,right,bottom),outline='blue' if left==800 else 'black',width=3)
    before=image.tobytes();result=geometry_observations(image)
    assert len(result['panel_frames']) == 6
    assert image.tobytes()==before


def fixture(scale=1):
    im=Image.new("RGB",(320,500),"white");d=ImageDraw.Draw(im)
    for y in [20,160,300,450]:d.line((60,y,300,y),fill="black",width=2)
    d.line((60,20,60,450),fill="black",width=2);d.line((300,20,300,450),fill="black",width=2)
    for y in [70,115,205,250,350,400]:d.line((52,y,60,y),fill="black",width=2)
    for box,c in [((85,80,105,157),"red"),((140,50,160,157),"red"),
                  ((85,220,105,297),"blue"),((140,180,160,297),"blue"),
                  ((85,380,94,447),"lime"),((96,390,105,447),(0,0,128)),
                  ((220,330,245,345),"lime")]:
        d.rectangle(box,fill=c)
    return im if scale==1 else im.resize((320*scale,500*scale),Image.Resampling.NEAREST)


def test_geometry_preserves_pixels_and_offers_frames_ticks_and_neutral_ink():
    im=fixture();before=im.tobytes();result=geometry_observations(im)
    assert im.tobytes()==before and len(result["band_candidates"])==3
    assert result["spines"] and len(result["spines"][0]["tick_candidates"])>=6
    assert len(result["rectangles"])>=7  # 图例色块仍是无标签候选，不能自动当作材料结果。
    def keys(value):
        if isinstance(value,dict):
            return set(value)|set().union(*(keys(v) for v in value.values()))
        if isinstance(value,list):return set().union(*(keys(v) for v in value),set())
        return set()
    assert not keys(result)&{"material","quantity","value_number","mu_star","pressure_value_gpa"}
    assert result["role"]=="unlabelled_geometry_candidates_not_scientific_results"


def test_geometry_positions_do_not_depend_on_raster_scale():
    a=geometry_observations(fixture());b=geometry_observations(fixture(2))
    assert len(a["band_candidates"])==len(b["band_candidates"])==3
    for x,y in zip(a["band_candidates"],b["band_candidates"]):
        assert x["bbox"]==pytest.approx(y["bbox"],abs=1000/319)


def test_grayscale_or_missing_candidates_are_not_claimed_to_be_absent_data():
    result=geometry_observations(Image.new("RGB",(200,200),"white"))
    assert result["rectangles"]==[] and result["limitations"]
