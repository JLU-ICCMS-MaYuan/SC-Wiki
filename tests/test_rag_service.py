"""RAG 服务边界：依赖状态、Mentor 路由和错误契约，不连接外部服务。"""

from types import SimpleNamespace

import pytest

from backend.rag import service


def _health_dependencies(monkeypatch, *, database=True, qdrant=True, api_key="test"):
    monkeypatch.setattr(service, "get_rag_settings", lambda: SimpleNamespace(
        database_available=database, qdrant_host="unused", qdrant_port=6333,
    ))
    monkeypatch.setattr(service, "get_llm_config", lambda: SimpleNamespace(
        api_key=api_key, provider="test", model="test-model",
    ))
    import qdrant_client

    class Client:
        def __init__(self, **kwargs):
            pass

        def get_collections(self):
            if not qdrant:
                raise RuntimeError("unavailable")
            return []

    monkeypatch.setattr(qdrant_client, "QdrantClient", Client)


@pytest.mark.parametrize("database,qdrant", [(False, True), (True, False)])
def test_health_reports_missing_dependencies(monkeypatch, database, qdrant):
    _health_dependencies(monkeypatch, database=database, qdrant=qdrant)
    assert service.health()["available"] is False


def test_health_reports_search_without_llm(monkeypatch):
    _health_dependencies(monkeypatch, api_key="")
    status = service.health()
    assert status["available"] is True
    assert status["qdrant_available"] is True
    assert status["chat_available"] is False


@pytest.mark.asyncio
async def test_search_rejects_unavailable_database(monkeypatch):
    _health_dependencies(monkeypatch, database=False)
    with pytest.raises(service.RagDataUnavailableError):
        await service.search("LaH10")


@pytest.mark.asyncio
async def test_chat_rejects_missing_llm(monkeypatch):
    _health_dependencies(monkeypatch, api_key="")
    with pytest.raises(service.RagChatUnavailableError):
        await service.chat("LaH10 的 Tc？")


@pytest.mark.asyncio
async def test_chat_and_stream_share_mentor_and_history(monkeypatch):
    from backend.rag.agent import mentor
    _health_dependencies(monkeypatch)
    calls = []

    async def fake_run_stream(question, prev_messages=None):
        calls.append((question, prev_messages))
        yield {"type": "token", "data": "回答"}
        yield {"type": "done", "data": {"answer": "回答"}}

    monkeypatch.setattr(mentor, "run_stream", fake_run_stream)
    history = [{"role": "user", "content": "上一问"}]
    answer = await service.chat("继续", history=history)
    events = [event async for event in service.chat_stream("继续", history=history)]
    assert answer == events[-1]["data"]
    assert answer["provider"] == "test"
    assert [c[0] for c in calls] == ["继续", "继续"]
    assert all(c[1][0].content == "上一问" for c in calls)


@pytest.mark.asyncio
async def test_chat_rejects_missing_completion(monkeypatch):
    async def unfinished(*args, **kwargs):
        yield {"type": "token", "data": "半句"}
    monkeypatch.setattr(service, "chat_stream", unfinished)
    with pytest.raises(service.RagInternalError, match="完成"):
        await service.chat("问题")
