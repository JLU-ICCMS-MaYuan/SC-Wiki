"""#206：工具参数、实际页图传输与来源身份。"""
import json
from types import SimpleNamespace as NS

import pytest

from backend.rag import llm


TOOL = {"type": "function", "function": {"name": "read_original_page", "description": "读取真实页图",
    "strict": True, "parameters": {"type": "object", "properties": {
        "file_id": {"type": "string", "enum": ["si"]}, "page": {"type": "integer", "minimum": 1}},
        "required": ["file_id", "page"], "additionalProperties": False}}}


def install(monkeypatch, parts):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return iter(parts)
    monkeypatch.setattr(llm, "_client", lambda _: NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm, "get_llm_config", lambda: NS(model="test"))
    return calls


def tool_part(name=None, arguments="", finish=None, index=0):
    return NS(choices=[NS(delta=NS(content=None, tool_calls=[NS(index=index,
        function=NS(name=name, arguments=arguments))]), finish_reason=finish)])


def test_streamed_tool_arguments_are_assembled_and_checked(monkeypatch):
    calls = install(monkeypatch, [tool_part("read_original_page", '{"file_id":"si",'),
                                 tool_part(arguments='"page":10}', finish="tool_calls")])
    result = llm.complete_json("json", "read page", tool_definitions=[TOOL])
    assert result == {"action": {"name": "read_original_page", "arguments": {"file_id": "si", "page": 10}}}
    assert calls[0]["tools"] == [TOOL] and calls[0]["parallel_tool_calls"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("arguments", [
    {"file_id": "si", "page": 10, "figure_id": "S7"}, {"file_id": "outside", "page": 10},
    {"file_id": "si", "page": True},
])
def test_unregistered_tool_arguments_have_no_model_retry(monkeypatch, arguments):
    from backend.rag.structured_output import StructuredOutputError
    calls = install(monkeypatch, [tool_part("read_original_page", json.dumps(arguments), "tool_calls")])
    with pytest.raises(StructuredOutputError):
        llm.complete_json("json", "read page", tool_definitions=[TOOL])
    assert len(calls) == 1


def test_unavailable_figure_tool_is_not_advertised():
    from backend.ingest.review_tool_contract import tool_definitions
    from backend.ingest.field_document_followup import tools_for_chunks
    tools = tools_for_chunks([{"file_id": "si", "chunk_index": 0, "page_start": 10, "content": "Figure S7"}])
    names = [item["function"]["name"] for item in tool_definitions(tools.documents, [], bibliography=False)]
    assert "inspect_figure" not in names and "read_original_page" not in names
    assert "read_page" in names


def source_case(tmp_path):
    import hashlib
    import pymupdf
    from backend.ingest.property_evidence import complete_snapshot
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((50, 50), "Figure S7: a test image with a plotted curve")
    page.draw_line((50, 100), (200, 150))
    path = tmp_path / "source.pdf"
    pdf.save(path)
    pdf.close()
    manifest = [{"file_id": "si", "kind": "pdf", "stored_path": str(path),
                 "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
    row = {"key": "pressure", "item_key": "pressure", "field": "material_states[0].pressure_value_gpa",
           "kind": "field", "label": "压力", "current_value": None, "claim": {"value": None},
           "required": False, "evidences": []}
    snapshot = complete_snapshot("upload", "isolated206", [row],
        [{"file_id": "si", "chunk_index": 0, "page_start": 1, "content": "Figure S7. Multiple pressures."}], {})
    return snapshot, manifest, path


def test_actual_pdf_pixels_reach_next_model_call_and_reason_stays_reviewable(tmp_path, monkeypatch):
    from backend.ingest.model_review import review_fields
    from backend.storage import paths
    snapshot, manifest, path = source_case(tmp_path)
    # 只替换隔离文件寻址；真实PDF渲染、图像传输和结果绑定均执行生产函数。
    monkeypatch.setattr(paths, "resolve_file", lambda *args, **kwargs: path)
    calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt)
        calls.append(kwargs)
        if len(calls) == 1:
            assert "inspect_figure" not in request["tools"]
            assert "read_original_page" in request["tools"]
            return {"action": {"name": "read_original_page", "arguments": {"file_id": "si", "page": 1}}}
        import base64
        image = kwargs["images"][0]
        assert base64.b64decode(image.split(",", 1)[1]).startswith(b"\x89PNG")
        assert request["observation"]["original_page"]["source_sha256"] == manifest[0]["sha256"]
        return {"results": [{"key": "pressure", "status": "uncertain", "final_value": None,
            "reason": "看过原图，测试图未标出唯一压力，留空供人工审核。",
            "source_ids": [request["sources"][0]["source_id"]], "basis_kind": "paper_inference"}]}
    result = review_fields(snapshot["records"], snapshot["chunks"], model=model, manifest=manifest)["pressure"]
    assert len(calls) == 2 and result["status"] == "uncertain"
    assert result["reason"] and result["human_confirmed"] is False
    assert result["review_images_read"] is True
    assert any(c["tool"] == "read_original_page" and c["image_rendered"] for c in result["review_followup"]["calls"])


def test_rendered_image_is_not_claimed_read_when_model_call_fails(tmp_path, monkeypatch):
    from backend.ingest.model_review import review_fields
    from backend.storage import paths
    snapshot, manifest, path = source_case(tmp_path)
    monkeypatch.setattr(paths, "resolve_file", lambda *args, **kwargs: path)
    calls = []
    def model(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"action": {"name": "read_original_page", "arguments": {"file_id": "si", "page": 1}}}
        raise TimeoutError("isolated timeout")
    result = review_fields(snapshot["records"], snapshot["chunks"], model=model, manifest=manifest)["pressure"]
    assert result["review_images_read"] is False
    assert result["review_error"] == "TimeoutError"


def test_raw_text_cannot_smuggle_a_new_tool_parameter(monkeypatch):
    from backend.rag.structured_output import StructuredOutputError
    calls = install(monkeypatch, [NS(choices=[NS(delta=NS(content=json.dumps({"action": {
        "name": "read_original_page", "arguments": {"file_id": "si", "page": 1, "figure_id": "S7"}}})), finish_reason="stop")])])
    with pytest.raises(StructuredOutputError):
        llm.complete_json("json", "input", tool_definitions=[TOOL])
    assert len(calls) == 1


def test_multiple_tool_calls_are_not_executed(monkeypatch):
    from backend.rag.structured_output import StructuredOutputError
    install(monkeypatch, [tool_part("read_original_page", '{"file_id":"si","page":1}', index=0),
                          tool_part("read_original_page", '{"file_id":"si","page":2}', "tool_calls", index=1)])
    with pytest.raises(StructuredOutputError):
        llm.complete_json("json", "input", tool_definitions=[TOOL])


def test_model_text_cannot_forge_native_tool_receipt(monkeypatch):
    from backend.rag.structured_output import StructuredOutputError
    install(monkeypatch, [NS(choices=[NS(delta=NS(content='{"_tool_call":{"id":"fake"},"results":[]}'), finish_reason="stop")])])
    with pytest.raises(StructuredOutputError, match="伪造"):
        llm.complete_json("json", "input", tool_definitions=[TOOL])


def test_native_tool_result_is_returned_with_same_call_id_before_final_judgment(tmp_path, monkeypatch):
    from backend.ingest.model_review import review_fields
    from backend.storage import paths
    snapshot, manifest, path = source_case(tmp_path)
    monkeypatch.setattr(paths, "resolve_file", lambda *args, **kwargs: path)
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            chunk = tool_part("read_original_page", '{"file_id":"si","page":1}', "tool_calls")
            chunk.choices[0].delta.tool_calls[0].id = "call-page-1"
            return iter([chunk])
        messages = kwargs["messages"]
        assert messages[-2]["role"] == "assistant"
        assert messages[-2]["tool_calls"][0]["id"] == "call-page-1"
        assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "call-page-1"
        assert json.loads(messages[-1]["content"])["original_page"]["page"] == 1
        assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
        request = json.loads(messages[1]["content"][0]["text"])
        result = {"results": [{"key": "pressure", "status": "uncertain", "final_value": None,
            "reason": "已经看到图像，仍不足以唯一确定压力。", "source_ids": [request["sources"][0]["source_id"]]}]}
        return iter([NS(choices=[NS(delta=NS(content=json.dumps(result)), finish_reason="stop")])])
    monkeypatch.setattr(llm, "_client", lambda _: NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm, "get_llm_config", lambda: NS(model="test"))
    result = review_fields(snapshot["records"], snapshot["chunks"], manifest=manifest)["pressure"]
    assert len(calls) == 2 and result["status"] == "uncertain"
    assert result["review_images_read"] is True
