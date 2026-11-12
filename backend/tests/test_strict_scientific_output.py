"""#205：真实调用边界的字段限制，不新增模型纠错调用。"""
from types import SimpleNamespace as NS

import pytest

from backend.rag import llm


PRESSURE = {"type": "object", "properties": {"pressure_value_gpa": {"type": ["number", "null"]}},
            "required": ["pressure_value_gpa"], "additionalProperties": False}


def client(monkeypatch, text):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return iter([NS(choices=[NS(delta=NS(content=text), finish_reason="stop")])])
    monkeypatch.setattr(llm, "_client", lambda timeout: NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm, "get_llm_config", lambda: NS(model="test"))
    return calls


def test_strict_generation_sends_fixed_schema_without_extra_call(monkeypatch):
    calls = client(monkeypatch, '{"pressure_value_gpa":null}')
    assert llm.complete_json("fixed fields", "uncertain", response_schema=PRESSURE) == {"pressure_value_gpa": None}
    assert len(calls) == 1
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    assert calls[0]["response_format"]["json_schema"]["schema"] == PRESSURE


def test_provider_ignoring_schema_is_rejected_without_model_retry(monkeypatch):
    from backend.rag.structured_output import StructuredOutputError
    calls = client(monkeypatch, '{"pressure_value_gpa":null,"pressure_ambiguity":"unclear"}')
    archived = []
    with pytest.raises(StructuredOutputError):
        llm.complete_json("fixed fields", "uncertain", response_schema=PRESSURE, retries=3, on_partial=archived.append)
    assert len(calls) == 1
    assert "pressure_ambiguity" in archived[-1]


def test_ordinary_json_requests_keep_existing_behavior(monkeypatch):
    calls = client(monkeypatch, '{"description":"existing general caller"}')
    assert llm.complete_json("json", "input")["description"]
    assert calls[0]["response_format"] == {"type": "json_object"}


def test_invalid_local_schema_does_not_call_model(monkeypatch):
    calls = client(monkeypatch, '{}')
    with pytest.raises(ValueError):
        llm.complete_json("json", "input", response_schema={"type": "object"})
    assert calls == []


def _value(schema, root):
    if "$ref" in schema:
        return _value(root["$defs"][schema["$ref"].rsplit("/", 1)[1]], root)
    if "anyOf" in schema:
        return _value(next((s for s in schema["anyOf"] if s.get("type") == "null"), schema["anyOf"][0]), root)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    kind = schema.get("type")
    if kind == "object":
        return {k: _value(v, root) for k, v in schema["properties"].items()}
    return {"array": [], "null": None, "string": "x", "number": 1.0, "integer": 1, "boolean": False}[kind]


def test_filling_uses_existing_reason_and_rejects_added_method_name():
    from backend.ingest.scientific_output_schema import filling_schema
    from backend.rag.structured_output import validate_output, StructuredOutputError
    schema = filling_schema()
    value = _value(schema, schema)
    record = _value(schema['properties']['records']['items'], schema)
    record.pop('method_name', None)
    record['reason'] = '原文及表格支持这两个 Tc／μ* 点属于同一方法；原文写法各自保留。'
    value['records'] = [record]
    validate_output(value, schema)
    record['method_name'] = 'unrequested description'
    with pytest.raises(StructuredOutputError):
        validate_output(value, schema)


@pytest.mark.parametrize("path", [
    ["description"], ["pressure_ambiguity"], ["calculation_conditions", "extensions"],
    ["calculation_conditions", "qe", "invented_cutoff"],
])
def test_nested_scientific_keys_cannot_be_generated_or_accepted(path):
    from backend.ingest.scientific_output_schema import payload_schema, conditions_schema, definitions
    from backend.rag.structured_output import StructuredOutputError, validate_output
    schema = payload_schema() | {"$defs": definitions()}
    value = _value(schema, schema)
    value["calculation_conditions"] = _value(conditions_schema(), schema)
    value["calculation_conditions"]["qe"] = _value(conditions_schema()["properties"]["qe"]["anyOf"][0], schema)
    validate_output(value, schema)
    parent = value
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = "invented"
    with pytest.raises(StructuredOutputError):
        validate_output(value, schema)


