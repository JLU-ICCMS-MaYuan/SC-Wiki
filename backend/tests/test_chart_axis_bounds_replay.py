"""#227：固定重放Peng2017图4两轮真实反序边界响应，不调用模型。"""
from copy import deepcopy
import json
from pathlib import Path

from PIL import Image
import pytest

from backend.ingest.chart_reading import calibrate_panel, append_readings, reading_schema
from backend.ingest.document_ir import DocumentIR, PageGeometry
from backend.rag.structured_output import validate_output


FIXTURES = Path(__file__).parent / 'fixtures' / 'chart_axis_bounds'
SOURCE = {'file_id': 'peng2017-main',
    'sha256': 'bf0725bea058339b814489fe213ec8285a0fca01eb5143da95254330eea06846', 'page': 4}


@pytest.mark.parametrize('filename', ['gpt-tc-response.json', 'gpt-tc-repeat1-response.json'])
def test_real_reversed_axis_keeps_values_conditions_and_original_response(filename):
    answer = json.loads((FIXTURES / filename).read_text())
    validate_output(answer, reading_schema())
    before = deepcopy(answer)
    panel = answer['panels'][0]
    assert panel['axis']['bounds'] == [795, 0]
    readings, unresolved = calibrate_panel(panel, Image.open(FIXTURES / 'panel-tc.png'),
        SOURCE, [0, 393, 879, 632])
    assert answer == before
    assert len(readings) == 18
    assert len(unresolved) == 2 and {v['category'] for v in unresolved} == {'PrH9'}
    assert {(r['point']['material'], r['point']['mu_star']) for r in readings} == {
        (material, mu) for material in panel['categories'] if material != 'PrH9' for mu in [0.1, 0.13]}
    for reading in readings:
        assert reading['axis']['bounds'] == [795, 0]
        assert reading['calibrated_axis']['bounds'] == [0, 795]
        assert reading['source_sha256'] == SOURCE['sha256']
        assert reading['reading_precision'] > 0 and reading['value_raw'].startswith('~')
    sc = {r['point']['mu_star']: r for r in readings if r['point']['material'] == 'ScH6'}
    assert sc[0.1]['value_number'] == 99
    assert sc[0.13]['value_number'] == 85
    assert all(r['point']['pressure_value_gpa'] == 300 for r in sc.values())
    ir = DocumentIR(document_id='axis-replay', source_file_id=SOURCE['file_id'],
        source_sha256=SOURCE['sha256'], parse_profile='complementary',
        pages=[PageGeometry(pdf_page=4, width=879, height=632)])
    append_readings(ir, readings)
    restored = DocumentIR.model_validate_json(ir.model_dump_json())
    assert [b.metadata['chart_reading'] for b in restored.blocks] == readings
    assert all('graph localization, NOT physical measurement error' in b.text for b in restored.blocks)
