"""优化方式归属不应重复发送整组物性记录，更不能改写它们。"""
from copy import deepcopy
import json

from backend.ingest.state_optimization import resolve_candidates


def test_optimizer_only_reads_state_identity_and_sources_keeps_records_in_host():
    records = [{'record_key': 'r', 'property_code': 'tc', 'value_number': 235,
        'payload': {'parameters': {'lambda_ep': 2.69, 'omega_log': 800}},
        'evidences': [{'quote': 'An independent Tc and EPC result.'}]}]
    candidates = [{'material_states': [{'material': 'CaH6', 'material_name': 'CaH6',
        'state_kind': 'theoretical', 'pressure_value_gpa': 150, 'reported_space_group_symbol': 'Im-3m',
        'structure_optimization': 'unknown', 'property_modules': [{'records': records}],
        'evidences': [{'quote': 'CaH6 at 150 GPa.'}]}]}]
    original = deepcopy(candidates)
    def model(_prompt, content):
        payload = json.loads(content)
        target = payload['targets'][0]['state']
        assert 'property_modules' not in target
        assert target['material'] == 'CaH6' and target['pressure_value_gpa'] == 150
        assert target['evidences'] == original[0]['material_states'][0]['evidences']
        return {'workflows': [], 'assignments': [{'target': '0/0', 'optimization': 'unknown',
            'workflow_id': None, 'reason': '原文不足', 'evidences': []}]}
    result, issues = resolve_candidates(candidates, [{'file_id': 'main', 'content': 'CaH6 at 150 GPa.'}], model)
    assert not issues and result == original and candidates == original
