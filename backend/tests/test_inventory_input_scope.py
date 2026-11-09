"""材料状态规划只判断归属；数值完整留在宿主，避免重复发送参数和来源副本。"""
from copy import deepcopy
import json

from backend.ingest.state_inventory import plan_states, FIELDS


def test_state_planner_receives_identity_scalar_and_record_ids_not_parameter_bodies():
    record = {'record_key': 'r', 'record_type': 'predicted_tc', 'property_code': 'tc',
        'value_kind': 'number', 'value_number': 235, 'value_raw': '235 K', 'canonical_unit': 'K',
        'method_code': 'isotropic_eliashberg', 'payload': {'parameters': {'lambda_ep': 2.69, 'omega_log': 800, 'mu_star': .1}}}
    state = {'state_key': 's', 'material': 'CaH6', 'material_name': 'CaH6', 'state_kind': 'theoretical',
        'pressure_value_gpa': 150, 'structure_optimization': 'classical_static',
        'property_modules': [{'module_key': 'm', 'module_code': 'superconductive_properties', 'records': [record]}]}
    draft = {'paper': {'research_materials': ['Reviewed calcium hydrides']}, 'material_states': [state]}
    before = deepcopy(draft)
    def model(_prompt, content, **_options):
        request = json.loads(content); candidate = request['candidates'][0]
        supplied = candidate['property_modules'][0]['records'][0]
        assert supplied['record_key'] == 'r' and supplied['value_number'] == 235
        assert 'parameters' not in (supplied.get('payload') or {})
        source_id = request['sources'][0]['source_id']
        return {'states': [{'values': {k: state.get(k) for k in FIELDS}, 'source_ids': [source_id], 'reason': '原文同一状态'}],
            'assignments': [{'candidate_state_key': 's', 'target_index': 0, 'status': 'supported',
                             'reason': '原值与原文状态一致', 'source_ids': [source_id]}], 'record_assignments': []}
    plan_states(draft, [{'file_id': 'main', 'content': 'CaH6 at 150 GPa has Tc 235 K.'}], model)
    assert draft['material_states'][0]['property_modules'][0]['records'][0] == record
    assert draft['paper'] == before['paper']
