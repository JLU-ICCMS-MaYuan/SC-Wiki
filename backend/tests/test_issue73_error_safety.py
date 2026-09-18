"""#73：使用真实 SDK 解析和假上游验证响应及错误边界，不访问网络。"""

import asyncio
import json
import traceback
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openai import OpenAI, APIStatusError, APIConnectionError

from backend.api import rag
from backend.rag import llm_context, llm
from backend.rag.core import reranker, engine


SECRET = "issue73-synthetic-credential"


@pytest.fixture
def scoped_config():
    token = llm_context.set_llm_config(llm_context.LlmConfig(
        "custom", "https://example.invalid/v1", "test-model", SECRET, True,
    ))
    yield
    llm_context.reset_llm_config(token)


@pytest.mark.parametrize("body,expected", [
    ("<html>gateway</html>", 502),
    ({"error": "unexpected success status"}, 502),
    ({"choices": []}, 502),
    ({"choices": [{"message": {"role": "assistant", "content": None}}]}, 502),
    ({"choices": [{"message": {"role": "assistant", "content": "  "}}]}, 502),
    ({"choices": [{"message": {"role": "assistant", "content": "hello"}}]}, 200),
])
def test_connection_checks_sdk_response(monkeypatch, scoped_config, body, expected):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=body) if isinstance(body, str) else httpx.Response(200, json=body)

    with OpenAI(api_key=SECRET, base_url="https://example.invalid/v1",
                http_client=httpx.Client(transport=httpx.MockTransport(respond))) as sdk:
        monkeypatch.setattr(rag, "get_llm_client", lambda **kwargs: sdk)
        app = FastAPI()
        app.post("/probe")(rag.test_llm_connection)
        with TestClient(app) as client:
            response = client.post("/probe")
        assert response.status_code == expected
        assert SECRET not in response.text
        assert len(requests) == 1
        assert json.loads(requests[0].content)["max_tokens"] == 1


@pytest.mark.parametrize("status", [401, 403])
def test_reranker_auth_failure_is_explicit_and_safe(monkeypatch, scoped_config, capsys, status):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise APIStatusError(SECRET, response=httpx.Response(status, request=httpx.Request(
            "POST", "https://example.invalid/v1")), body={"message": SECRET})

    monkeypatch.setattr(reranker, "get_llm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail))))
    with pytest.raises(llm_context.UserCredentialError) as raised:
        asyncio.run(reranker.rerank_chunks("hello", [{"content": "synthetic"}]))
    assert raised.value.code == "LLM_USER_CREDENTIAL_FAILED"
    assert SECRET not in "".join(traceback.format_exception(raised.value))
    assert SECRET not in capsys.readouterr().out
    assert len(calls) == 1


def test_reranker_non_auth_fallback_does_not_print_upstream(monkeypatch, scoped_config, capsys):
    def fail(**kwargs):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(reranker, "get_llm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail))))
    chunks = [{"content": "synthetic"}]
    assert asyncio.run(reranker.rerank_chunks("hello", chunks)) == chunks
    assert SECRET not in capsys.readouterr().out


@pytest.mark.parametrize("error", [RuntimeError(SECRET), rag.service.RagInternalError(SECRET)])
def test_api_errors_do_not_echo_upstream(monkeypatch, scoped_config, error):
    app = FastAPI()

    @app.get("/failure")
    def fail():
        raise rag._map_internal_error(error)

    with TestClient(app) as client:
        response = client.get("/failure")
    assert response.status_code == 502
    assert SECRET not in response.text


def test_json_retry_log_does_not_echo_upstream(monkeypatch, scoped_config, capsys):
    def fail(*args, **kwargs):
        raise APIConnectionError(message=SECRET, request=httpx.Request("POST", "https://example.invalid"))
    monkeypatch.setattr(llm, "_stream_json", fail)
    with pytest.raises(APIConnectionError):
        llm.complete_json("system", "hello", retries=1)
    assert SECRET not in capsys.readouterr().out


def test_stream_generation_error_does_not_echo_upstream(monkeypatch, scoped_config):
    from backend.rag import database

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, *args):
            return SimpleNamespace(scalar=lambda: 0, scalars=lambda: [])

    async def search(*args, **kwargs):
        return {"chunks": [{"paper_id": 1, "content": "synthetic"}]}

    async def ranked(_question, chunks, **kwargs):
        return chunks

    def fail(**kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(database, "async_session_factory", Session)
    monkeypatch.setattr(engine, "_extract_intent", lambda _: {
        "intent": "mechanism", "question_type": "mechanism", "subjects": [], "predicates": [],
    })
    monkeypatch.setattr(engine, "search_semantic_only", search)
    monkeypatch.setattr(engine, "rerank_chunks", ranked)
    monkeypatch.setattr(engine, "get_llm_client", lambda: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail))))

    async def collect():
        return [event async for event in engine.ask_stream("Why superconductivity?")]

    events = asyncio.run(collect())
    assert SECRET not in json.dumps(events)
    assert "出现错误" in events[-1]["data"]["answer"]
