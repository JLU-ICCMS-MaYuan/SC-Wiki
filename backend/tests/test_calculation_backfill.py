from copy import deepcopy

import pytest

from backend.ingest.calculation_backfill import assert_conditions_only, assert_current, condition_proposal, projection, revalidate_prior_candidates
from backend.ingest.scientific_context import build_context, fingerprint, scientific_fingerprint


def sample():
    record = {'record_key': 'r', 'module_code': 'superconductive_properties', 'record_type': 'predicted_tc', 'property_code': 'tc',
              'name_raw': 'Tc', 'method_code': 'isotropic_eliashberg', 'definition_key': 'record.superconductive_properties.predicted_tc.isotropic_eliashberg',
              'definition_version': 1, 'value_kind': 'number', 'value_number': 311, 'value_min': 281, 'value_max': 311, 'value_raw': '311',
              'canonical_unit': 'K', 'payload': {'parameters': {'lambda_ep': 3.94, 'omega_log': 745, 'mu_star': .1}, 'calculation_conditions': {}},
              'evidences': [{'file_id': 'main', 'quote': 'Anharmonic 150 3.94 745 18.44 281 to 311'}]}
    draft = {'material_states': [{'state_key': 's', 'material': 'LaSc2H24', 'pressure_value_gpa': 150,
              'property_modules': [{'module_key': 'm', 'module_code': 'superconductive_properties', 'records': [record]}]}]}
    context = build_context([{'file_id': 'main', 'file_role': 'main', 'source_sha256': 'a'*64,
                             'content': 'Phonons use a 24x24x24 k grid. SSCHA uses an 80 Ry cutoff.'}])
    return draft, record, context


def test_condition_only_backfill_keeps_parameters_tc_manual_values_and_source_binding():
    draft, record, context = sample()
    original = deepcopy(draft)
    projected = projection(draft)
    target = projected['material_states'][0]['property_modules'][0]['records'][0]
    assert target['value_min'] is None and target['payload']['approximation'] == 'anharmonic'
    evidence = {'source_id': context['sources'][0]['source_id']}
    candidate = {'target': 's/m/r', 'target_path': '/payload/calculation_conditions/k_grid', 'value': '24x24x24',
                 'stage': 'electron_phonon', 'basis_kind': 'paper_inference', 'scope': {'material': 'LaSc2H24'},
                 'expected_fingerprint': scientific_fingerprint(target), 'fact_evidences': [evidence], 'scope_evidences': [evidence],
                 'reported_value_raw': '24x24x24', 'explanation': '原文说明该材料声子计算的网格，适用范围仍须核对。'}
    updated, applied, gaps = condition_proposal(draft, projected, [candidate], context)
    assert len(applied) == 1 and not gaps
    actual = updated['material_states'][0]['property_modules'][0]['records'][0]
    assert actual['value_min'] == 281 and actual['value_number'] == 311
    assert actual['payload']['parameters'] == record['payload']['parameters']
    assert actual['payload']['source_associations'][0]['target_fingerprint'] == scientific_fingerprint(actual)
    assert 'approximation' not in actual['payload']
    assert draft == original
    assert_conditions_only(draft, updated)
    manual = deepcopy(draft)
    manual['material_states'][0]['property_modules'][0]['records'][0]['payload']['calculation_conditions']['k_grid'] = '12x12x12'
    projected_manual = projection(manual)
    candidate['expected_fingerprint'] = scientific_fingerprint(projected_manual['material_states'][0]['property_modules'][0]['records'][0])
    preserved, applied, gaps = condition_proposal(manual, projected_manual, [candidate], context)
    assert not applied and gaps
    assert preserved == manual


def test_stale_plan_and_noncondition_values_are_rejected():
    draft, _, _ = sample()
    state = {'status': 'ready', 'revision': 6}
    assert_current(fingerprint(draft), 6, draft, state)
    for changed in [{'status': 'ready', 'revision': 7}, {'status': 'submitted', 'revision': 6}]:
        with pytest.raises(ValueError, match='变化'):
            assert_current(fingerprint(draft), 6, draft, changed)
    updated = deepcopy(draft)
    updated['material_states'][0]['property_modules'][0]['records'][0]['value_number'] = 500
    with pytest.raises(ValueError, match='之外'):
        assert_conditions_only(draft, updated)


def test_unknown_approximation_does_not_receive_sscha():
    draft, record, context = sample()
    record['evidences'] = []
    projected = projection(draft)
    evidence = {'source_id': context['sources'][0]['source_id']}
    candidate = {'target': 's/m/r', 'target_path': '/payload/calculation_conditions/extensions/-', 'stage': 'sscha',
                 'value': {'key': 'sscha.energy_cutoff', 'value_kind': 'number', 'value_number': 80, 'value_raw': '80', 'unit_raw': 'Ry'},
                 'expected_fingerprint': scientific_fingerprint(record), 'basis_kind': 'paper_inference', 'scope': {'material': 'LaSc2H24'},
                 'fact_evidences': [evidence], 'scope_evidences': [evidence], 'reported_value_raw': '80', 'explanation': '模型候选，不代表已获准适用。'}
    updated, applied, gaps = condition_proposal(draft, projected, [candidate], context)
    assert not applied and gaps[0]['reason'] == 'scope_ambiguous'
    assert updated == draft


def test_reusing_real_candidates_requires_identical_sources_draft_and_target():
    draft, _, context = sample()
    projected = projection(draft)
    target = projected['material_states'][0]['property_modules'][0]['records'][0]
    ledger = {'version': 'old-reader', 'complete': True,
              'source_fingerprint': fingerprint(['old-reader', context['sources'], context.get('tables', [])]),
              'associations': [{'target': 's/m/r', 'expected_fingerprint': scientific_fingerprint(target)}]}
    before = deepcopy(ledger)
    assert revalidate_prior_candidates(draft, projected, context, deepcopy(draft), ledger) == ledger['associations']
    assert ledger == before
    changed_source = deepcopy(context)
    changed_source['sources'][0]['source_sha256'] = 'b' * 64
    changed_draft = deepcopy(draft)
    changed_draft['material_states'][0]['material'] = 'Other'
    changed_target = deepcopy(ledger)
    changed_target['associations'][0]['expected_fingerprint'] = 'outdated'
    for current, source, candidate in [(changed_draft, context, ledger), (draft, changed_source, ledger), (draft, context, changed_target)]:
        with pytest.raises(ValueError):
            revalidate_prior_candidates(current, projected, source, draft, candidate)
