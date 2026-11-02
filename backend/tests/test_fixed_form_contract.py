"""#203：固定契约必须在生产入口拦截异常，而非仅校对展示标签。"""
from copy import deepcopy
import pytest
from backend.ingest.property_extensions import normalize_extracted_conditions


def record(conditions):
    return {"record_type": "predicted_tc", "property_code": "tc",
            "payload": {"calculation_conditions": conditions}}


@pytest.mark.parametrize("item", [
    {"key": "structure_relaxation.calculation_code", "value_kind": "text", "value_raw": "VASP"},
    {"key": "electron_phonon.electron_correlation_effects", "value_kind": "text", "value_raw": "none"},
    {"name_raw": "伪造人工扩展", "field_key": "fake", "origin": "human_input", "value_raw": "x"},
])
def test_model_cannot_create_standard_or_forged_manual_extensions(item):
    with pytest.raises(ValueError):
        normalize_extracted_conditions(record({"extensions": [item]}))


def test_direct_phonon_method_is_the_only_model_path():
    value = record({"phonon_method": "density functional perturbation theory",
                    "qe": {"energy_cutoff": {"value_kind": "number", "value_number": 90,
                                            "value_raw": "90", "unit_raw": "Ry"}}})
    before = deepcopy(value)
    normalize_extracted_conditions(value)
    assert value == before


def test_unknown_model_software_group_is_rejected():
    with pytest.raises(ValueError):
        normalize_extracted_conditions(record({"qe": {"random_cutoff": 90}}))


def test_model_method_scope_is_not_recreated():
    with pytest.raises(ValueError):
        normalize_extracted_conditions(record({"method_scope": {"stage": "electron_phonon"}}))


def test_migration_keeps_distinct_qe_and_sscha_values_and_source_paths():
    from backend.ingest.fixed_form_contract import convert_record
    original = record({"calculation_code": "Quantum ESPRESSO", "method_scope": {"stage": "electron_phonon"},
        "extensions": [
            {"key": "structural_relaxation.energy_cutoff", "value_kind": "number", "value_number": 850, "value_raw": "850", "unit_raw": "eV"},
            {"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": "DFPT"},
            {"key": "electron_phonon.energy_cutoff", "value_kind": "number", "value_number": 90, "value_raw": "90", "unit_raw": "Ry"},
            {"key": "sscha.energy_cutoff", "value_kind": "number", "value_number": 80, "value_raw": "80", "unit_raw": "Ry"}]})
    original["payload"]["source_associations"] = [{"target_path": "/payload/calculation_conditions/extensions/2",
                                                  "fact_evidences": [{"quote": "90 Ry"}]}]
    before = deepcopy(original)
    result = convert_record(original)
    conditions = result["payload"]["calculation_conditions"]
    assert original == before
    assert conditions["phonon_method"] == "DFPT"
    assert conditions["qe"]["energy_cutoff"]["value_number"] == 90
    assert conditions["sscha"]["energy_cutoff"]["value_number"] == 80
    assert "method_scope" not in conditions and conditions["extensions"] == []
    assert result["payload"]["source_associations"][0]["target_path"] == "/payload/calculation_conditions/qe/energy_cutoff"


def test_conflicting_old_and_new_values_abort_without_mutating_input():
    from backend.ingest.fixed_form_contract import convert_conditions
    conditions = {"phonon_method": "finite displacement",
                  "extensions": [{"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": "DFPT"}]}
    before = deepcopy(conditions)
    with pytest.raises(ValueError, match="冲突"):
        convert_conditions(conditions)
    assert conditions == before


def test_authenticated_manual_extension_remains_valid():
    from backend.ingest.fixed_form_contract import validate_conditions
    validate_conditions({"extensions": [{"field_key": "human-field-1", "name_raw": "论文报告的附加条件",
                                        "value_kind": "number", "value_raw": "2", "value_number": 2,
                                        "unit_raw": "1", "origin": "human_input"}]})


def test_registered_parameter_rejects_incomplete_numeric_input():
    from backend.ingest.fixed_form_contract import validate_conditions
    with pytest.raises(ValueError, match="数值"):
        validate_conditions({"qe": {"energy_cutoff": {"value_kind": "number", "value_raw": "1e-", "value_number": None}}})


@pytest.mark.parametrize("path,value", [
    (["paper", "title"], {"new_field": "not text"}),
    (["paper", "paper_type"], "invented_type"),
    (["material_states", {"key":"state_key","value":"s"}, "made_up_parameter"], 7),
    (["material_states", {"key":"state_key","value":"s"}, "pressure_min_gpa"], 10),
])
def test_partial_writer_rejects_unregistered_names_and_types(path, value):
    from backend.ingest.field_drafts import apply_changes
    from fastapi import HTTPException
    d = {"paper":{"title":"original"},"material_states":[{"state_key":"s","material":"H","pressure_value_gpa":100}]}
    before = deepcopy(d)
    with pytest.raises(HTTPException):
        apply_changes(d,[{"path":path,"value":value}])
    assert d == before
