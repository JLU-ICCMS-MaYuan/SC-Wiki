"""领域契约与确定性组装；用反例验证条件和来源不被汇总改写。"""
import copy
import json

import pytest

from backend.ingest.domain_extraction import normalize_extraction, merge_scientific_candidates, structured_chunks
from backend.ingest.document_parsers import DocumentSource, ParseOptions, PyMuPDFParser, ParserError
from backend.ingest.document_claims import claims_from_candidates


def extraction():
    evidence = {"file_id": "main", "pdf_page": 1, "block_id": "b1", "quote": "LaH10 Tc = 200 K at 150 GPa"}
    return {"extraction_version": "1", "material_states": [{
        "scope": "current_paper", "material": "LaH10", "state_kind": "experimental",
        "pressure_value_gpa": 150, "evidences": [evidence],
        "property_modules": [{"module_code": "superconductive_properties", "records": [{
            "module_code": "superconductive_properties", "record_type": "measured_tc", "property_code": "tc",
            "name_raw": "critical temperature", "value_kind": "number", "value_number": 200,
            "value_raw": "200 K", "unit_raw": "K", "canonical_unit": "K", "method_code": "unknown",
            "payload": {"experimental_conditions": {"description": "Four-probe measurement."}},
            "evidences": [copy.deepcopy(evidence)],
        }]}],
    }]}


def normalize(raw):
    return normalize_extraction(raw, allowed_blocks={("main", 1, "b1"), ("main", 2, "b2")})


def test_unknown_measurement_method_is_never_guessed_and_values_are_preserved():
    result = normalize(extraction())
    record = result["material_states"][0]["property_modules"][0]["records"][0]
    assert record["method_code"] == "unknown"
    assert record["value_raw"] == "200 K"
    assert record["definition_key"] == "record.superconductive_properties.measured_tc.unknown"
    assert record["record_key"].startswith("ir-")
    assert result["extraction_version"] == "1"


@pytest.mark.parametrize("change", ["legacy", "incompatible_conditions", "method", "pressure", "nan", "outside", "module", "tc_as_property", "tc_in_wrong_module"])
def test_invalid_scientific_contract_fails(change):
    raw = extraction()
    state = raw["material_states"][0]
    record = state["property_modules"][0]["records"][0]
    if change == "legacy": state["tc_results"] = []
    elif change == "incompatible_conditions": record["payload"] = {"calculation_conditions": {}}
    elif change == "method": record["method_code"] = "experimental"
    elif change == "pressure": state.update(pressure_min_gpa=160, pressure_max_gpa=140)
    elif change == "nan": record["value_number"] = float("nan")
    elif change == "outside": record["evidences"][0]["file_id"] = "other"
    elif change == "module": record["module_code"] = "electronic_properties"
    elif change == "tc_as_property": record["record_type"] = "property"
    elif change == "tc_in_wrong_module":
        state["property_modules"][0]["module_code"] = record["module_code"] = "electronic_properties"
    with pytest.raises(ValueError): normalize(raw)


def test_different_pressures_materials_methods_and_conditions_survive_merge():
    candidates = []
    for material, pressure, method, condition in [
        ("LaH10", 150, "resistivity", "onset"), ("LaH10", 160, "resistivity", "onset"),
        ("LaH10", 150, "specific_heat", "peak"), ("LaH10", 150, "resistivity", "zero resistance"),
        ("YH6", 150, "resistivity", "onset"),
    ]:
        raw = extraction()
        state = raw["material_states"][0]
        state.update(material=material, pressure_value_gpa=pressure)
        record = state["property_modules"][0]["records"][0]
        record.update(method_code=method, criterion_raw=condition)
        candidates.append(normalize(raw))
    merged = merge_scientific_candidates([*candidates, copy.deepcopy(candidates[0])])
    records = [r for s in merged for m in s["property_modules"] for r in m["records"]]
    assert len(merged) == 3 and len(records) == 5
    assert len({r["record_key"] for r in records}) == 5
    assert {r["criterion_raw"] for r in records} == {"onset", "peak", "zero resistance"}


def test_referenced_work_is_not_assembled_and_inference_stays_uncertain():
    raw = extraction(); raw["material_states"][0]["scope"] = "referenced_work"
    assert merge_scientific_candidates([normalize(raw)]) == []
    raw = extraction(); raw["material_states"][0]["basis_kind"] = "paper_inference"
    claims = claims_from_candidates(normalize(raw), {})
    assert claims and all(c.status == "uncertain" for c in claims)


def test_cross_page_multiple_evidences_survive(tmp_path):
    import pymupdf
    path = tmp_path / "two-pages.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 70), "LaH10 at 150 GPa.")
        pdf.new_page().insert_text((50, 70), "Tc = 200 K from resistivity.")
        pdf.save(path)
    ir = PyMuPDFParser().parse(DocumentSource(path, "main"), ParseOptions())
    chunks = structured_chunks(ir)
    context = json.loads(chunks[0].content)
    assert [p["geometry"]["pdf_page"] for p in context["pages"]] == [1, 2]
    assert chunks[0].source_page_end == 2
    raw = extraction()
    evidence = [{"file_id": "main", "pdf_page": b.pdf_page, "block_id": b.block_id, "quote": b.text.strip()}
                for b in ir.blocks if b.text.strip()]
    state = raw["material_states"][0]
    state["evidences"] = copy.deepcopy(evidence)
    state["property_modules"][0]["records"][0]["evidences"] = copy.deepcopy(evidence)
    result = normalize_extraction(raw, allowed_blocks={("main", b.pdf_page, b.block_id) for b in ir.blocks})
    claims = claims_from_candidates(result, {"main": ir})
    assert len(claims) == 2
    assert all(c.status == "validated" and {e.pdf_page for e in c.evidences} == {1, 2} for c in claims)
    broken = copy.deepcopy(result)
    broken["material_states"][0]["property_modules"][0]["records"][0]["evidences"][1]["quote"] = "invented quote"
    assert claims_from_candidates(broken, {"main":ir})[-1].status == "uncertain"
    with pytest.raises(ParserError, match="单页"):
        structured_chunks(ir, max_chars=20)


def test_record_unit_and_raw_range_are_not_reparsed():
    raw = extraction()
    record = raw["material_states"][0]["property_modules"][0]["records"][0]
    record.update(value_kind="range", value_number=None, value_min=199, value_max=201,
                  value_raw="199–201 K", unit_raw="kelvin", uncertainty=1)
    result = normalize(raw)
    actual = merge_scientific_candidates([result])[0]["property_modules"][0]["records"][0]
    assert (actual["value_min"], actual["value_max"], actual["uncertainty"]) == (199, 201, 1)
    assert actual["value_raw"] == "199–201 K" and actual["unit_raw"] == "kelvin"


def test_text_attachment_source_is_preserved_during_mixed_document_merge():
    candidate = {"_source":{"file_id":"text-attachment"}, "material_states":[{
        "scope":"current_paper", "material":"LaH10", "evidence":{"quote":"200 K"},
        "tc_results":[{"tc_value_k":200,"tc_method":"unknown","result_kind":"theoretical", "evidence":{"quote":"200 K"}}],
    }]}
    state = merge_scientific_candidates([candidate])[0]
    assert state["evidence"]["file_id"] == "text-attachment"
    assert state["property_modules"][0]["records"][0]["evidence"]["file_id"] == "text-attachment"
    assert not claims_from_candidates({"material_states":[state]}, {}, legacy_sources={"text-attachment":"200 K"})