def test_manual_extensions_still_work_but_cannot_be_model_created():
    from backend.ingest.fixed_form_contract import validate_conditions
    value = {"extensions": [{"field_key": "human-added", "name_raw": "人工附加参数",
                             "value_kind": "number", "value_number": 2, "value_raw": "2", "origin": "human_input"}]}
    validate_conditions(value)
    with pytest.raises(ValueError, match="模型不能"):
        validate_conditions(value, model_output=True)


def test_decoding_preserves_unknown_pressure_and_never_drops_unknown_keys():
    from backend.ingest.scientific_output_schema import decode_optional_containers
    original = {"pressure_value_gpa": None, "payload": {"parameters": None, "pressure_ambiguity": "invalid"}}
    decoded = decode_optional_containers(original)
    assert decoded["pressure_value_gpa"] is None
    assert decoded["payload"]["pressure_ambiguity"] == "invalid"  # 后续门必须拒绝，不能靠删键通过。
    assert original["payload"]["parameters"] is None


def test_filling_structure_error_keeps_candidates_without_another_call():
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    from backend.rag.structured_output import StructuredOutputError
    states = [{"property_modules": [{"records": [{"property_code": "dos_fermi", "value_number": 0.02234}]}]}]
    calls = []
    def model(*args):
        calls.append(args)
        raise StructuredOutputError("unregistered key")
    result, report = fill_scientific_forms(states, [], model)
    assert result == states and len(calls) == 1
    assert report["stop_reason"] == "invalid_output_structure"
    assert report["attempts"][0]["error_type"] == "StructuredOutputError"


@pytest.mark.parametrize("text", ['not json', '{"pressure_value_gpa":'])
def test_invalid_strict_json_has_no_model_retry(monkeypatch, text):
    from backend.rag.structured_output import StructuredOutputError
    calls = client(monkeypatch, text)
    with pytest.raises(StructuredOutputError):
        llm.complete_json("json", "input", response_schema=PRESSURE)
    assert len(calls) == 1


def test_unsupported_interface_is_not_silently_downgraded(monkeypatch):
    import httpx
    from openai import BadRequestError
    from backend.rag.structured_output import StructuredOutputError
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        raise BadRequestError("unsupported", response=httpx.Response(400, request=httpx.Request("POST", "https://example.invalid")), body={})
    monkeypatch.setattr(llm, "_client", lambda timeout: NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm, "get_llm_config", lambda: NS(model="test"))
    with pytest.raises(StructuredOutputError, match="未降级"):
        llm.complete_json("json", "input", response_schema=PRESSURE)
    assert len(calls) == 1


@pytest.mark.parametrize("candidate", [None, 50])
def test_uncertain_field_keeps_reason_and_requires_human_review(candidate):
    import json
    from backend.ingest.model_review import review_fields
    from backend.ingest.property_evidence import complete_snapshot
    row = {"key": "pressure", "item_key": "pressure", "field": "material_states[0].pressure_value_gpa",
           "kind": "field", "label": "压力", "current_value": None, "claim": {"value": None},
           "required": False, "evidences": []}
    snap = complete_snapshot("upload", "isolated205", [row], [{"file_id": "si", "chunk_index": 0,
        "page_start": 10, "content": "Figure S7 covers tI10 at 50/150 GPa. DOS is 0.02234."}], {})
    calls = []
    def model(_, prompt, **kwargs):
        calls.append(prompt)
        source = json.loads(prompt)["sources"][0]["source_id"]
        return {"results": [{"key": "pressure", "status": "uncertain", "final_value": candidate,
            "reason": "图注涉及多个压力，当前证据不足以唯一确定归属，须人工审核。", "source_ids": [source],
            "basis_kind": "paper_inference", "unique": False}]}
    result = review_fields(snap["records"], snap["chunks"], model=model)["pressure"]
    assert result["status"] == "uncertain" and result["reason"]
    assert result["human_confirmed"] is False and len(calls) == 1
    if candidate is not None:
        assert result["proposal"]["values"][""] == candidate


