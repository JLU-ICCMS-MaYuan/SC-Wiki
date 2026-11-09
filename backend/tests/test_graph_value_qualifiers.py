"""约数限定贯穿当前值整理，不回填旧数值，不生成旧式同义参数。"""
from copy import deepcopy

from backend.ingest.property_modules import normalize_current_tc_value
from backend.ingest.scientific_contracts import normalize_parameters


def test_current_tc_keeps_matching_approximation_and_clears_stale_raw():
    record = {'record_type': 'predicted_tc', 'value_kind': 'number', 'value_number': 99,
              'value_raw': '~99 K', 'unit_raw': 'K'}
    assert normalize_current_tc_value(record)['value_raw'] == '~99'
    assert normalize_current_tc_value({**record, 'value_number': 100})['value_raw'] == '100'
    assert normalize_current_tc_value({**record, 'value_number': None})['value_raw'] == ''
    assert normalize_current_tc_value({**record, 'value_raw': '~99 mK'})['value_raw'] == '99'


def test_registered_parameter_quantity_survives_normalization_with_source():
    quantity = {'value_kind': 'number', 'value_number': 1.3, 'value_raw': '~1.3 dimensionless',
                'unit_raw': 'dimensionless', 'reported': True,
                'evidences': [{'file_id': 'main', 'pdf_page': 4, 'block_id': 'graph-point'}]}
    record = {'payload': {'parameters': {'lambda_ep': deepcopy(quantity), 'mu_star': .1}}}
    normalize_parameters(record)
    assert record['payload']['parameters']['lambda_ep'] == quantity
    assert 'extensions' not in record['payload']['parameters']
    before = deepcopy(record); normalize_parameters(record); assert record == before


def test_unknown_omega_unit_is_not_assumed_to_be_kelvin():
    record = {'payload': {'parameters': {'omega_log': {'value_kind': 'number', 'value_number': 1000,
        'value_raw': '~1000', 'unit_raw': None, 'reported': True}}}}
    normalize_parameters(record)
    parameters = record['payload']['parameters']
    assert 'omega_log' not in parameters
    assert parameters['extensions'][0]['unit_raw'] == 'unknown'
    assert parameters['extensions'][0]['reported'] is True


def test_qualifier_is_a_real_dependency_only_for_the_qualified_value():
    from backend.ingest.review_dependencies import record_inputs
    record = {'record_type': 'predicted_tc', 'value_kind': 'number', 'value_number': 99,
              'value_raw': '~99', 'unit_raw': 'K', 'payload': {'parameters': {}}}
    assert 'value_raw' in record_inputs(record, 'value_number')
    assert 'value_raw' not in record_inputs({**record, 'value_raw': '99'}, 'value_number')
    assert 'value_raw' not in record_inputs(record, 'payload.parameters.lambda_ep')
