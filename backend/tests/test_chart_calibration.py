"""#227：有已知真值的图像标定，覆盖变换、精度与缺失保护。"""
import math
import pytest
from PIL import Image, ImageDraw

from backend.ingest.chart_calibration import coordinate_value, approximate, heatmap_position, bar_edge, ChartReadingError


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
