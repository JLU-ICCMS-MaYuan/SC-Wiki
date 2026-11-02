"""#181：只接受已确认的简谐同义写法，保持科学类别和原文来源。"""
from copy import deepcopy

import pytest

from backend.ingest.calculation_methods import method_field_issue, record_method_issue
from backend.ingest.property_extensions import normalize_extracted_conditions


def test_reported_harmonic_approximation_is_not_an_electronic_method_error():
    assert method_field_issue("vibrational_treatment", "harmonic approximation") is None


def test_fresh_candidate_normalizes_value_but_preserves_source_and_other_fields():
    raw = {"module_code": "superconductive_properties", "property_code": "tc", "record_type": "predicted_tc",
           "payload": {"calculation_conditions": {"electronic_method": "DFT", "phonon_method": "DFPT",
                                                    "vibrational_treatment": "harmonic approximation"}},
           "evidences": [{"file_id": "main", "pdf_page": 4, "block_id": "source",
                          "quote": "The calculation of the EPC is based on the harmonic approximation."}]}
    candidate = deepcopy(raw)
    normalize_extracted_conditions(candidate)
    assert candidate["payload"]["calculation_conditions"]["vibrational_treatment"] == "harmonic"
    assert candidate["evidences"] == raw["evidences"]
    assert candidate["payload"]["calculation_conditions"]["phonon_method"] == "DFPT"
    assert raw["payload"]["calculation_conditions"]["vibrational_treatment"] == "harmonic approximation"
    assert record_method_issue(candidate) is None


@pytest.mark.parametrize("value", ["DFT", "HF", "DFPT", "density functional theory"])
def test_wrong_scientific_categories_are_still_rejected(value):
    assert "电子理论" in method_field_issue("vibrational_treatment", value)


@pytest.mark.parametrize("value", ["unrecognized treatment", "harmonic approximation with extra corrections"])
def test_unrecognized_wording_is_not_misreported_as_dft(value):
    issue = method_field_issue("vibrational_treatment", value)
    assert "未识别" in issue
    assert "DFT" not in issue


@pytest.mark.parametrize("value", ["unknown", "harmonic", "quasi_harmonic", "anharmonic", "anharmonic_quantum", "anharmonic_classical"])
def test_existing_canonical_values_remain_valid(value):
    assert method_field_issue("vibrational_treatment", value) is None