@pytest.mark.parametrize("extra", [False, True])
def test_real_chunk_entry_passes_schema_archives_response_and_never_retries_keys(monkeypatch, tmp_path, extra):
    import json
    from backend.ingest import upload_jobs
    from backend.ingest.chunker import Chunk
    from backend.ingest.domain_extraction import EXTRACTION_OUTPUT_SCHEMA
    from backend.rag import llm_context
    from backend.rag.structured_output import StructuredOutputError
    from backend.storage import paths
    response = _value(EXTRACTION_OUTPUT_SCHEMA, EXTRACTION_OUTPUT_SCHEMA)
    if extra:
        response["pressure_ambiguity"] = "forbidden"
    calls = client(monkeypatch, json.dumps(response))
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: NS(provider="test", model="test", base_url="https://example.invalid"))
    monkeypatch.setattr(upload_jobs, "_chunk_result_path", lambda *args: tmp_path / "00000.json")
    monkeypatch.setattr(paths, "object_mode", lambda: False)
    chunk = Chunk(paper_id=0, chunk_index=0, section_name="Document IR", heading=None,
                  content=json.dumps({"file_id": "si", "pages": []}), token_count=10)
    call = lambda: upload_jobs._read_chunk("isolated205", chunk, "si", {"kind": "pdf", "parser_profile": "complementary"})
    if extra:
        with pytest.raises(StructuredOutputError):
            call()
        assert not (tmp_path / "00000.json").exists()
        assert "pressure_ambiguity" in next(tmp_path.rglob("response.txt")).read_text()
    else:
        result = call()
        assert result["material_states"] == []
        assert call() == result  # 相同结构与内容命中缓存，不再调用模型。
        archived = json.loads(next(tmp_path.rglob("input.json")).read_text())
        from backend.ingest.scientific_output_schema import constrain_extraction_records
        assert archived["response_schema"] == constrain_extraction_records(EXTRACTION_OUTPUT_SCHEMA)
    assert len(calls) == 1


def test_record_generation_rejects_unpaired_custom_but_keeps_standard_and_thermal_cases():
    from copy import deepcopy
    from backend.ingest.domain_extraction import EXTRACTION_OUTPUT_SCHEMA
    from backend.ingest.scientific_output_schema import constrain_extraction_records
    from backend.rag.structured_output import validate_output,StructuredOutputError
    base=EXTRACTION_OUTPUT_SCHEMA;before=deepcopy(base)
    projected=constrain_extraction_records(base)
    row=_value(base['$defs']['ExtractedRecord'],base)
    row['evidences']=[{'file_id':'fixture','pdf_page':1,'block_id':'block','quote':'synthetic type fixture','quote_id':None}]
    def check(value,schema):validate_output(value,{'$ref':'#/$defs/ExtractedRecord','$defs':schema['$defs']})
    check(row,projected)
    bad=deepcopy(row);bad.update(property_code='custom',module_code='superconductive_properties')
    check(bad,base)
    with pytest.raises(StructuredOutputError):check(bad,projected)
    thermal=deepcopy(bad);thermal['module_code']='thermodynamical_properties'
    value=base['$defs']['ExtractedRecord']['properties']['payload']['properties']['thermodynamic_stability']['anyOf'][0]
    thermal['payload']['thermodynamic_stability']=_value(value,base)
    check(thermal,projected)
    assert base==before


def test_original_bad_payload_is_rejected_without_mutating_it():
    from copy import deepcopy
    from backend.ingest.scientific_output_schema import payload_schema, definitions
    from backend.rag.structured_output import validate_output, StructuredOutputError
    raw = {"description": "Reported DOS of tI10-CaH4 at the Fermi level.",
           "pressure_ambiguity": "The caption lists 50/150 GPa for tI10-CaH4 but does not tie the scalar to either pressure."}
    before = deepcopy(raw)
    with pytest.raises(StructuredOutputError):
        validate_output(raw, payload_schema() | {"$defs": definitions()})
    assert raw == before
