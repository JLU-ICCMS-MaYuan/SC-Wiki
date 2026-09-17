"""Tc 只保留当前值，兼容 raw 列不能继续携带被更正的旧值。"""
import pytest

from backend.ingest.property_modules import PropertyValidationError, validate_record


def tc_record(**patch):
    return {
        "record_key": "tc-current", "module_code": "superconductive_properties",
        "record_type": "measured_tc", "property_code": "tc", "method_code": "resistivity",
        "name_raw": "Tc", "value_kind": "number", "value_number": 4.25,
        "value_raw": "wrong 3.78 mK", "unit_raw": "mK", "canonical_unit": "K",
        "payload": {"experimental_conditions": {}}, **patch,
    }


@pytest.mark.parametrize("patch,raw,unit", [
    ({}, "4.25", "K"),
    ({"value_number": 0}, "0", "K"),
    ({"value_number": 5.0, "value_raw": ""}, "5", "K"),
    ({"value_number": 1e-7}, "1e-7", "K"),
    ({"value_number": 1e-6}, "0.000001", "K"),
    ({"value_number": 1e20}, "100000000000000000000", "K"),
    ({"value_number": 1e21}, "1e+21", "K"),
    ({"value_kind": "range", "value_number": None, "value_min": 0, "value_max": 5.0}, "0–5", "K"),
    ({"value_kind": "text", "value_number": None, "value_text": "未观察到超导"}, "未观察到超导", None),
    ({"value_kind": "boolean", "value_number": None, "value_boolean": False}, "false", None),
])
def test_tc_current_value_overwrites_stale_raw_without_changing_input(patch, raw, unit):
    record = tc_record(**patch)
    old_raw = record["value_raw"]
    result = validate_record(record)
    assert result["value_raw"] == raw
    assert result["unit_raw"] == unit
    assert record["value_raw"] == old_raw
    assert result["record_key"] == record["record_key"]


@pytest.mark.parametrize("value", [None, -1, float("nan"), float("inf"), "4.2", True])
def test_old_raw_cannot_supply_missing_or_invalid_current_tc(value):
    with pytest.raises(PropertyValidationError):
        validate_record(tc_record(value_number=value))


@pytest.mark.parametrize("patch", [
    {"value_kind": "text", "value_number": None, "value_text": ""},
    {"value_kind": "boolean", "value_number": None, "value_boolean": "false"},
    {"value_kind": "range", "value_number": None, "value_min": "1", "value_max": 2},
    {"value_kind": "range", "value_number": None, "value_min": 0, "value_max": float("inf")},
])
def test_missing_or_invalid_typed_values_are_field_errors(patch):
    with pytest.raises(PropertyValidationError):
        validate_record(tc_record(**patch))


def test_current_only_record_accepts_omitted_raw():
    record = tc_record()
    del record["value_raw"]
    del record["unit_raw"]
    assert validate_record(record)["value_raw"] == "4.25"


def test_ordinary_property_still_keeps_its_own_contract():
    record = tc_record(record_type="property", property_code="custom", custom_property_key="property", payload={})
    assert validate_record(record)["value_raw"] == "wrong 3.78 mK"
