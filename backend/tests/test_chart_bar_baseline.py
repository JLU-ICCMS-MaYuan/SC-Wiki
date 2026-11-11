"""零刻度必须与按零基线读取的柱端一致，不能用错误刻度输出伪零值。"""
import json
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from backend.ingest.chart_calibration import bar_edge, ChartReadingError
from backend.ingest.chart_reading import calibrate_panel

ROOT=Path(__file__).parent/'fixtures/chart_bar_baseline'


def test_wrong_zero_tick_on_an_internal_level_is_not_a_valid_bar_calibration():
    image=Image.new('RGB',(100,100),'white')
    ImageDraw.Draw(image).rectangle((30,30,40,90),fill=(0,200,0))
    with pytest.raises(ChartReadingError,match='基线'):
        bar_edge(image,{'x':350,'y':300,'pixel_error':2},
                 {'ticks':[{'position':100,'value':200},{'position':800,'value':0}],'bounds':[100,950]})


def test_real_flash_shifted_tc_is_rejected_without_moving_ticks_or_using_expected_values():
    answer=json.loads((ROOT/'failed-response.json').read_text())
    panel=next(x for x in answer['panels']if x['quantity']=='tc')
    before=json.dumps(panel,sort_keys=True)
    source=json.loads((ROOT/'source.json').read_text())
    found,missing=calibrate_panel(panel,Image.open(ROOT/'failed-crop.png'),
        {**source['document'],'page':4},source['crop_bbox'])
    assert not found
    # 完整链路可先检出无字刻度；下面仍直接验证错误零线必被基线检查拒绝。
    assert any('基线' in row['reason'] or row.get('reason_code') == 'TICK_LABEL_POSITION_UNSUPPORTED'
               for row in missing)
    with pytest.raises(ChartReadingError,match='基线'):
        bar_edge(Image.open(ROOT/'failed-crop.png'),panel['points'][0],panel['axis'])
    assert json.dumps(panel,sort_keys=True)==before


def test_real_dos_from_the_same_image_is_unchanged():
    answer=json.loads((ROOT/'failed-response.json').read_text())
    panel=next(x for x in answer['panels']if x['quantity']=='dos_fermi')
    source=json.loads((ROOT/'source.json').read_text())
    found,missing=calibrate_panel(panel,Image.open(ROOT/'failed-crop.png'),
        {**source['document'],'page':4},source['crop_bbox'])
    assert len(found)==10 and not missing
    assert all(x['value_number']>0 for x in found)


def test_reported_number_cannot_be_bound_to_an_unlabelled_minor_tick():
    answer=json.loads((ROOT/'minor-tick-response.json').read_text())
    panel=next(x for x in answer['panels']if x['quantity']=='tc')
    before=json.dumps(panel,sort_keys=True)
    source=json.loads((ROOT/'source.json').read_text())
    found,missing=calibrate_panel(panel,Image.open(ROOT/'failed-crop.png'),
        {**source['document'],'page':4},source['crop_bbox'])
    assert not found
    assert any('印刷' in row['reason']for row in missing)
    assert any(row.get('reason_code')=='TICK_LABEL_POSITION_UNSUPPORTED'for row in missing)
    assert json.dumps(panel,sort_keys=True)==before


def test_text_box_top_is_aligned_to_the_actual_tick_and_black_frame_is_not_a_zero_bar():
    panel=json.loads((ROOT/'text-corner-response.json').read_text())['panels'][0]
    source=json.loads((ROOT/'source.json').read_text())
    reference=json.loads((ROOT/'independent-reference.json').read_text())
    expected={(x['material'],x['mu_star']):x for x in reference['items']if x['quantity']=='tc'}
    found,missing=calibrate_panel(panel,Image.open(ROOT/'failed-crop.png'),
        {**source['document'],'page':4},source['crop_bbox'])
    assert len(found)==18 and len(missing)==2
    assert {x['category']for x in missing}=={'PrH9'}
    for item in found:
        target=expected[(item['point']['material'],item['point']['mu_star'])]
        assert abs(item['calculated_value']-target['value'])<=target['tolerance'],item['point']['material']
    assert all(item['value_number']>0 for item in found)


def test_real_s33_endpoint_label_and_all_sixteen_bars_are_preserved():
    saved=json.loads((ROOT/"s33-boundary-label-response.json").read_text())
    panel=saved["panel"];before=json.dumps(panel,sort_keys=True)
    found,missing=calibrate_panel(panel,Image.open(ROOT/"s33-boundary-label-crop.png"),
        {**saved["source"],"page":26},saved["crop_bbox"])
    assert len(found)==16 and not missing
    assert {x["point"]["material"] for x in found}==set(panel["categories"])
    assert all(x["point"]["pressure_value_gpa"]==200 for x in found)
    assert json.dumps(panel,sort_keys=True)==before


def test_inward_ticks_are_located_from_the_real_s33_spine_without_reusing_shifted_axis():
    from backend.ingest.chart_calibration import align_value_ticks
    saved=json.loads((ROOT/"s33-boundary-label-response.json").read_text())
    image=Image.open(ROOT/"s33-boundary-label-crop.png")
    axis,facts=align_value_ticks(image,saved["previous_axis"],localization_error=2,verify_label_positions=True)
    assert facts["ticks_aligned"]
    assert any(abs(a["position"]-b["position"])>2 for a,b in zip(axis["ticks"],saved["previous_axis"]["ticks"]))
    # 原位图0.040为27、0为502，三原像素容差；不从正文或模型值推轴。
    expected=(.04/(502-27))*(502-57)
    panel={**saved["panel"],"axis":saved["previous_axis"]}
    found,missing=calibrate_panel(panel,image,{**saved["source"],"page":26},saved["crop_bbox"])
    assert len(found)==16 and not missing
    pr=next(f for f in found if f["point"]["material"]=="PrH9")
    assert abs(pr["calculated_value"]-expected)<=.04/(502-27)*3
