"""#170：真实SDK用量回执到任务状态、公开读取与快照恢复。"""
import json
from contextlib import nullcontext
from copy import deepcopy

import httpx
import pytest
from openai import OpenAI

from backend.ingest import upload_contracts, upload_tasks, scientific_evidence
from backend.rag import llm
from test_upload_extraction_timing import MemoryRedis


@pytest.fixture
def stored_task(monkeypatch, tmp_path):
    client = MemoryRedis()
    snapshots = []
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    monkeypatch.setattr(upload_tasks, "authoritative_state", lambda *args: None)
    monkeypatch.setattr(upload_tasks, "upload_task_lock", lambda _: nullcontext())
    monkeypatch.setattr(upload_tasks, "artifact_directory", lambda _: tmp_path)
    monkeypatch.setattr(scientific_evidence, "persist_upload_state",
                        lambda _, state: snapshots.append(deepcopy(state)))
    task = upload_tasks.create_task(7, filename="paper.pdf", file_kind="pdf")
    upload_tasks.update_state(task["task_id"], status="extracting")
    return task["task_id"], client, snapshots


def install_streams(monkeypatch, scripts):
    """仅隔离HTTP传输，保留OpenAI序列化、SSE解码与生产JSON校验。"""
    seen = []
    def respond(request):
        seen.append(json.loads(request.content))
        outcome = scripts[len(seen) - 1]
        if isinstance(outcome, int):
            return httpx.Response(outcome, json={"error": {"code": "service_unavailable", "message": "isolated"}})
        content, usage = outcome
        chunks = [{"id": "isolated", "object": "chat.completion.chunk", "choices": [
            {"index": 0, "delta": {"content": content}, "finish_reason": "stop"}]}]
        if usage is not None:
            chunks.append({"id": "isolated", "object": "chat.completion.chunk", "choices": [], "usage": usage})
        body = "".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)
    monkeypatch.setattr(llm, "_client", lambda _: OpenAI(api_key="isolated-test",
        base_url="https://model.invalid/v1", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond))))
    return seen


