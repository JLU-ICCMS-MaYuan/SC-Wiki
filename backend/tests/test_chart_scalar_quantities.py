from copy import deepcopy

from PIL import Image
import pytest

from backend.ingest.chart_reading import calibrate_panel
from backend.tests.test_chart_reading import panel


@pytest.mark.parametrize('quantity,unit,value', [('tc', 'K', 100), ('lambda_ep', '1', 2),
                                               ('omega_log', 'K', 800), ('dos_fermi', 'states/eV/f.u.', 3)])
def test_four_explicit_scalar_labels_keep_quantity_and_units(quantity, unit, value):
    chart = panel(); chart.update(quantity=quantity, unit=unit)
    chart['series'] = ['blue']; chart['points'] = [chart['points'][0]]
    chart['points'][0].update(reading='label', label_value=value, label_text=str(value))
    values, missing = calibrate_panel(chart, Image.new('RGB', (200, 200)),
        {'file_id': 'si', 'sha256': 'f' * 64, 'page': 2}, [0, 0, 200, 200])
    assert not missing and len(values) == 1
    assert values[0]['quantity'] == quantity and values[0]['unit'] == unit
    assert values[0]['value_number'] == value and values[0]['precision_kind'] == 'reported_label'


@pytest.mark.parametrize('bounds', [[0, 1000], [1000, 0]])
def test_dos_curve_requires_fermi_energy_calibration_and_rejects_other_energy(bounds):
    chart = panel('line'); chart.update(quantity='dos_fermi', unit='states/eV', layout='sparse')
    chart['series'] = ['blue']; chart['points'] = [chart['points'][0]]
    source = {'file_id': 'si', 'sha256': 'f' * 64, 'page': 2}
    image = Image.new('RGB', (200, 200), 'white')
    assert not calibrate_panel(chart, image, source, [0, 0, 200, 200])[0]
    chart.update(x_axis={'scale': 'linear', 'bounds': bounds, 'ticks': [
        {'position': 0, 'value': -10}, {'position': 1000, 'value': 10}]}, x_quantity='energy', x_unit='eV')
    chart['points'][0]['x'] = 500
    assert len(calibrate_panel(chart, image, source, [0, 0, 200, 200])[0]) == 1
    chart['points'][0]['x'] = 800
    assert not calibrate_panel(chart, image, source, [0, 0, 200, 200])[0]
