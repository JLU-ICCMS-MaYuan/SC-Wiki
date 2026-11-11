"""修订阶段沿用原生严格工具；失败协议缓存不能冒充成功步骤。"""
import json
from types import SimpleNamespace as NS
import pytest
from backend.rag import llm
from backend.rag.structured_output import StructuredOutputError
from backend.tests.test_model_runtime import setup_runtime


def definitions(name="repair_structures"):
    return [{"type":"function","function":{"name":name,"description":"结构修订","strict":True,
      "parameters":{"type":"object","properties":{"updates":{"type":"array","items":{"type":"integer"}},"reason":{"type":"string"}},
                    "required":["updates","reason"],"additionalProperties":False}}}]


def install(monkeypatch, *, text=None):
    sent=[]
    class Stream:
        closed=False
        def __iter__(self):
            if text is not None:
                yield NS(choices=[NS(delta=NS(content=text),finish_reason="stop")])
            else:
                call=NS(index=0,id="native-repair",function=NS(name="repair_structures",arguments=json.dumps({"updates":[],"reason":"合法修订"})))
                yield NS(choices=[NS(delta=NS(content=None,tool_calls=[call]),finish_reason="tool_calls")])
        def close(self):self.closed=True
    stream=Stream()
    def create(**kwargs):sent.append(kwargs);return stream
    monkeypatch.setattr(llm,"get_llm_config",lambda:NS(model="fixture"))
    monkeypatch.setattr(llm,"_client",lambda _:NS(chat=NS(completions=NS(create=create))))
    return sent,stream


def test_repair_stage_requires_native_tool_choice_and_keeps_real_call_id(monkeypatch):
    sent,stream=install(monkeypatch)
    result=llm.complete_json("JSON","原文",tool_definitions=definitions())
    assert sent[0]["tool_choice"]=="required"
    assert result["_tool_call"]["id"]=="native-repair" and stream.closed


@pytest.mark.parametrize("body", ['{"type":"function_call","updates":[],"reason":"真实失败协议"}','{"updates":[],"reason":"自由JSON也不能冒充原生回执"}'])
def test_plain_repair_json_is_not_cached_as_native_success(tmp_path,monkeypatch,body):
    sent,stream=install(monkeypatch,text=body)
    from backend.ingest.model_runtime import ModelRequestError
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    with context(runtime),pytest.raises(ModelRequestError):
        llm.complete_json("JSON","原文",tool_definitions=definitions())
    assert len(sent)==1 and stream.closed and not list(tmp_path.rglob("result.json"))
    assert state['model_activity']['error']['error_type']=='StructuredOutputError'


def test_only_repair_transport_gets_new_request_identity(tmp_path,monkeypatch):
    sent,_=install(monkeypatch)
    runtime,context,_=setup_runtime(tmp_path,monkeypatch)
    old={"type":"function_call","updates":[],"reason":"原失败回执保留"}
    runtime.call(lambda *_a,**_k:old,llm._json_output_prompt("JSON"),"原文",tool_definitions=definitions())
    old_files={p:p.read_bytes()for p in tmp_path.rglob("result.json")}
    initial={"structures":"已成功结果保持原样"}
    runtime.call(lambda *_a,**_k:initial,llm._json_output_prompt("JSON"),"原文",tool_definitions=definitions("report_structures"))
    runtime,context,_=setup_runtime(tmp_path,monkeypatch)
    with context(runtime):
        assert llm.complete_json("JSON","原文",tool_definitions=definitions("report_structures"))==initial
        result=llm.complete_json("JSON","原文",tool_definitions=definitions())
    assert result.get("_tool_call",{}).get("id")=="native-repair"
    assert len(sent)==1 and all(p.read_bytes()==b for p,b in old_files.items())
