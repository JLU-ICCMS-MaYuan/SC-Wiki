"""使用真实 SDK 与隔离 HTTP 边界验证 Embedding 分批和文本对应关系。"""

import json
from types import SimpleNamespace

import httpx
from openai import OpenAI
import pytest

from backend.ingest import embedder
from backend.rag.config import RagSettings


def configure(monkeypatch, handler, *, dimensions=2):
    monkeypatch.setattr(embedder, "settings", SimpleNamespace(
        embedding_key="test-private-key", embedding_url="https://embedding.invalid/v1",
        embedding_model="text-embedding-v4", embedding_dimensions=dimensions,
        embedding_batch_size=10,
    ))
    monkeypatch.setattr(embedder, "OpenAI", lambda **kwargs: OpenAI(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ))


def response(vectors):
    return httpx.Response(200, json={
        "object": "list", "model": "text-embedding-v4", "data": vectors,
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    })


def test_batches_preserve_input_order_and_explicit_dimensions(monkeypatch):
    sizes = []

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/embeddings"
        assert body["dimensions"] == 2
        assert body["model"] == "text-embedding-v4"
        sizes.append(len(body["input"]))
        return response([
            {"object": "embedding", "index": i, "embedding": [float(t), 1.0]}
            for i, t in reversed(list(enumerate(body["input"])))
        ])

    configure(monkeypatch, handler)
    assert embedder.embed_texts([str(i) for i in range(23)]) == [[float(i), 1.0] for i in range(23)]
    assert sizes == [10, 10, 3]


def test_unset_dimensions_are_omitted_and_empty_input_does_not_call(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        assert "dimensions" not in body
        calls.append(body)
        return response([{"object": "embedding", "index": 0, "embedding": [1.0, 2.0, 3.0]}])

    configure(monkeypatch, handler, dimensions=None)
    assert embedder.embed_texts([]) == []
    assert not calls
    assert embedder.embed_texts(["测试"]) == [[1.0, 2.0, 3.0]]


@pytest.mark.parametrize("vectors", [
    [],
    [{"index": 1, "embedding": [1.0, 2.0]}],
    [{"index": 0, "embedding": [1.0]}],
    [{"index": 0, "embedding": []}],
])
def test_invalid_response_never_reaches_index(monkeypatch, vectors):
    configure(monkeypatch, lambda _: response(vectors))
    writes = []
    monkeypatch.setattr(embedder, "index_chunks", lambda *args: writes.append(args))
    with pytest.raises(RuntimeError, match="Embedding"):
        embedder.embed_and_index_chunks([{"content": "测试"}])
    assert not writes


def test_failure_in_later_batch_does_not_partially_index_or_leak_key(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return response([{"index": i, "embedding": [1.0, 2.0]} for i in range(10)])
        return httpx.Response(401, json={"error": {"message": "test-private-key", "type": "auth_error"}})

    configure(monkeypatch, handler)
    writes = []
    monkeypatch.setattr(embedder, "index_chunks", lambda *args: writes.append(args))
    with pytest.raises(RuntimeError) as exc:
        embedder.embed_and_index_chunks([{"content": "测试"}] * 11)
    assert "test-private-key" not in str(exc.value)
    assert len(calls) == 2
    assert not writes


@pytest.mark.parametrize("values", [{"embedding_batch_size": 0}, {"embedding_dimensions": 0}])
def test_invalid_configuration_is_rejected(values):
    with pytest.raises(ValueError):
        RagSettings(_env_file=None, **values)
