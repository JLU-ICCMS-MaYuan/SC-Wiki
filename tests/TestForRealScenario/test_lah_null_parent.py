"""La-H真实堆栈回归：已登记字段自动补空不能向null父级直接写入。"""
from copy import deepcopy

import pytest


def test_candidate_projection_fills_null_software_group_without_changing_other_fields():
    from backend.ingest.field_candidates import patched_draft
    record = {'record_key': 'r', 'module_code': 'superconductive_properties',
        'record_type': 'predicted_tc', 'property_code': 'tc', 'name_raw': 'Tc',
        'value_kind': 'number', 'value_number': 274, 'value_raw': '274',
        'unit_raw': 'K', 'canonical_unit': 'K', 'method_code': 'unknown',
        'payload': {'parameters': {'mu_star': .13},
                    'calculation_conditions': {'qe': None, 'epw': None, 'sscha': None}}}
    draft = {'material_states': [{'state_key': 's', 'material': 'LaH10',
        'pressure_value_gpa': 210, 'property_modules': [{'module_key': 'm', 'records': [record]}]}]}
    before = deepcopy(draft)
    field = {'state_key': 's', 'module_key': 'm', 'record_key': 'r',
             'record_field': 'payload.calculation_conditions.qe.k_grid'}
    # 此数值仅为固定回归输入，不声称是La-H真实提取或科学验收。
    projected = patched_draft(draft, field, {'': '4 4 4'})
    result = projected['material_states'][0]['property_modules'][0]['records'][0]
    assert result['payload']['calculation_conditions']['qe'] == {'k_grid': '4 4 4'}
    assert result['payload']['calculation_conditions']['epw'] is None
    assert result['payload']['calculation_conditions']['sscha'] is None
    assert result['value_number'] == 274 and result['payload']['parameters'] == {'mu_star': .13}
    assert draft == before


@pytest.mark.parametrize('software', ['qe', 'epw', 'sscha'])
def test_registered_software_null_container_can_be_written(software):
    from backend.ingest.property_field_review import write_path
    value = {'payload': {'calculation_conditions': {software: None}}}
    write_path(value, f'payload.calculation_conditions.{software}.k_grid', '4 4 4')
    assert value['payload']['calculation_conditions'][software] == {'k_grid': '4 4 4'}


def test_nonempty_wrong_parent_type_is_not_overwritten():
    from backend.ingest.property_field_review import write_path
    value = {'payload': {'calculation_conditions': {'qe': 'invalid existing content'}}}
    before = deepcopy(value)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        write_path(value, 'payload.calculation_conditions.qe.k_grid', '4 4 4')
    assert value == before
