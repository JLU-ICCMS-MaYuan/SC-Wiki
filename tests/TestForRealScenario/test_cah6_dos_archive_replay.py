"""真实CaH6失败响应的最小独立状态重放，不调用模型或业务库。"""
from copy import deepcopy
import json
from pathlib import Path

from backend.ingest.scientific_form_filling import apply_plan, validate_filling_coverage


def test_real_dos_response_keeps_server_archive_and_all_original_sources():
    fixture = json.loads((Path(__file__).parent / 'fixtures/cah6-dos-archive-failed.json').read_text())
    original = deepcopy(fixture['states'])
    assert '未登记科学字段：dos_fermi_sources' in fixture['original_error']
    values, audit = apply_plan(original, fixture['sources'], fixture['response'],
                               state_offset=fixture['state_offset'])
    record = values[0]['property_modules'][0]['records'][0]
    assert values[0]['material'] == 'CaH4' and values[0]['pressure_value_gpa'] == 50
    assert record['value_number'] == .02234 and record['canonical_unit'] == 'states/eV/f.u.'
    assert record['payload']['dos_fermi_sources'] == original[0]['property_modules'][0]['records'][0]['payload']['dos_fermi_sources']
    assert original == fixture['states']
    validate_filling_coverage(original, values, audit, state_offset=fixture['state_offset'])
