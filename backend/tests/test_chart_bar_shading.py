"""真实柱内亮度波动不能把网格线误当柱顶；保留原AI坐标和科学来源。"""
from pathlib import Path
import json
from PIL import Image, ImageDraw
import pytest
from backend.ingest.chart_reading import calibrate_panel
from backend.ingest.chart_calibration import bar_edge

ROOT = Path(__file__).parent / "fixtures/chart_bar_shading"


def test_real_yh10_blue_bar_is_not_cut_at_internal_200k_line():
    answer = json.loads((ROOT / "failed-response.json").read_text())
    panel = next(p for p in answer["panels"] if p["quantity"] == "tc")
    source = json.loads((ROOT / "source.json").read_text())
    image = Image.open(ROOT / "failed-crop.png")
    readings, missing = calibrate_panel(panel, image, {**source["document"], "page": 4}, source["crop_bbox"])
    point = next(v for v in readings if v["point"]["material"] == "YH10" and v["point"]["mu_star"] == .13)
    assert point["point"]["y"] == 269  # 故障原响应字节未修饰。
    assert 280 <= point["value_number"] <= 300, point
    assert abs(point["snapped_y"] - point["initial_model_y"]) < 10
    assert len(readings) == 18 and len(missing) == 2


@pytest.mark.parametrize("color", [(0,0,128), (0,128,0), (128,0,0)])
def test_same_hue_bright_pixel_above_dark_grid_does_not_break_bar(color):
    image = Image.new("RGB", (100, 100), "white"); draw = ImageDraw.Draw(image)
    draw.rectangle((30, 25, 40, 90), fill=color)
    brighter = tuple(round(v * 1.04) for v in color)
    draw.line((30, 49, 40, 49), fill=brighter)
    draw.line((30, 50, 40, 50), fill=tuple(v // 3 for v in color))
    y, _ = bar_edge(image, {"x":350, "y":250, "pixel_error":5},
        {"ticks":[{"position":100,"value":200},{"position":900,"value":0}],"bounds":[100,900]})
    assert y == pytest.approx(250, abs=12)


def test_real_white_gap_does_not_connect_same_color_objects():
    image = Image.new("RGB", (100,100), "white"); draw=ImageDraw.Draw(image)
    draw.rectangle((30,15,40,35),fill=(0,0,128))
    draw.rectangle((30,50,40,90),fill=(0,0,128))
    y, _ = bar_edge(image, {"x":350,"y":500,"pixel_error":5},
        {"ticks":[{"position":100,"value":200},{"position":900,"value":0}],"bounds":[100,900]})
    assert y > 480


def test_previous_wrong_completed_result_is_not_reused_and_new_request_has_version(tmp_path):
    from backend.tests.test_chart_reading import original, fake_model
    from backend.ingest.chart_reading import enrich_document, VERSION
    path, ir, source = original(tmp_path); calls=[]
    ir.coverage["chart_reading"]={"version":"scientific-chart-reading-v6","status":"completed","readings":0}
    report=enrich_document(ir,path,source,fake_model(calls))
    assert report["readings"]==2 and len(calls)==2
    assert calls[-1]["reader_version"]==VERSION
