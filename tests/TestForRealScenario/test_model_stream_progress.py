"""真实空白流故障：沿既有read_timeout终止无进展，保留片段且严格调用不重试。"""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def model_module(monkeypatch):
    candidate = os.environ.get("SCWIKI_STREAM_CANDIDATE")
    if candidate:
        spec = importlib.util.spec_from_file_location("backend.rag._stream_candidate", Path(candidate))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        from backend.rag import llm as module
    monkeypatch.setattr(module, "get_llm_config", lambda: SimpleNamespace(model="isolated-model"))
    return module


def install(monkeypatch, module, entries):
    clock = SimpleNamespace(now=0)
    class Stream:
        closed = False
        def __iter__(self):
            for moment, content in entries:
                clock.now = moment
                delta = SimpleNamespace(content=content) if isinstance(content, str) else content
                yield SimpleNamespace(choices=[SimpleNamespace(
                    delta=delta, finish_reason=getattr(delta, 'finish_reason', None))])
        def close(self):
            self.closed = True
    stream = Stream()
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return stream
    monkeypatch.setattr(module, "_client", lambda _: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(module.time, "monotonic", lambda: clock.now)
    return stream, calls


def test_whitespace_stream_fails_once_preserves_raw_and_closes(monkeypatch, model_module):
    module = model_module
    stream, calls = install(monkeypatch, module, [(1, "{"), (50, " " * 100),
                                                 (100, "\n " * 100), (101, '"ok":1}')])
    partials, receipts = [], []
    from backend.rag.structured_output import StructuredOutputError
    with pytest.raises(StructuredOutputError):
        module.complete_json("JSON", "source", read_timeout=90, retries=2,
            on_partial=partials.append, on_call=receipts.append,
            response_schema={"type": "object", "properties": {"ok": {"type": "integer"}},
                             "required": ["ok"], "additionalProperties": False})
    assert len(calls) == 1 and len(receipts) == 1
    assert receipts[0]["status"] == "failed"
    assert partials[-1] == "{" + " " * 100 + "\n " * 100
    assert stream.closed


def test_real_progress_can_exceed_total_read_timeout(monkeypatch, model_module):
    module = model_module
    stream, calls = install(monkeypatch, module, [(1, "{"), (70, '"ok"'),
        (140, ": "), (210, "1"), (240, "}")])
    assert module.complete_json("JSON", "source", read_timeout=90) == {"ok": 1}
    assert len(calls) == 1 and stream.closed


def test_callback_cancellation_closes_upstream_connection(monkeypatch, model_module):
    module = model_module
    stream, _ = install(monkeypatch, module, [(1, "{")])
    class Cancelled(Exception): pass
    def cancel(_): raise Cancelled()
    with pytest.raises(Cancelled):
        module.complete_json("JSON", "source", on_partial=cancel)
    assert stream.closed


def test_native_tool_arguments_count_as_progress(monkeypatch, model_module):
    module = model_module
    def delta(name, arguments, finish=None):
        return SimpleNamespace(content=None, finish_reason=finish, tool_calls=[SimpleNamespace(
            index=0, id='call-original-page', function=SimpleNamespace(name=name, arguments=arguments))])
    stream, calls = install(monkeypatch, module, [(1, delta('read_original_page', '{')),
        (70, delta('', '"page":')), (140, delta('', '1}')), (141, delta('', '', 'tool_calls'))])
    tools = [{'type': 'function', 'function': {'name': 'read_original_page', 'description': '读取原页',
        'strict': True, 'parameters': {'type': 'object', 'properties': {'page': {'type': 'integer'}},
                                     'required': ['page'], 'additionalProperties': False}}}]
    result = module.complete_json('JSON', 'source', read_timeout=90, tool_definitions=tools)
    assert result['action'] == {'name': 'read_original_page', 'arguments': {'page': 1}}
    assert result['_tool_call']['id'] == 'call-original-page'
    assert len(calls) == 1 and stream.closed
