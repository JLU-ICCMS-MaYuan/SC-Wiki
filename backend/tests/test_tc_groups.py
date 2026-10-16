from copy import deepcopy

import pytest

from backend.ingest.tc_groups import tc_collection_issues, tc_record_issues
from backend.ingest.upload_contracts import convert_legacy_scientific_draft, UploadContractError


def point(key='a', method='isotropic_eliashberg', representative=False):
    return {'record_key': key, 'record_type': 'predicted_tc', 'property_code': 'tc', 'module_code': 'superconductive_properties',
            'method_code': method, 'definition_key': f'record.superconductive_properties.predicted_tc.{method}', 'definition_version': 1,
            'name_raw': 'Tc', 'value_kind': 'number', 'value_number': 311, 'value_raw': '311', 'canonical_unit': 'K',
            'is_representative': representative, 'payload': {'parameters': {'lambda_ep': 3.94, 'omega_log': 745, 'mu_star': .1},
            'calculation_conditions': {'k_grid': '24×24×24'},
            'tc_group': {'version': 1, 'group_key': 'g', 'method_key': method, 'point_key': key}}}


def test_many_methods_and_points_keep_independent_identity_and_one_representative():
    rows = [point('a'), point('b'), point('c', representative=True), point('d', 'allen_dynes')]
    assert not tc_collection_issues(rows, strict_representative=True)
    rows[-1]['is_representative'] = True
    assert tc_collection_issues(rows)[0][1] == 'duplicate_representative_tc'


@pytest.mark.parametrize('change,code', [
    (lambda r: r['payload']['tc_group'].update(version=True), 'invalid_tc_group'),
    (lambda r: r.update(value_kind='range'), 'invalid_tc_point'),
    (lambda r: r['payload']['parameters'].update(mu_star=None), 'incomplete_representative_tc'),
    (lambda r: r.update(value_number=float('nan')), 'incomplete_representative_tc'),
])
def test_representative_is_bound_to_real_scalar_tc_mu(change, code):
    row = point(representative=True)
    change(row)
    assert tc_record_issues(row)[0][1] == code


def test_draft_boundary_rejects_conflicting_conditions_or_duplicate_point_identity():
    first, second = point('a'), point('b')
    second['payload']['calculation_conditions']['k_grid'] = '3×3×3'
    draft = {'material_states': [{'state_kind': 'theoretical', 'material': 'LaSc2H24',
                                 'property_modules': [{'module_code': 'superconductive_properties', 'records': [first, second]}]}]}
    with pytest.raises(UploadContractError, match='不一致'):
        convert_legacy_scientific_draft(draft)
    second['payload']['calculation_conditions']['k_grid'] = '24×24×24'
    second['payload']['tc_group']['point_key'] = 'a'
    assert any(code == 'duplicate_tc_point' for _, code, _ in tc_collection_issues([first, second]))


def test_old_range_is_readable_without_silent_endpoint_or_group_assignment():
    legacy = point(representative=True)
    legacy['payload'].pop('tc_group')
    legacy.update(value_kind='range', value_number=None, value_min=281, value_max=311)
    before = deepcopy(legacy)
    assert not tc_collection_issues([legacy])
    assert tc_collection_issues([legacy], strict_representative=True)[0][1] == 'incomplete_representative_tc'
    assert legacy == before


def test_methods_soft_hyphen_is_only_formatting_not_a_different_software():
    from backend.ingest.scientific_context import reported_value_matches
    evidence = [{'quote': 'The harmonic phonons use Quantum-\u00ad ESPRESSO within density functional perturbation theory.'}]
    assert reported_value_matches('Quantum ESPRESSO', 'Quantum ESPRESSO', evidence)
    assert reported_value_matches('DFPT', 'DFPT', evidence)
    assert not reported_value_matches('VASP', 'VASP', evidence)
    table = [{'quote': 'Harmonic 290 3.56 865 18.69 311 to 339'}]
    assert reported_value_matches(3.56, '3.56', table)
    assert reported_value_matches(865, '865', table)
    assert not reported_value_matches(2903.56, '2903.56', table)


def test_group_and_range_history_are_not_current_scientific_claims():
    from backend.ingest.scientific_context import scientific_fingerprint
    from backend.ingest.scientific_evidence import record_claim
    row = point()
    before = scientific_fingerprint(row)
    row['payload']['tc_range_origin'] = {'value_min': 1, 'value_max': 9999}
    row['payload']['tc_group']['point_key'] = 'another-ui-key'
    assert scientific_fingerprint(row) == before
    snapshot = deepcopy(row)
    claim = record_claim(row, {})
    assert row == snapshot
    assert 'tc_group' not in claim['record']['payload']
    assert 'tc_range_origin' not in claim['record']['payload']
    row['value_number'] = 320
    assert scientific_fingerprint(row) != before
