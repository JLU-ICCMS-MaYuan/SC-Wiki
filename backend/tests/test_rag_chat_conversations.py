"""RAG 云端会话的真实数据库事务与所有权边界。"""

import os
import json

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models import Base, RagChatConversation, RagChatTurn, User
from backend.services import rag_chat_conversations as chats


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[User.__table__, RagChatConversation.__table__, RagChatTurn.__table__])
    with Session(engine) as session:
        session.add_all([
            User(id=1, email="a@example.org", username="researcher_a", password_hash="x", real_name="A"),
            User(id=2, email="b@example.org", username="researcher_b", password_hash="x", real_name="B"),
        ])
        session.commit()
        yield session
    engine.dispose()


def test_owner_isolation_and_completed_turn(db):
    conversation = chats.create(db, 1)
    with pytest.raises(chats.ConversationNotFound):
        chats.detail(db, 2, conversation["id"])
    assert chats.prepare(db, 1, conversation["id"], "req-1", 0)["history"] == []

    result = chats.complete(db, 1, conversation["id"], "req-1", 0, "LaH10 的 Tc?", "见 [PID_7]", {
        "citations": [{"paper_id": 7, "attribution": "论文直接报告"}],
        "papers": {"7": {"title": "Paper"}},
        "api_key": "must-not-be-stored",
    })
    assert result["sequence"] == 1
    assert chats.detail(db, 1, conversation["id"])["turns"][0]["answer"] == "见 [PID_7]"
    assert "api_key" not in str(chats.detail(db, 1, conversation["id"])["turns"])
    assert chats.prepare(db, 1, conversation["id"], "req-1", 0)["completed"]["sequence"] == 1
    with pytest.raises(chats.ConversationNotFound):
        chats.delete(db, 2, conversation["id"])


def test_conflict_does_not_overwrite_and_import_is_idempotent(db):
    conversation = chats.create(db, 1)
    chats.complete(db, 1, conversation["id"], "req-1", 0, "Q1", "A1", {})
    with pytest.raises(chats.ConversationConflict):
        chats.prepare(db, 1, conversation["id"], "req-2", 0)
    with pytest.raises(chats.ConversationConflict):
        chats.complete(db, 1, conversation["id"], "req-2", 0, "Q2", "A2", {})
    assert len(chats.detail(db, 1, conversation["id"])["turns"]) == 1

    messages = [{"role": "user", "content": "old Q"}, {"role": "assistant", "content": "old A"}]
    first = chats.import_local(db, 1, "old-1", "旧会话", messages)
    second = chats.import_local(db, 1, "old-1", "旧会话", messages)
    assert first["id"] == second["id"]
    assert len(chats.list_for_user(db, 1)) == 2
    assert chats.list_for_user(db, 2) == []
    with pytest.raises(ValueError):
        chats.import_local(db, 1, "too-long", "旧会话", [{"role": "user", "content": "x" * 1001}])
    assert len(chats.list_for_user(db, 1)) == 2


def test_polish_preserves_scientific_values_without_writing_history(monkeypatch, db):
    from backend.rag import service

    class Response:
        choices = [type("Choice", (), {"finish_reason": "stop", "message": type("Message", (), {
            "content": "请列出 LaH10 在 200 GPa 下的 Tc，注明论文来源。",
        })()})()]

    class Client:
        chat = type("Chat", (), {"completions": type("Completions", (), {
            "create": staticmethod(lambda **kwargs: Response()),
        })()})()

    monkeypatch.setattr(service, "get_llm_client", lambda **kwargs: Client())
    monkeypatch.setattr(service, "get_llm_config", lambda: type("Config", (), {"model": "test", "api_key": "fake"})())
    assert "LaH10" in service.polish_prompt("LaH10 200 GPa Tc?")
    assert chats.list_for_user(db, 1) == []

    class BadResponse:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": "只说答案"})()})()]

    Client.chat.completions.create = lambda **kwargs: BadResponse()
    with pytest.raises(ValueError):
        service.polish_prompt("LaH10 200 GPa Tc?")
    with pytest.raises(ValueError):
        service.polish_prompt("   ")

    class LongResponse:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": "LaH10 200 GPa Tc " * 150})()})()]

    Client.chat.completions.create = lambda **kwargs: LongResponse()
    with pytest.raises(ValueError):
        service.polish_prompt("LaH10 200 GPa Tc?")
    monkeypatch.setattr(service, "get_llm_config", lambda: type("Config", (), {"model": "test", "api_key": ""})())
    with pytest.raises(service.RagChatUnavailableError):
        service.polish_prompt("LaH10 200 GPa Tc?")


