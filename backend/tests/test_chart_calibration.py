"""#227：有已知真值的图像标定，覆盖变换、精度与缺失保护。"""
import math
import pytest
from PIL import Image, ImageDraw

from backend.ingest.chart_calibration import coordinate_value, approximate, heatmap_position, bar_edge, ChartReadingError


def test_real_s14_wrong_energy_labels_cannot_hide_in_fitted_reading_precision():
    import json
    from pathlib import Path
    failure = json.loads((Path(__file__).parent/'fixtures/native-tool-extra-closer.json').read_text())
    raw = json.loads(failure['partial_response'])['tool_calls'][0]['arguments']
    answer, _ = json.JSONDecoder().raw_decode(raw)
    axis = answer['panels'][0]['x_axis']
    with pytest.raises(ChartReadingError) as error:
        coordinate_value(axis, 679.3, pixel_error=6)
    assert error.value.details['reason_code'] == 'TICK_CALIBRATION_INCONSISTENT'


def test_ticks_within_declared_localization_band_remain_calibratable():
    axis = {'scale': 'linear', 'bounds': [100, 500], 'ticks': [
        {'position': x, 'value': y} for x, y in zip([100, 202, 298, 402, 500], range(5))]}
    value, precision, _ = coordinate_value(axis, 300, pixel_error=2)
    assert abs(value - 2) < .1 and precision > 0


def test_real_horizontal_labels_reject_self_consistent_wrong_positions():
    from pathlib import Path
    from PIL import Image
    from backend.ingest.chart_calibration import verify_horizontal_tick_labels
    image = Image.open(Path(__file__).parent/'fixtures/s14-original-energy-axis.png')
    axis = {'scale': 'linear', 'bounds': [144.6, 942.5], 'ticks': [
        {'position': x, 'value': y} for x, y in zip([144.6,244.1,343.5,443,542.5,642,741.5], [-20,-15,-10,-5,0,5,10])]}
    with pytest.raises(ChartReadingError) as error:
        verify_horizontal_tick_labels(image, axis, localization_error=3)
    assert error.value.details['reason_code'] == 'HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED'
    assert axis['ticks'][4] == {'position': 542.5, 'value': 0}


def test_real_horizontal_printed_positions_are_accepted_without_changing_values():
    from pathlib import Path
    from PIL import Image
    from backend.ingest.chart_calibration import verify_horizontal_tick_labels
    image = Image.open(Path(__file__).parent/'fixtures/s14-original-energy-axis.png')
    axis = {'scale': 'linear', 'bounds': [149, 945], 'ticks': [
        {'position': x, 'value': y} for x,y in zip([150.1,282.3,414.5,546.7,678.9,811.1,943.3], [-20,-15,-10,-5,0,5,10])]}
    facts = verify_horizontal_tick_labels(image, axis, localization_error=3)
    assert facts['checked']
    assert [tick['value'] for tick in axis['ticks']] == [-20,-15,-10,-5,0,5,10]


def test_real_top_material_cannot_borrow_bottom_material_tick_positions():
    import json
    from pathlib import Path
    from PIL import Image
    from copy import deepcopy
    from backend.ingest.chart_reading import calibrate_panel
    root=Path(__file__).parent/'fixtures'
    record=json.loads((root/'s15-lambda-axis-scope.json').read_text())
    image=Image.open(root/'s15-lambda-columns.png')
    panel=deepcopy(record['actual_arguments']['panels'][0])
    width=record['original_size'][0];left=record['crop_pixels'][0]
    transform=lambda x:(x*width/1000-left)/image.width*1000
    panel['x_axis']['bounds']=[transform(x)for x in panel['x_axis']['bounds']]
    for tick in panel['x_axis']['ticks']:tick['position']=transform(tick['position'])
    for point in panel['points']:
        point['x']=transform(point['x']);point['pixel_error']*=width/image.width
    readings,issues=calibrate_panel(panel,image,{'file_id':'si','sha256':record['source_sha256'],'page':14},[0,0,100,100])
    assert not readings
    assert issues[0]['reason_code']=='HORIZONTAL_TICK_LABEL_POSITION_UNSUPPORTED'


@pytest.mark.parametrize('scale,ticks,expected', [
    ('linear', [{'position': 100, 'value': 200}, {'position': 900, 'value': 0}], 100),
    ('linear', [{'position': 100, 'value': 0}, {'position': 900, 'value': 200}], 100),
    ('log10', [{'position': 100, 'value': 100}, {'position': 900, 'value': 1}], 10),
])
def test_boundary_order_does_not_change_tick_value_direction(scale, ticks, expected):
    axis = {'scale': scale, 'ticks': ticks, 'bounds': [900, 100]}
    value, _, _ = coordinate_value(axis, 500)
    assert value == pytest.approx(expected)
    assert axis['bounds'] == [900, 100]


