"""真实SDK/SSE：缺少完成标记属于断流，完整错误结构仍停止。"""
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
from openai import OpenAI
import pytest
from backend.rag import llm
from backend.tests.test_model_runtime import setup_runtime

FAILURE=Path(__file__).parent/"fixtures/model_stream_incomplete/failure.json"
SCHEMA={"type":"object","properties":{"answer":{"type":"integer"}},"required":["answer"],"additionalProperties":False}


def install(monkeypatch, first, finish=None, incomplete_attempts=1):
    sent=[]
    def handler(request):
        sent.append(json.loads(request.content))
        failing=len(sent)<=incomplete_attempts
        chunk={"id":"replay","object":"chat.completion.chunk","created":0,"model":"fixture",
          "choices":[{"index":0,"delta":{"content":first if failing else '{"answer":42}'},
                      "finish_reason":finish if failing else "stop"}]}
        # 第一次流在HTTP层正常结束，但没有finish_reason或DONE；与真实故障一致。
        content="data: "+json.dumps(chunk)+"\n\n"
        if not failing or finish is not None:content+="data: [DONE]\n\n"
        return httpx.Response(200,headers={"content-type":"text/event-stream"},content=content)
    clients=[]
    def factory(_):
        client=OpenAI(api_key="isolated-stream-fixture",base_url="https://fixture.invalid/v1",max_retries=0,
                      http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        clients.append(client);return client
    monkeypatch.setattr(llm,"_client",factory)
    monkeypatch.setattr(llm,"get_llm_config",lambda:SimpleNamespace(model="fixture"))
    return SimpleNamespace(close=lambda:[c.close() for c in clients]),sent


@pytest.mark.parametrize("first",[json.loads(FAILURE.read_text())["partial_response"],'{"answer":999}'],ids=["real-partial","valid-without-finish"])
def test_unfinished_stream_retries_identical_request_and_preserves_partial(tmp_path,monkeypatch,first):
    client,sent=install(monkeypatch,first)
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    try:
        with context(runtime):assert llm.complete_json("Fixed JSON contract","Unchanged original source",response_schema=SCHEMA)=={"answer":42}
    finally:client.close()
    assert len(sent)==2 and sent[0]==sent[1]
    failure=json.loads(next(tmp_path.rglob("failure-*.json")).read_text())
    assert failure["partial_response"]==first and failure["error"]["output_started"] is True
    assert failure["error"]["code"]=="LLM_STREAM_INCOMPLETE"
    assert json.loads(next(tmp_path.rglob("result.json")).read_text())["response"]=={"answer":42}


@pytest.mark.parametrize("first,finish",[('{broken',"stop"),('{"answer":42,"extra":1}',"stop"),('{"answer":',"length"),('{"answer":',"content_filter")])
def test_complete_invalid_or_explicit_truncation_remains_blocked(tmp_path,monkeypatch,first,finish):
    client,sent=install(monkeypatch,first,finish)
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    try:
        with context(runtime),pytest.raises(Exception):llm.complete_json("JSON contract","source",response_schema=SCHEMA)
    finally:client.close()
    assert len(sent)==1 and not list(tmp_path.rglob("result.json"))
    assert state["model_activity"]["error"]["error_type"]=="StructuredOutputError"


def test_five_incomplete_streams_pause_without_sending_a_sixth(tmp_path,monkeypatch):
    from backend.ingest import model_runtime
    first=json.loads(FAILURE.read_text())["partial_response"]
    client,sent=install(monkeypatch,first,incomplete_attempts=5)
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    monkeypatch.setattr(model_runtime,"_pause_task_state",lambda *a,**k:state.update(status="paused",execution_generation=2))
    try:
        with context(runtime),pytest.raises(model_runtime.ExecutionStopped):
            llm.complete_json("JSON contract","unchanged source",response_schema=SCHEMA)
    finally:client.close()
    assert len(sent)==5 and state["status"]=="paused"
    assert len(list(tmp_path.rglob("failure-*.json")))==5
    assert not list(tmp_path.rglob("result.json"))
