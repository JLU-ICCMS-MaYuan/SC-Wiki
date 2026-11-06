"""用户确认：仅明确未输出的可重试503，原请求最多额外两次，完整计账。"""
import json
from types import SimpleNamespace as NS
import httpx,pytest
from openai import APIStatusError
from backend.rag import llm

def error(body,status=503):
    request=httpx.Request("POST","https://model.invalid/chat/completions")
    return APIStatusError("private-not-for-receipts",response=httpx.Response(status,request=request),body=body)

SAFE={"error":{"output_started":False,"retryable":True,"message":"private-not-for-receipts"}}

def install(monkeypatch,outcomes):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs);result=outcomes.pop(0)
        if isinstance(result,Exception):raise result
        return iter([NS(choices=[NS(delta=NS(content=result),finish_reason="stop")])])
    monkeypatch.setattr(llm,"_client",lambda _:NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm,"get_llm_config",lambda:NS(model="fixture"))
    monkeypatch.setattr(llm.time,"sleep",lambda _:None)
    return calls

def test_explicit_unstarted_503_retries_twice_even_without_format_retry(monkeypatch):
    calls=install(monkeypatch,[error(SAFE),error(SAFE),'{"ok":true}']);receipts=[]
    assert llm.complete_json("JSON","source",retries=0,on_call=receipts.append)=={"ok":True}
    assert len(calls)==3 and calls[0]==calls[1]==calls[2]
    assert [r["status"] for r in receipts]==["failed","failed","completed"]
    assert "private-not-for-receipts" not in json.dumps(receipts)

def test_three_service_failures_stop_at_two_retries(monkeypatch):
    calls=install(monkeypatch,[error(SAFE),error(SAFE),error(SAFE)]);receipts=[]
    with pytest.raises(APIStatusError):llm.complete_json("JSON","source",retries=0,on_call=receipts.append)
    assert len(calls)==len(receipts)==3

@pytest.mark.parametrize("body,status",[
    (SAFE,401),(SAFE,400),(SAFE,422),(SAFE,500),
    ({"output_started":True,"retryable":True},503),
    ({"retryable":True},503),({"output_started":False},503),
    ({"output_started":"false","retryable":True},503),
    ({"output_started":False,"retryable":True,"error":{"output_started":True}},503),
    ({"output_started":False,"retryable":False},503),
])
def test_missing_conflicting_or_started_status_does_not_retry(monkeypatch,body,status):
    calls=install(monkeypatch,[error(body,status)])
    with pytest.raises(APIStatusError):llm.complete_json("JSON","source",retries=0)
    assert len(calls)==1

def test_local_output_blocks_retry_even_if_server_claims_unstarted(monkeypatch):
    calls=[]
    class Stream:
        def __iter__(self):
            yield NS(choices=[NS(delta=NS(content=" "),finish_reason=None)])
            raise error(SAFE)
        def close(self):pass
    def create(**kwargs):calls.append(kwargs);return Stream()
    monkeypatch.setattr(llm,"_client",lambda _:NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm,"get_llm_config",lambda:NS(model="fixture"))
    with pytest.raises(APIStatusError):llm.complete_json("JSON","source",retries=0)
    assert len(calls)==1

def test_sdk_inner_body_cannot_hide_conflicting_outer_response(monkeypatch):
    request=httpx.Request("POST","https://model.invalid/chat/completions")
    exc=APIStatusError("private-not-for-receipts",response=httpx.Response(503,request=request,
        json={"output_started":True,"error":{"output_started":False,"retryable":True}}),
        body={"output_started":False,"retryable":True})
    calls=install(monkeypatch,[exc])
    with pytest.raises(APIStatusError):llm.complete_json("JSON","source",retries=0)
    assert len(calls)==1
