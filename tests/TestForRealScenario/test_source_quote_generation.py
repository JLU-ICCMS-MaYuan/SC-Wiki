"""#183/#205：现有引句/整块引用规则在生成前闭合，不删响应或增加纠错。"""
from copy import deepcopy
import json
from types import SimpleNamespace

from jsonschema import ValidationError, validate
import pytest


def context():
    return {"file_id": "main", "pages": [{"geometry": {"pdf_page": 1}, "blocks": [
        {"pdf_page": 1, "block_id": "caption", "text": "Original table header."},
        {"pdf_page": 1, "block_id": "empty-table", "text": ""},
        {"pdf_page": 1, "block_id": "cell", "text": "Original cell text."}], "tables": []}]}


def base_schema():
    from backend.ingest.scientific_output_schema import obj, array, quote_schema
    return obj({"evidences": array(quote_schema())})


def evidence():
    return {"file_id": "main", "pdf_page": 1, "block_id": "cell", "quote": None, "quote_id": "cell"}


@pytest.mark.parametrize("mutation", ["empty_parent", "both_modes", "unknown_block", "wrong_file", "wrong_page"])
def test_generation_rejects_existing_backend_forbidden_source_choices(mutation):
    from backend.ingest.scientific_output_schema import bind_extraction_sources
    raw = evidence()
    if mutation == "empty_parent": raw.update(block_id="empty-table", quote_id="empty-table")
    elif mutation == "both_modes": raw["quote"] = "Original cell text."
    elif mutation == "unknown_block": raw.update(block_id="invented", quote_id="invented")
    elif mutation == "wrong_file": raw["file_id"] = "unprovided-file"
    elif mutation == "wrong_page": raw["pdf_page"] = 2
    base = base_schema()
    validate({"evidences": [raw]}, base)  # 旧生成协议允许，后处理却会拒绝。
    bound = bind_extraction_sources(base, context())
    with pytest.raises(ValidationError): validate({"evidences": [raw]}, bound)
    assert base == base_schema()


def test_literal_and_original_block_modes_both_remain_supported():
    from backend.ingest.scientific_output_schema import bind_extraction_sources
    from backend.rag.structured_output import output_format
    source = context(); before = deepcopy(source)
    bound = bind_extraction_sources(base_schema(), source)
    validate({"evidences": [evidence()]}, bound)
    literal = {**evidence(), "quote": "Original cell text.", "quote_id": None}
    validate({"evidences": [literal]}, bound)
    output_format(bound)
    assert source == before and source["pages"][0]["blocks"][1]["block_id"] == "empty-table"


def test_real_read_chunk_passes_source_bound_schema_before_model_call(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs
    from backend.rag import llm_context
    from backend.ingest.scientific_output_schema import bind_extraction_sources
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: SimpleNamespace(
        provider="isolated", model="isolated-model", base_url="https://model.invalid"))
    monkeypatch.setattr(upload_jobs, "_chunk_result_path", lambda *args: tmp_path / "chunk.json")
    class Probed(Exception): pass
    seen = []
    def model(_, content, **kwargs):
        schema = kwargs["response_schema"]
        quote = schema["$defs"]["SourceQuote"]
        bad = {**evidence(), "quote": "Original cell text."}
        with pytest.raises(ValidationError): validate(bad, {"$defs": schema["$defs"], **quote})
        seen.append(schema)
        raise Probed()
    monkeypatch.setattr(upload_jobs, "complete_json", model)
    chunk = SimpleNamespace(chunk_index=0, content=json.dumps(context()), section_name="Document IR", source_page=1)
    with pytest.raises(Probed):
        upload_jobs._read_chunk("a" * 32, chunk, "main", {"kind": "pdf", "parser_profile": "complementary"})
    assert seen


def test_http_failure_after_partial_transport_does_not_relabel_old_response(tmp_path, monkeypatch):
    import httpx
    from openai import APIConnectionError, APIStatusError
    from backend.ingest import upload_jobs
    from backend.rag import llm, llm_context
    cfg = SimpleNamespace(provider="isolated", model="isolated-model", base_url="https://model.invalid")
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: cfg)
    monkeypatch.setattr(llm, "get_llm_config", lambda: cfg)
    monkeypatch.setattr(upload_jobs, "_chunk_result_path", lambda *args: tmp_path / "chunk.json")
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    monkeypatch.setattr(upload_jobs, "complete_json", llm.complete_json)
    attempts = []
    request = httpx.Request("POST", "https://model.invalid")
    def stream(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            kwargs["on_partial"]('{"partial":')
            raise APIConnectionError(request=request)
        raise APIStatusError("unavailable", response=httpx.Response(503, request=request), body=None)
    monkeypatch.setattr(llm, "_stream_json", stream)
    chunk = SimpleNamespace(chunk_index=0, content=json.dumps(context()), section_name="Document IR", source_page=1)
    with pytest.raises(APIStatusError):
        upload_jobs._read_chunk("a" * 32, chunk, "main", {"kind": "pdf", "parser_profile": "complementary"})
    assert len(attempts) == 2
    assert next(tmp_path.rglob("call-1.response.txt")).read_text() == '{"partial":'
    assert not list(tmp_path.rglob("call-2.response.txt"))
    second = json.loads(next(tmp_path.rglob("call-2.json")).read_text())
    assert second["status"] == "failed" and second["status_code"] == 503