@pytest.fixture
def polish_api(monkeypatch, db):
    """实际 HTTP 路由、线程上下文与 SDK，只替换外部模型的 HTTP 传输。"""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-only-for-isolated-tests")
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from openai import OpenAI
    from backend.api import rag
    from backend.rag import service, llm_context

    state = {"content": "请比较 LaH10 在 200 GPa 下的 Tc，并说明证据来源。",
             "finish_reason": "stop", "requests": [], "status": 200}

    def upstream(request):
        state["requests"].append(json.loads(request.content))
        if state.get("timeout"):
            raise httpx.ReadTimeout("private-upstream-key", request=request)
        return httpx.Response(state["status"], json={
            "id": "polish-test", "object": "chat.completion", "created": 0, "model": "chosen-model",
            "choices": [{"index": 0, "finish_reason": state["finish_reason"],
                         "message": {"role": "assistant", "content": state["content"],
                                     "refusal": state.get("refusal"), "tool_calls": state.get("tool_calls")}}],
        })

    config = llm_context.LlmConfig(provider="test", base_url="https://model.test/v1", model="chosen-model", api_key="fake")

    async def selected_config():
        token = llm_context.set_llm_config(config)
        try:
            yield config
        finally:
            llm_context.reset_llm_config(token)

    with httpx.Client(transport=httpx.MockTransport(upstream)) as http:
        sdk = OpenAI(api_key="fake", base_url=config.base_url, http_client=http, max_retries=0)
        monkeypatch.setattr(service, "get_llm_client", lambda **kwargs: sdk)
        app = FastAPI()
        app.include_router(rag.router)
        app.dependency_overrides[llm_context.request_llm_config] = selected_config
        with TestClient(app) as client:
            yield client, state
    assert db.query(RagChatConversation).count() == 0
    assert db.query(RagChatTurn).count() == 0


def test_polish_http_uses_selected_model_and_preserves_contract(polish_api):
    client, state = polish_api
    result = client.post("/api/rag/prompts/polish", json={"draft": "LaH10 200 GPa Tc?"})
    assert result.status_code == 200
    assert result.json() == {"ok": True, "data": {"suggestion": state["content"]}}
    request = state["requests"][0]
    assert request["model"] == "chosen-model"
    assert request["max_tokens"] == 4096
    assert json.loads(request["messages"][1]["content"])["originalPrompt"] == "LaH10 200 GPa Tc?"


@pytest.mark.parametrize("change", [
    {"finish_reason": "length"}, {"finish_reason": None}, {"content": "  "},
    {"content": None}, {"content": "问" * 1001}, {"content": "LaH10 1200 GPa Tc?"},
    {"refusal": "不能提供"},
    {"finish_reason": "tool_calls", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "search", "arguments": "{}"}}]},
])
def test_polish_http_rejects_invalid_generation(polish_api, change):
    client, state = polish_api
    state.update(change)
    result = client.post("/api/rag/prompts/polish", json={"draft": "LaH10 200 GPa Tc?"})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "POLISH_INVALID"


@pytest.mark.parametrize("draft", ["", " \n ", "问" * 1001])
def test_polish_http_rejects_invalid_input_before_call(polish_api, draft):
    client, state = polish_api
    assert client.post("/api/rag/prompts/polish", json={"draft": draft}).status_code == 422
    assert state["requests"] == []


def test_polish_unicode_limit_matches_chat_input(polish_api):
    from backend.api.rag import RagChatRequest
    client, state = polish_api
    state["content"] = "𠮷" * 1000
    result = client.post("/api/rag/prompts/polish", json={"draft": "问" * 1000})
    assert result.status_code == 200
    assert RagChatRequest(question=result.json()["data"]["suggestion"]).question == state["content"]


