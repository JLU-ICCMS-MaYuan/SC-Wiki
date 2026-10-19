import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from backend.ingest.upload_jobs import _bind_structure_candidates, _formula_from_material


def test_formula_identity_separates_space_group_prefix_and_preserves_unknown_names():
    assert _formula_from_material("Fd-3m-Li2MgH16") == "Li2MgH16"
    assert _formula_from_material("P6/mmm-LaSc2H24") == "LaSc2H24"
    assert _formula_from_material("Li2MgH16") == "Li2MgH16"
    assert _formula_from_material("unknown-Li2MgH16") == ""


def test_matching_space_group_and_pressure_do_not_cross_compounds():
    draft = {"material_states": [
        {"material": "LaSc2H24", "reported_space_group_symbol": "P6/mmm", "pressure_value_gpa": 300},
        {"material": "LaSc2", "reported_space_group_symbol": "P6/mmm", "pressure_value_gpa": 300},
    ]}
    candidate = {"material_state_ref": "unassigned:supp", "reported_structure": {
        "material": "LaSc2H24", "space_group_symbol": "P6/mmm", "pressure_value_gpa": 300,
    }}
    _bind_structure_candidates(draft, [candidate])
    assert candidate["material_state_ref"] == "material_states[0]"
    candidate["material_state_ref"] = "unassigned:supp"
    draft["material_states"] = draft["material_states"][1:]
    _bind_structure_candidates(draft, [candidate])
    assert candidate["material_state_ref"] == "unassigned:supp"


def test_binding_does_not_approve_failed_structure_or_pick_an_ambiguous_state():
    state = {"material": "LaSc2H24", "reported_space_group_symbol": "P6/mmm", "pressure_value_gpa": 300}
    candidate = {"material_state_ref": "unassigned:supp", "status": "blocked", "confirmation": "unreviewed",
                 "reported_structure": {"material": "LaSc2H24", "space_group_symbol": "P6/mmm", "pressure_value_gpa": 300}}
    _bind_structure_candidates({"material_states": [state, dict(state)]}, [candidate])
    assert candidate["material_state_ref"] == "unassigned:supp"
    _bind_structure_candidates({"material_states": [state]}, [candidate])
    assert candidate["material_state_ref"] == "material_states[0]"
    assert candidate["status"] == "blocked" and candidate["confirmation"] == "unreviewed"
