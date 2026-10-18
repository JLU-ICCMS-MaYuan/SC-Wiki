from copy import deepcopy

from backend.ingest.scientific_context import scientific_fingerprint, association_issues
from backend.ingest.upload_contracts import convert_legacy_scientific_draft


def test_field_annotations_roundtrip_and_invalidate_old_source_binding():
    record = {'record_key': 'r', 'record_type': 'predicted_tc', 'property_code': 'tc', 'name_raw': 'Tc',
              'method_code': 'isotropic_eliashberg', 'value_kind': 'number', 'value_number': 311,
              'payload': {'parameters': {'lambda_ep': 3.94, 'mu_star': .1},
                          'calculation_conditions': {'calculation_code': 'Quantum ESPRESSO'}}}
    before = scientific_fingerprint(record)
    association = {'version': 1, 'target_path': '/payload/calculation_conditions/calculation_code',
                   'basis_kind': 'paper_inference', 'stage': 'electron_phonon', 'scope': {},
                   'explanation': 'Methods 中的材料设置仍待人工核对', 'source_fingerprint': 'a' * 64, 'target_fingerprint': before,
                   'fact_evidences': [{'file_id': 'main', 'quote': 'Quantum ESPRESSO'}],
                   'scope_evidences': [{'file_id': 'main', 'quote': 'LaSc2H24'}]}
    record['payload']['source_associations'] = [association]
    assert not association_issues(record)
    record['payload']['calculation_conditions']['field_settings'] = {'calculation_code': {'name_raw': 'EPC软件', 'unit_raw': ''}}
    record['payload']['parameters']['field_settings'] = {'lambda_ep': {'name_raw': 'λ', 'unit_raw': '1'}}
    record['payload']['field_settings'] = {'tc': {'name_raw': '选定Tc', 'unit_raw': 'K'}}
    assert scientific_fingerprint(record) != before
    assert record['payload']['source_associations'][0]['target_fingerprint'] != scientific_fingerprint(record)
    assert not association_issues(record)  # 结构有效但科学指纹已变化，旧来源不重新授信。
    original = deepcopy(record)
    draft = {'material_states': [{'material': 'LaSc2H24', 'state_kind': 'theoretical',
             'property_modules': [{'module_code': 'superconductive_properties', 'records': [record]}]}]}
    actual = convert_legacy_scientific_draft(draft)['material_states'][0]['property_modules'][0]['records'][0]
    assert actual['payload'] == original['payload']
    assert record == original
