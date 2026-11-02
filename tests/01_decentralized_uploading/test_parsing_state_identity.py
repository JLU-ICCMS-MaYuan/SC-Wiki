"""#174/#176/#204：模型使用服务器稳定身份，不能要求模型填空身份。"""
from copy import deepcopy
import pytest
from backend.ingest.material_state_contract import ensure_state_keys, MaterialStateContractError


def test_initial_identity_assignment_preserves_existing_ids_and_is_idempotent():
    states = [{'state_key': None}, {'state_key': 'state-1'}, {}]
    ensure_state_keys(states)
    assigned = deepcopy(states)
    assert len({s['state_key'] for s in states}) == 3
    assert states[1]['state_key'] == 'state-1'
    ensure_state_keys(states)
    assert states == assigned


def test_duplicate_existing_identity_is_not_silently_reassigned():
    states = [{'state_key': 'same'}, {'state_key': 'same'}, {}]
    before = deepcopy(states)
    with pytest.raises(MaterialStateContractError):
        ensure_state_keys(states)
    assert states == before