def test_sdk_usage_is_aggregated_and_public_after_ready(stored_task, monkeypatch):
    from backend.ingest.upload_usage import collect_upload_usage
    task_id, client, snapshots = stored_task
    seen = install_streams(monkeypatch, [('{"value":1}', {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200}),
        ('{"value":2}', {"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600})])
    with collect_upload_usage(task_id):
        assert llm.complete_json("fixed", "main") == {"value": 1}
        with llm.call_phase("automatic_spectra"):
            assert llm.complete_json("fixed", "spectrum") == {"value": 2}
    upload_tasks.update_state(task_id, status="ready")
    public = upload_contracts.public_task_state(upload_tasks.get_state(task_id))
    usage = public["extraction_token_usage"]
    assert (usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]) == (1500, 300, 1800)
    assert usage["request_count"] == usage["recorded_requests"] == 2
    assert snapshots[-1]["extraction_token_usage"] == usage
    assert json.loads(client.values[upload_tasks.task_key(task_id)])["extraction_token_usage"] == usage
    assert "_extraction_token_requests" not in public
    assert "_token_usage_event" not in public
    assert all(request["stream_options"]["include_usage"] for request in seen)
    upload_tasks.update_state(task_id, draft_saved=True)
    assert upload_tasks.get_state(task_id)["extraction_token_usage"] == usage


def test_invalid_json_still_counts_returned_usage_and_missing_is_not_zero(stored_task, monkeypatch):
    from backend.ingest.upload_usage import collect_upload_usage
    task_id, _, _ = stored_task
    install_streams(monkeypatch, [('not-json', {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
                                ('{"value":2}', None)])
    with collect_upload_usage(task_id):
        with pytest.raises(RuntimeError):
            llm._complete_json("fixed", "bad", _single_attempt=True)
        llm.complete_json("fixed", "missing")
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["total_tokens"] == 15
    assert usage["request_count"] == 2 and usage["recorded_requests"] == 1


def test_pause_resume_keeps_usage_and_new_retry_rejects_old_receipt(stored_task):
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag.token_usage import token_request
    task_id, _, _ = stored_task
    with collect_upload_usage(task_id):
        with token_request() as record:
            record({"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    first = deepcopy(upload_tasks.get_state(task_id)["extraction_token_usage"])
    upload_tasks.update_state(task_id, status="paused")
    upload_tasks.update_state(task_id, status="queued", resume=True)
    upload_tasks.update_state(task_id, status="extracting")
    assert upload_tasks.get_state(task_id)["extraction_token_usage"] == first
    with collect_upload_usage(task_id), token_request() as record:
        upload_tasks.update_state(task_id, status="failed")
        upload_tasks.update_state(task_id, status="queued", retry=True)
        record({"input_tokens": 100, "output_tokens": 50, "total_tokens": 150})
    current = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert current["run_id"] != first["run_id"]
    assert current["request_count"] == current["total_tokens"] == 0


def test_request_finish_is_idempotent_and_legacy_remains_missing(stored_task):
    task_id, _, _ = stored_task
    run_id = upload_tasks.get_state(task_id)["extraction_token_usage"]["run_id"]
    event = {"run_id": run_id, "request_id": "same", "kind": "started"}
    upload_tasks.update_state(task_id, _token_usage_event=event)
    upload_tasks.update_state(task_id, _token_usage_event=event)
    event = {**event, "kind": "finished", "usage": {"input_tokens": 10, "output_tokens": 5}}
    upload_tasks.update_state(task_id, _token_usage_event=event)
    upload_tasks.update_state(task_id, _token_usage_event=event)
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["request_count"] == usage["recorded_requests"] == 1
    assert usage["total_tokens"] == 15
    old = upload_contracts.apply_state_changes({"status": "reading"}, now=10, _token_usage_event=event)
    assert "extraction_token_usage" not in old and "_token_usage_event" not in old


@pytest.mark.parametrize("receipt", [None, {}, {"input_tokens": -1, "output_tokens": 2},
    {"input_tokens": True, "output_tokens": 2}, {"input_tokens": 2.5, "output_tokens": 2},
    {"input_tokens": 2, "output_tokens": 1, "total_tokens": 99}])
def test_invalid_or_missing_receipt_stays_unknown(stored_task, receipt):
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag.token_usage import token_request
    task_id, _, _ = stored_task
    with collect_upload_usage(task_id), token_request() as record:
        record(receipt)
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["request_count"] == 1 and usage["recorded_requests"] == 0


def test_snapshot_restores_usage_and_private_deduplication(sqlite_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend import database, models
    from backend.ingest.upload_usage import new_extraction_token_usage
    client = MemoryRedis()
    sessions = sessionmaker(bind=sqlite_engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    task_id = "d" * 32
    state = {"task_id": task_id, "status": "ready", "user_id": 7,
             "extraction_token_usage": {**new_extraction_token_usage(), "input_tokens": 10,
                 "output_tokens": 5, "total_tokens": 15, "request_count": 1, "recorded_requests": 1},
             "_extraction_token_requests": {"original": "recorded"}}
    with sessions.begin() as db:
        db.add(models.ScientificUploadDraft(task_id=task_id, owner_id=7, state=state, draft={}))
    restored = upload_tasks.get_state(task_id)
    assert restored["extraction_token_usage"] == state["extraction_token_usage"]
    assert restored["_extraction_token_requests"] == state["_extraction_token_requests"]


def test_worker_wrapper_records_main_and_automatic_spectrum_requests(stored_task, monkeypatch, tmp_path):
    from backend.ingest import upload_jobs, model_runtime, document_run_metadata, document_shadow
    from backend.rag.llm_context import LlmConfig
    task_id, _, _ = stored_task
    upload_tasks.update_state(task_id, status="queued")
    monkeypatch.setattr(upload_jobs, "load_llm_config", lambda _: LlmConfig(
        "fixture", "https://model.invalid/v1", "fixture", "isolated"))
    monkeypatch.setattr(upload_jobs, "delete_llm_config", lambda _: None)
    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path)
    monkeypatch.setattr(document_run_metadata, "save_run_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(document_shadow, "refresh_comparison", lambda _: None)
    monkeypatch.setattr(model_runtime.ModelRuntime, "wait", lambda self, _: self.check())
    seen = install_streams(monkeypatch, [('{"value":1}', {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ('{"value":2}', {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30})])
    def process(task_id):
        upload_tasks.update_state(task_id, status="extracting")
        assert llm.complete_json("fixed", "main") == {"value": 1}
        with llm.call_phase("automatic_spectra"):
            assert llm.complete_json("fixed", "spectrum") == {"value": 2}
        return upload_tasks.update_state(task_id, status="ready")
    monkeypatch.setattr(upload_jobs, "_process_upload_task", process)
    result = upload_jobs.process_upload_task(task_id)
    assert len(seen) == 2
    assert result["extraction_token_usage"]["total_tokens"] == 45
    assert result["extraction_token_usage"]["recorded_requests"] == 2


def test_summary_and_checkpoint_replay_count_only_one_request(stored_task, monkeypatch, tmp_path):
    from backend.ingest.model_runtime import ModelRuntime, execution_context
    from backend.ingest.model_memory import compact_history
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag import llm_client
    from langchain_core.messages import AIMessage
    from types import SimpleNamespace
    task_id, _, _ = stored_task
    upload_tasks.update_state(task_id, execution_generation=1)
    calls = []
    class Model:
        root_client = SimpleNamespace(close=lambda: None)
        def bind(self, **kwargs):
            return self
        def invoke(self, prompt):
            calls.append(prompt)
            return AIMessage(content="旧过程已完成，保留当前原文", usage_metadata={
                "input_tokens": 100, "output_tokens": 20, "total_tokens": 120})
    monkeypatch.setattr(llm_client, "get_langchain_llm", lambda **kwargs: Model())
    def runtime():
        return ModelRuntime(task_id, 1, tmp_path / "runtime", lambda: upload_tasks.get_state(task_id),
            lambda **changes: upload_tasks.update_state(task_id, **changes), lambda: nullcontext(), identity={"model": "fixture"})
    history = []
    for i in range(5):
        history += [{"role": "assistant", "content": None, "tool_calls": [{"id": f"t{i}", "type": "function",
            "function": {"name": "read_page", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": f"t{i}", "content": "old operation " * 100}]
    with execution_context(runtime()), collect_upload_usage(task_id):
        first = compact_history(history, tmp_path / "first.json", budget=1000)
    before = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert before["total_tokens"] == 120 and before["request_count"] == before["recorded_requests"] == 1
    with execution_context(runtime()), collect_upload_usage(task_id):
        second = compact_history(history, tmp_path / "second.json", budget=1000)
    assert first == second and len(calls) == 1
    assert upload_tasks.get_state(task_id)["extraction_token_usage"] == before


def test_old_execution_receipt_cannot_complete_pending_request(stored_task, tmp_path):
    from backend.ingest.model_runtime import ModelRuntime, execution_context
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag.token_usage import token_request
    task_id, _, _ = stored_task
    upload_tasks.update_state(task_id, execution_generation=1)
    runtime = ModelRuntime(task_id, 1, tmp_path, lambda: upload_tasks.get_state(task_id),
        lambda **changes: upload_tasks.update_state(task_id, **changes), lambda: nullcontext(), identity={})
    with execution_context(runtime), collect_upload_usage(task_id), token_request() as record:
        upload_tasks.update_state(task_id, execution_generation=2, status="paused")
        record({"input_tokens": 100, "output_tokens": 20})
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["request_count"] == 1 and usage["recorded_requests"] == 0


def test_direct_spectrum_vision_counts_usage_even_when_result_is_rejected(stored_task, monkeypatch):
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag import llm_client
    from backend.spectra.vision import complete_image_json
    task_id, _, _ = stored_task
    def respond(request):
        return httpx.Response(200, json={"id": "vision", "object": "chat.completion", "created": 0,
            "model": "fixture", "choices": [{"index": 0, "message": {"role": "assistant", "content": "bad-json"},
                "finish_reason": "stop"}], "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}})
    monkeypatch.setattr(llm_client, "get_llm_client", lambda **kwargs: OpenAI(api_key="isolated",
        http_client=httpx.Client(transport=httpx.MockTransport(respond))))
    with collect_upload_usage(task_id), pytest.raises(RuntimeError):
        complete_image_json("fixed", "read", images=["data:image/png;base64,isolated"])
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["total_tokens"] == 10 and usage["recorded_requests"] == 1


def test_native_responses_pdf_usage_is_counted_before_validation(stored_task, tmp_path):
    import pymupdf
    from backend.ingest.native_pdf import parse_native_pdf
    from backend.ingest.document_parsers import DocumentSource, ParseOptions
    from backend.ingest.upload_usage import collect_upload_usage
    from backend.rag.llm_context import LlmConfig
    task_id, _, _ = stored_task
    path = tmp_path / "isolated.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((20, 30), "isolated transcription")
        pdf.save(path)
    def respond(request):
        return httpx.Response(200, json={"id": "resp-isolated", "object": "response", "created_at": 0,
            "model": "fixture-pdf", "status": "completed", "output": [{"id": "msg", "type": "message",
                "role": "assistant", "status": "completed", "content": [{"type": "output_text", "annotations": [],
                "text": '{"blocks":[{"pdf_page":1,"block_type":"paragraph","text":"isolated transcription","bbox":null,"estimated":false}]}'}]}],
            "usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15}})
    def factory(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    with collect_upload_usage(task_id):
        ir = parse_native_pdf(DocumentSource(path, "file"), ParseOptions(profile="native_pdf_llm"),
            config=LlmConfig("fixture", "https://api.openai.com/v1", "fixture-pdf", "isolated"),
            allowed_models=["fixture-pdf"], client_factory=factory)
    assert ir.blocks[0].text == "isolated transcription"
    usage = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert usage["total_tokens"] == 15 and usage["recorded_requests"] == 1


def test_retry_counts_each_physical_attempt_but_checkpoint_replay_adds_nothing(stored_task, monkeypatch, tmp_path):
    from backend.ingest.model_runtime import ModelRuntime, execution_context
    from backend.ingest.upload_usage import collect_upload_usage
    task_id, _, _ = stored_task
    upload_tasks.update_state(task_id, execution_generation=1)
    seen = install_streams(monkeypatch, [503, ('{"value":42}', {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})])
    def runtime():
        instance = ModelRuntime(task_id, 1, tmp_path / "checkpoint", lambda: upload_tasks.get_state(task_id),
            lambda **changes: upload_tasks.update_state(task_id, **changes), lambda: nullcontext(), identity={"model": "fixture"})
        instance.wait = lambda _: instance.check()
        return instance
    with execution_context(runtime()), collect_upload_usage(task_id):
        assert llm.complete_json("fixed", "source") == {"value": 42}
    before = upload_tasks.get_state(task_id)["extraction_token_usage"]
    assert len(seen) == before["request_count"] == 2
    assert before["recorded_requests"] == 1 and before["total_tokens"] == 15
    with execution_context(runtime()), collect_upload_usage(task_id):
        assert llm.complete_json("fixed", "source") == {"value": 42}
    assert len(seen) == 2 and upload_tasks.get_state(task_id)["extraction_token_usage"] == before
