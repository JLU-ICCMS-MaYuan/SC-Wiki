"""#211 FR-002：初步非空压力不是事实，查图后只纠正相关记录。"""
from copy import deepcopy
import base64
import hashlib
import json

import pytest


def case(material="LaH10"):
    evidence = {"file_id": "main", "pdf_page": 1, "block_id": "numeric",
                "quote": "DOS is 10 states/Ry; see Fig. 6 and Fig. S3."}
    states = [{"state_key": "old", "material": material, "pressure_value_gpa": 300,
        "state_kind": "theoretical", "structure_optimization": "classical_static",
        "property_modules": [
            {"module_key": "tc", "module_code": "superconductive_properties",
             "records": [{"record_key": "tc-300", "property_code": "tc", "value_number": 241}]},
            {"module_key": "el", "module_code": "electronic_properties",
             "records": [{"record_key": "dos", "property_code": "dos_fermi", "value_number": 10,
                          "evidences": [evidence]}]}]}]
    sources = [{"source_id": "s0", "file_id": "main", "page_start": 1,
                "block_id": "numeric", "content": evidence["quote"]},
               {"source_id": "s1", "file_id": "main", "page_start": 2,
                "block_id": "bands", "content": "Fig. 6. Electronic bands and phonons at 300 GPa."},
               {"source_id": "s2", "file_id": "si", "page_start": 1,
                "block_id": "dos-caption", "content": "Fig. S3. Electronic DOS at 250 GPa."}]
    def entry(pressure):
        return {"values": {"material": material, "pressure_value_gpa": pressure,
            "state_kind": "theoretical", "structure_optimization": "classical_static"},
            "source_ids": ["s1" if pressure == 300 else "s2"], "reason": "对应物理量及条件"}
    response = {"states": [entry(300), entry(250)],
        "assignments": [{"candidate_state_key": "old", "target_index": 0,
            "status": "supported", "source_ids": ["s1"], "reason": "300 GPa的Tc保留"}],
        "record_assignments": [{"candidate_state_key": "old", "module_key": "el",
            "record_key": "dos", "target_index": 1, "status": "supported", "source_ids": ["s0", "s2"],
            "reason": "图6不是电子DOS；图S3图例和图注支持250 GPa，仅调整DOS，不移动300 GPa的Tc"}]}
    return states, sources, response


@pytest.mark.parametrize("material", ["LaH10", "MgH6"])
def test_record_correction_preserves_other_pressure_results_and_all_origins(material):
    from backend.ingest.state_inventory import apply_inventory
    states, sources, response = case(material)
    before = deepcopy(states)
    result = apply_inventory({"material_states": states}, sources, response)
    first, second = result["material_states"]
    assert [(r["record_key"], r["value_number"]) for m in first["property_modules"] for r in m["records"]] == [("tc-300", 241)]
    moved = second["property_modules"][0]["records"][0]
    assert moved["record_key"] == "dos" and moved["value_number"] == 10
    assert before[0]["property_modules"][1]["records"][0]["evidences"][0] in moved["evidences"]
    assert any(e["file_id"] == "si" and e["pdf_page"] == 1 for e in moved["evidences"])
    assert states == before
    assert not result["generation_issues"]


@pytest.mark.parametrize("mutation", ["unknown_record", "duplicate", "other_material", "other_phase", "other_optimization", "unknown_source"])
def test_record_assignment_cannot_lose_duplicate_or_borrow_other_conditions(mutation):
    from backend.ingest.state_inventory import apply_inventory
    states, sources, response = case()
    override = response["record_assignments"][0]
    if mutation == "unknown_record": override["record_key"] = "missing"
    elif mutation == "duplicate": response["record_assignments"].append(deepcopy(override))
    elif mutation == "other_material": response["states"][1]["values"]["material"] = "YH10"
    elif mutation == "other_phase":
        states[0]["reported_space_group_symbol"] = "Fm-3m"
        response["states"][0]["values"]["reported_space_group_symbol"] = "Fm-3m"
        response["states"][1]["values"]["reported_space_group_symbol"] = "Im-3m"
    elif mutation == "other_optimization": response["states"][1]["values"]["structure_optimization"] = "sscha"
    elif mutation == "unknown_source": override["source_ids"] = ["invented"]
    before = deepcopy(states)
    with pytest.raises(ValueError): apply_inventory({"material_states": states}, sources, response)
    assert states == before


def test_only_wrong_scalar_does_not_force_an_empty_state_for_its_initial_guess():
    from backend.ingest.state_inventory import apply_inventory
    states, sources, response = case()
    states[0]["property_modules"] = [states[0]["property_modules"][1]]
    response["states"] = [response["states"][1]]
    response["assignments"][0].update(target_index=0, source_ids=["s2"], reason="原300是初猜，图S3确认该记录为250")
    response["record_assignments"][0]["target_index"] = 0
    result = apply_inventory({"material_states": states}, sources, response)
    assert len(result["material_states"]) == 1
    assert result["material_states"][0]["pressure_value_gpa"] == 250


def test_known_nonempty_pressure_still_reads_all_referenced_actual_figure_pages(tmp_path, monkeypatch):
    from backend.ingest.state_inventory import plan_states
    import pymupdf
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    files = []
    for file_id, texts in [("main", ["DOS is 10 states/Ry; see Fig. 6 and Fig. S3.",
                                    "Fig. 6. Electronic bands and phonons at 300 GPa."]),
                           ("si", ["Fig. S3. Electronic DOS at 250 GPa."])]:
        path = tmp_path / (file_id + ".pdf")
        with pymupdf.open() as document:
            for text in texts:
                page = document.new_page()
                page.insert_text((40, 60), text)
            document.save(path)
        files.append({"file_id": file_id, "kind": "pdf", "stored_path": str(path),
            "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    states, sources, response = case()
    chunks = [{k: v for k, v in s.items() if k != "source_id"} for s in sources]
    seen = []
    def model(_, content, **kwargs):
        request = json.loads(content)
        assert {(p["file_id"], p["pdf_page"]) for p in request["original_pages"]} == {("main", 2), ("si", 1)}
        assert len(kwargs["images"]) == 2
        assert all(base64.b64decode(value.split(",", 1)[1]).startswith(b"\x89PNG") for value in kwargs["images"])
        seen.append(request)
        answer = deepcopy(response)
        for item in [*answer["states"], *answer["assignments"], *answer["record_assignments"]]:
            item["source_ids"] = ["inventory-source-" + value[1:] for value in item["source_ids"]]
        return answer
    result = plan_states({"material_states": states}, chunks, model, files=files)
    assert seen and result["material_states"][1]["property_modules"][0]["records"][0]["record_key"] == "dos"