@pytest.mark.parametrize("term", ["FeSe", "MgB2", "H₃S", "0–9", "-0.10", "1e-3", "GPa", "Tc(P)", "K", "°C", "λ", "ω_log", "μ*", "0.10", "{{material_a}}", "10.1234/example", "[PID_12]"])
def test_polish_preserves_scientific_tokens_next_to_chinese(polish_api, term):
    client, state = polish_api
    draft = f"请解释{term}的含义。"
    state["content"] = f"请说明{term}的含义及适用条件。"
    assert client.post("/api/rag/prompts/polish", json={"draft": draft}).status_code == 200
    state["content"] = "请说明含义及适用条件。"
    assert client.post("/api/rag/prompts/polish", json={"draft": draft}).status_code == 422


def test_polish_rejects_changed_sign_and_exponent(polish_api):
    client, state = polish_api
    for draft, changed in [("参数=-0.10", "参数=0.10"), ("误差1e-3", "误差1e3")]:
        state["content"] = changed
        assert client.post("/api/rag/prompts/polish", json={"draft": draft}).status_code == 422


@pytest.mark.parametrize("change", [{"timeout": True}, {"status": 401}])
def test_polish_upstream_failure_is_sanitized(polish_api, change):
    client, state = polish_api
    state.update(change)
    result = client.post("/api/rag/prompts/polish", json={"draft": "低压超导研究思路"})
    assert result.status_code == 502
    assert "private-upstream-key" not in result.text
    assert len(state["requests"]) == 1


def test_stream_uses_server_history_and_enforces_owner(monkeypatch, db):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-only-for-isolated-tests")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api import rag
    from backend.database import get_db
    from backend.rag import llm_context
    from backend.security import get_current_user, get_current_user_optional

    sessions = sessionmaker(bind=db.bind)
    monkeypatch.setattr(rag, "SessionLocal", sessions)
    seen_history = []

    async def fake_stream(question, **kwargs):
        seen_history.append(kwargs["history"])
        yield {"type": "token", "data": "回答"}
        yield {"type": "done", "data": {"answer": "回答", "citations": []}}

    monkeypatch.setattr(rag.service, "chat_stream", fake_stream)
    async def allow_test_catalog_user(request):
        return None
    monkeypatch.setattr(llm_context, "require_catalog_user", allow_test_catalog_user)
    app = FastAPI()
    app.include_router(rag.router)

    def test_db():
        with sessions() as session:
            yield session

    owner = {"id": 1}
    def current_user():
        with sessions() as session:
            return session.get(User, owner["id"])

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_current_user_optional] = current_user

    with TestClient(app) as client:
        conversation = client.post("/api/rag/conversations", json={}).json()["data"]
        payload = {"question": "Q1", "conversation_id": conversation["id"],
                   "request_id": "req-1", "expected_last_sequence": 0,
                   "history": [{"role": "user", "content": "伪造历史"}]}
        response = client.post("/api/rag/chat/stream", json=payload)
        assert response.status_code == 200
        assert '"sequence": 1' in response.text
        assert seen_history == [[]]
        assert client.get(f'/api/rag/conversations/{conversation["id"]}').json()["data"]["turns"][0]["answer"] == "回答"
        assert '"sequence": 1' in client.post("/api/rag/chat/stream", json=payload).text
        assert len(seen_history) == 1

        owner["id"] = 2
        assert client.get(f'/api/rag/conversations/{conversation["id"]}').status_code == 404
        assert client.delete(f'/api/rag/conversations/{conversation["id"]}').status_code == 404
        assert client.post("/api/rag/chat/stream", json={**payload, "request_id": "req-2"}).status_code == 404

        owner["id"] = 1
        assert client.post("/api/rag/chat/stream", json={**payload, "request_id": "req-3"}).status_code == 409

        async def failed_stream(question, **kwargs):
            yield {"type": "token", "data": "未完成"}
            raise RuntimeError("upstream test failure")

        monkeypatch.setattr(rag.service, "chat_stream", failed_stream)
        failed = client.post("/api/rag/chat/stream", json={**payload, "request_id": "req-4",
                                                               "expected_last_sequence": 1})
        assert "event: error" in failed.text
        assert len(client.get(f'/api/rag/conversations/{conversation["id"]}').json()["data"]["turns"]) == 1
        monkeypatch.setattr(llm_context, "get_catalog", lambda: (_ for _ in ()).throw(RuntimeError("catalog unavailable")))
        assert client.get("/api/rag/conversations").status_code == 200