@pytest.mark.parametrize('bounds', [[900, 100], [100, 900]])
@pytest.mark.parametrize('position', [50, 950])
def test_boundary_order_does_not_allow_values_outside_the_axis(bounds, position):
    axis = {'scale': 'linear', 'bounds': bounds,
            'ticks': [{'position': 100, 'value': 200}, {'position': 900, 'value': 0}]}
    with pytest.raises(ChartReadingError):
        coordinate_value(axis, position)


@pytest.mark.parametrize('bounds', [[100, 100], [-1, 900], [1001, 100],
    [float('nan'), 900], [100, float('inf')], [], [100], [100, 500, 900], [200, 800]])
def test_invalid_axis_bounds_remain_rejected(bounds):
    axis = {'scale': 'linear', 'bounds': bounds,
            'ticks': [{'position': 100, 'value': 200}, {'position': 900, 'value': 0}]}
    with pytest.raises(ChartReadingError):
        coordinate_value(axis, 500)


@pytest.mark.parametrize('grid', ['black', (0, 60, 0), (140, 240, 140)])
@pytest.mark.parametrize('bounds', [[100, 900], [900, 100]])
def test_bar_pixel_edge_crosses_an_internal_grid_line(grid, bounds):
    image = Image.new('RGB', (100, 100), 'white'); draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 40, 90), fill=(0, 200, 0)); draw.line((20, 50, 90, 50), fill=grid, width=3)
    result = bar_edge(image, {'x': 350, 'y': 305, 'pixel_error': 10},
        {'ticks': [{'position': 100, 'value': 200}, {'position': 900, 'value': 0}], 'bounds': bounds})
    assert result[0] == pytest.approx(300, abs=12)


@pytest.mark.parametrize('ticks,position,expected', [
    ([{'position': 0, 'value': 0}, {'position': 100, 'value': 200}], 25, 50),
    ([{'position': 0, 'value': 300}, {'position': 300, 'value': 0}], 200, 100),
    ([{'position': 100, 'value': -10}, {'position': 200, 'value': 10}], 125, -5),
])
def test_linear_and_reversed_coordinates(ticks, position, expected):
    value, precision, _ = coordinate_value({'scale': 'linear', 'ticks': ticks}, position)
    assert value == pytest.approx(expected)
    assert precision > 0
    rounded, bound = approximate(value, precision)
    assert abs(rounded - expected) <= bound


def test_logarithmic_coordinate_uses_log_domain():
    value, precision, _ = coordinate_value({'scale': 'log10', 'ticks': [
        {'position': 0, 'value': 1}, {'position': 100, 'value': 100}]}, 50)
    assert value == pytest.approx(10)
    assert precision >= 10 ** 1.02 - 10


@pytest.mark.parametrize('axis,position', [
    ({'scale': 'linear', 'ticks': [{'position': 0, 'value': 1}]}, 0),
    ({'scale': 'linear', 'ticks': [{'position': 0, 'value': 1}, {'position': 0, 'value': 2}]}, 0),
    ({'scale': 'log10', 'ticks': [{'position': 0, 'value': -1}, {'position': 100, 'value': 2}]}, 40),
    ({'scale': 'linear', 'ticks': [{'position': 0, 'value': 1}, {'position': 100, 'value': 2}]}, 120),
])
def test_missing_invalid_or_extrapolated_axis_is_rejected(axis, position):
    with pytest.raises(ChartReadingError): coordinate_value(axis, position)


@pytest.mark.parametrize('bounds', [[125, 875], [875, 125]])
def test_heatmap_reads_actual_colorbar_pixels(bounds):
    image = Image.new('RGB', (400, 400), 'white')
    draw = ImageDraw.Draw(image)
    for y in range(50, 351):
        draw.line((300, y, 320, y), fill=(y - 50, 0, 350 - y))
    color = image.getpixel((310, 200)); draw.rectangle((50, 50, 150, 150), fill=color)
    pos, error, metadata = heatmap_position(image, (250, 250),
        {'bbox': [750, 125, 800, 875], 'orientation': 'vertical'})
    value, precision, _ = coordinate_value({'scale': 'linear', 'bounds': bounds, 'ticks': [
        {'position': 125, 'value': 300}, {'position': 875, 'value': 0}]}, pos, pixel_error=error)
    assert value == pytest.approx(150, abs=precision)
    assert metadata['color_distance'] == 0


def test_heatmap_color_not_in_palette_does_not_become_a_value():
    image = Image.new('RGB', (200, 200), 'white')
    draw = ImageDraw.Draw(image)
    for y in range(20, 181):draw.line((150, y, 160, y), fill=(y, 0, 0))
    with pytest.raises(ChartReadingError, match='颜色'):
        heatmap_position(image, (300, 300), {'bbox': [750, 100, 800, 900], 'orientation': 'vertical'})
