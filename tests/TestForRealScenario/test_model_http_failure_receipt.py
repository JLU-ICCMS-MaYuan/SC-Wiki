"""真实5xx未进入调用账本：只补安全状态回执，不改变重试或保存响应凭据。"""
import json
from types import SimpleNamespace

import httpx
from openai import APIStatusError
import pytest


@pytest.mark.parametrize("status", [401, 503])
def test_http_failure_is_recorded_once_without_response_secrets_or_automatic_retry(monkeypatch, status):
    from backend.rag import llm
    request = httpx.Request("POST", "https://model.invalid/chat/completions",
                            headers={"Authorization": "Bearer isolated-secret-not-for-logs"})
    error = APIStatusError("response contains isolated-secret-not-for-logs",
        response=httpx.Response(status, request=request), body={"message": "isolated-secret-not-for-logs"})
    attempts, callbacks, observed = [], [], []
    def stream(*args, **kwargs):
        attempts.append(True)
        raise error
    monkeypatch.setattr(llm, "_stream_json", stream)
    monkeypatch.setattr(llm, "get_llm_config", lambda: SimpleNamespace(model="isolated-model"))
    token = llm.set_call_observer(observed.append)
    try:
        with pytest.raises(APIStatusError) as caught:
            llm.complete_json("scientific prompt", "source content", retries=2, on_call=callbacks.append)
    finally:
        llm.reset_call_observer(token)
    assert caught.value is error and len(attempts) == 1
    assert len(callbacks) == len(observed) == 1
    assert callbacks[0]["status"] == observed[0]["status"] == "failed"
    assert callbacks[0]["status_code"] == observed[0]["status_code"] == status
    assert "isolated-secret-not-for-logs" not in json.dumps([callbacks, observed])


def test_completed_wire_response_rejected_by_schema_is_counted_without_retry(monkeypatch):
    from backend.rag import llm
    from backend.rag.structured_output import StructuredOutputError
    attempts, callbacks, observed = [], [], []
    def stream(*args, **kwargs):
        attempts.append(True)
        return {"illegal": True}
    monkeypatch.setattr(llm, "_stream_json", stream)
    monkeypatch.setattr(llm, "get_llm_config", lambda: SimpleNamespace(model="isolated-model"))
    token = llm.set_call_observer(observed.append)
    try:
        with pytest.raises(StructuredOutputError):
            llm.complete_json("prompt", "source", retries=2, on_call=callbacks.append,
                response_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False})
    finally:
        llm.reset_call_observer(token)
    assert len(attempts) == 1 and len(callbacks) == len(observed) == 1
    assert observed[0]["status"] == "failed" and observed[0]["error_type"] == "StructuredOutputError"
