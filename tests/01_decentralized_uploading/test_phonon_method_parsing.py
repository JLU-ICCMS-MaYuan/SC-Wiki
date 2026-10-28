"""#172：真实新提取入口的格式、声子方法及泛函边界。"""
from copy import deepcopy

import pytest

from backend.ingest.domain_extraction import normalize_extraction, merge_scientific_candidates
from backend.ingest.upload_jobs import _normalize_draft
from test_issue114_domain_extraction import extraction


def raw_with(extensions, quote="Phonons of LaH10 use DFPT with Quantum ESPRESSO. VASP uses PBE for optimization."):
    raw = extraction()
    state = raw["material_states"][0]
    state["state_kind"] = "theoretical"
    record = state["property_modules"][0]["records"][0]
    record.update(record_type="predicted_tc", method_code="allen_dynes")
    record["payload"] = {"calculation_conditions": {"calculation_code": "Quantum ESPRESSO",
        "exchange_correlation_functional": "PBE", "extensions": deepcopy(extensions)}}
    record["evidences"].append({"file_id": "main", "pdf_page": 2, "block_id": "b2", "quote": quote})
    return raw


def run(raw):
    return normalize_extraction(raw, allowed_blocks={("main", 1, "b1"), ("main", 2, "b2")}, form_parameters=True)


def conditions(result):
    return result["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]


def test_observed_group_preserves_method_and_source_through_assembly_and_draft():
    raw = raw_with({"electron_phonon": {"phonon_method": "DFPT"}})
    before = deepcopy(raw)
    result = run(raw)
    value = conditions(result)
    assert value["extensions"] == [{"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": "DFPT"}]
    assert value["exchange_correlation_functional"] is None
    assert value["calculation_code"] == "Quantum ESPRESSO"
    assert raw == before
    draft = _normalize_draft({"material_states": merge_scientific_candidates([result])})
    assert conditions(draft)["extensions"][0]["value_raw"] == "DFPT"
    assert draft["material_states"][0]["property_modules"][0]["records"][0]["evidences"] == result["material_states"][0]["property_modules"][0]["records"][0]["evidences"]


@pytest.mark.parametrize("extensions", [None, {}, []])
def test_empty_extensions_remain_empty(extensions):
    assert conditions(run(raw_with(extensions)))["extensions"] == []


def test_canonical_list_preserves_metadata_and_explicit_qe_functional():
    extension = {"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": "DFPT",
                 "name_raw": "My phonon method", "field_key": "original-field", "unit_raw": "", "reported": {"text": "DFPT"}}
    value = conditions(run(raw_with([extension], "Quantum ESPRESSO uses PBE and DFPT for LaH10.")))
    assert value["extensions"] == [extension]
    assert value["exchange_correlation_functional"] == "PBE"


@pytest.mark.parametrize("extensions", ["DFPT", 1, False, ["DFPT"], [None], [1], [{}], [{"key": 1}],
    {"phonon_method": "DFPT"}, {"other": {"phonon_method": "DFPT"}},
    {"electron_phonon": {"phonon_method": "DFPT", "unknown": "x"}},
    {"electron_phonon": {"phonon_method": ""}}, {"electron_phonon": {"phonon_method": 1}},
    {"electron_phonon": "DFPT"}])
def test_unknown_or_malformed_shape_is_explicit_error_not_silent_drop(extensions):
    with pytest.raises(ValueError, match="extensions"):
        run(raw_with(extensions))


@pytest.mark.parametrize("bad", ["DFPT", ["DFPT"], 1, False])
def test_invalid_conditions_container_is_explicit_error(bad):
    raw = raw_with([])
    raw["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"] = bad
    with pytest.raises(ValueError, match="calculation_conditions"):
        run(raw)


def test_wrong_electronic_method_is_still_rejected():
    raw = raw_with({"electron_phonon": {"phonon_method": "DFPT"}})
    raw["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]["electronic_method"] = "DFPT"
    with pytest.raises(ValueError, match="电子结构方法"):
        run(raw)


@pytest.mark.parametrize("custom", [None, "自定义声子方法"])
def test_review_sidebar_label_preserves_manual_name(custom):
    from backend.ingest.property_evidence import draft_records
    item = {"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": "DFPT"}
    if custom:
        item["name_raw"] = custom
    draft = _normalize_draft({"material_states": merge_scientific_candidates([run(raw_with([item]))])})
    from backend.ingest.property_field_review import expand_property_fields
    fields = expand_property_fields(draft_records(draft, {}))
    field = next(f for f in fields if f.get("record_field") == "payload.calculation_conditions.extensions.0")
    assert field["label"] == (custom or "声子方法")


@pytest.mark.parametrize("malformed", [False, True])
def test_worker_entry_keeps_existing_retry_contract(tmp_path, monkeypatch, malformed):
    import json
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.chunker import Chunk
    from backend.ingest.document_parsers import ParserError
    from backend.rag.llm_context import LlmConfig
    raw = raw_with(["DFPT"] if malformed else {"electron_phonon": {"phonon_method": "DFPT"}})
    context = {"file_id": "main", "pages": [{"geometry": {"pdf_page": 1}, "blocks": [
        {"pdf_page": e["pdf_page"], "block_id": e["block_id"], "text": e["quote"]}
        for e in raw["material_states"][0]["property_modules"][0]["records"][0]["evidences"]], "tables": []}]}
    chunk = Chunk(paper_id=0, chunk_index=0, section_name="Methods", heading=None,
                  content=json.dumps(context), token_count=100)
    monkeypatch.setattr(jobs, "_chunk_result_path", lambda *args: tmp_path / "00000.json")
    monkeypatch.setattr("backend.rag.llm_context.get_llm_config", lambda: LlmConfig("test", "http://localhost", "test", "test"))
    monkeypatch.setattr(jobs, "_ensure_not_cancelled", lambda *args: None)
    monkeypatch.setattr("backend.storage.paths.object_mode", lambda: False)
    calls = []
    def complete(system, prompt, **kwargs):
        calls.append(prompt)
        return deepcopy(raw)
    monkeypatch.setattr(jobs, "complete_json", complete)
    if malformed:
        with pytest.raises(ParserError):
            jobs._read_chunk("isolated", chunk, "main", {"kind": "pdf", "parser_profile": "complementary"})
        assert len(calls) == 2 and "extensions" in calls[1]
        assert not (tmp_path / "00000.json").exists()
    else:
        result = jobs._read_chunk("isolated", chunk, "main", {"kind": "pdf", "parser_profile": "complementary"})
        assert conditions(result)["extensions"][0]["value_raw"] == "DFPT"
        assert len(calls) == 1
        assert json.loads((tmp_path / "00000.json").read_text()) == result


@pytest.mark.parametrize("key", ["phonon_method", "calculation_code", "exchange_correlation_functional", "electronic_method", "k_grid"])
def test_unqualified_known_extension_cannot_bypass_software_source_policy(key):
    with pytest.raises(ValueError, match="缺少计算阶段"):
        run(raw_with([{"key": key, "value_kind": "text", "value_raw": "PBE"}]))


@pytest.mark.parametrize("value, expected", [("density functional (linear-response) theory", True), ("DFPT", False)])
def test_source_method_wording_survives_without_granting_unquoted_acronym(value, expected):
    item = {"key": "electron_phonon.phonon_method", "value_kind": "text", "value_raw": value}
    normalized = run(raw_with([item], "Phonons use density functional (linear-response) theory in Quantum ESPRESSO."))
    assert conditions(normalized)["extensions"] == ([item] if expected else [])
