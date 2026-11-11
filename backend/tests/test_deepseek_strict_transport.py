"""官方严格入口及嵌套引用的实际SDK/SSE回放；原科学Schema不变。"""
from copy import deepcopy
from types import SimpleNamespace as NS
import json
import httpx
from openai import OpenAI
import pytest
from backend.rag import llm
from backend.tests.test_model_runtime import setup_runtime

SCHEMA={"type":"object","properties":{"measurement":{"anyOf":[{"$ref":"#/$defs/Measurement"},{"type":"null"}]}},
 "required":["measurement"],"additionalProperties":False,"$defs":{"Measurement":{"type":"object",
 "properties":{"value":{"type":"number"},"uncertainty":{"anyOf":[{"type":"number"},{"type":"null"}]}},
 "required":["value","uncertainty"],"additionalProperties":False}}}


def install(monkeypatch,host="api.deepseek.com"):
    config=NS(model="deepseek-flash",base_url="https://"+host,provider="fixture")
    monkeypatch.setattr(llm,"get_llm_config",lambda:config)
    sent=[];clients=[]
    def handle(request):
        body=json.loads(request.content);sent.append((request.url,body))
        schema=body["tools"][0]["function"]["parameters"] if "tools"in body else body["response_format"]["json_schema"]["schema"]
        compatible=(request.url.path=="/beta/chat/completions" and "$defs"not in schema
          and all("type"in v for v in schema["properties"]["measurement"]["anyOf"]))
        good=compatible or host!="api.deepseek.com"
        args={"measurement":{"value":42,**({"uncertainty":None}if good else{})}}
        if "tools"in body:
            delta={"tool_calls":[{"index":0,"id":"native-strict","type":"function","function":{"name":"report_structured_output","arguments":json.dumps(args)}}]};finish="tool_calls"
        else:delta={"content":json.dumps(args)};finish="stop"
        chunk={"id":"strict-replay","object":"chat.completion.chunk","created":0,"model":"fixture",
          "choices":[{"index":0,"delta":delta,"finish_reason":finish}]}
        return httpx.Response(200,headers={"content-type":"text/event-stream"},content="data: "+json.dumps(chunk)+"\n\ndata: [DONE]\n\n")
    def factory(_):
        client=OpenAI(api_key="isolated-fixture",base_url=config.base_url,max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        clients.append(client);return client
    monkeypatch.setattr(llm,"_client",factory)
    return config,sent,lambda:[c.close()for c in clients]


def test_official_request_uses_beta_and_supported_references_without_changing_contract(monkeypatch):
    config,sent,close=install(monkeypatch);before=deepcopy(SCHEMA)
    try:assert llm.complete_json("JSON","measurement 42",response_schema=SCHEMA)=={"measurement":{"value":42,"uncertainty":None}}
    finally:close()
    assert sent[0][0].path=="/beta/chat/completions"
    wire=sent[0][1]["tools"][0]["function"]["parameters"]
    assert "$defs"not in wire
    assert wire["properties"]["measurement"]["anyOf"][0]["properties"]==SCHEMA["$defs"]["Measurement"]["properties"]
    assert SCHEMA==before and config.base_url=="https://api.deepseek.com"


def test_custom_gateway_keeps_its_original_schema_and_route(monkeypatch):
    _,sent,close=install(monkeypatch,"gateway.invalid")
    try:assert llm.complete_json("JSON","measurement 42",response_schema=SCHEMA)["measurement"]["value"]==42
    finally:close()
    assert sent[0][0].path=="/chat/completions"
    assert sent[0][1]["response_format"]["json_schema"]["schema"]==SCHEMA


def test_transport_budget_marker_does_not_invalidate_valid_canonical_checkpoint(tmp_path,monkeypatch):
    _,sent,close=install(monkeypatch)
    runtime,context,_=setup_runtime(tmp_path,monkeypatch)
    prompt=llm._json_output_prompt("JSON")+"\nSchema transport strict-function-v1: use the registered report_structured_output function for the complete JSON response."
    good={"measurement":{"value":42,"uncertainty":None}}
    runtime.call(lambda *_a,**_k:deepcopy(good),prompt,"source",response_schema=SCHEMA)
    before={p:p.read_bytes()for p in tmp_path.rglob("result.json")}
    runtime,context,_=setup_runtime(tmp_path,monkeypatch)
    try:
        with context(runtime):assert llm.complete_json("JSON","source",response_schema=SCHEMA)==good
    finally:close()
    assert not sent and all(p.read_bytes()==v for p,v in before.items())


def test_budget_counts_actual_wire_schema_without_raising_existing_limit():
    from backend.rag.deepseek_strict import MODE,MARKER,request_tools
    from backend.ingest.model_memory import _fixed_token_estimate,prepare_fixed_request,ContextBudgetError
    request={"system_prompt":"JSON","user_prompt":"measurement 42","response_schema":SCHEMA,MARKER:MODE}
    actual={"system_prompt":request["system_prompt"],"user_prompt":request["user_prompt"],"tool_definitions":request_tools(request)}
    expected=_fixed_token_estimate(actual)
    assert _fixed_token_estimate(request)==expected
    assert expected!=_fixed_token_estimate({k:v for k,v in request.items()if k!=MARKER})
    with pytest.raises(ContextBudgetError):prepare_fixed_request(request,budget=expected-1)


def test_schema_projection_keeps_the_same_accepted_values_and_rejects_recursive_union():
    from backend.rag.deepseek_strict import wire_schema
    from backend.rag.structured_output import StructuredOutputError
    from jsonschema import Draft202012Validator
    projected=wire_schema(SCHEMA)
    samples=[{"measurement":None},{"measurement":{"value":42,"uncertainty":None}},
      {"measurement":{"value":42}},{"measurement":{"value":42,"uncertainty":None,"extra":1}}]
    assert [Draft202012Validator(SCHEMA).is_valid(v)for v in samples]==[Draft202012Validator(projected).is_valid(v)for v in samples]
    cyclic={"$defs":{"Loop":{"anyOf":[{"$ref":"#/$defs/Loop"},{"type":"null"}]}},"anyOf":[{"$ref":"#/$defs/Loop"}]}
    with pytest.raises(StructuredOutputError):wire_schema(cyclic)


def test_alias_to_union_is_explicit_at_use_site_and_references_only_typed_definitions():
    from backend.rag.deepseek_strict import wire_schema
    schema=deepcopy(SCHEMA)
    schema["$defs"]["OptionalMeasurement"]=schema["properties"]["measurement"]
    schema["$defs"]["Alias"]={"$ref":"#/$defs/OptionalMeasurement"}
    schema["properties"]["measurement"]={"$ref":"#/$defs/Alias"}
    projected=wire_schema(schema)
    assert "anyOf"in projected["properties"]["measurement"]
    refs=[]
    def collect(node):
        if isinstance(node,dict):
            if "$ref"in node:refs.append(node["$ref"])
            for child in node.values():collect(child)
        elif isinstance(node,list):
            for child in node:collect(child)
    collect(projected)
    assert all("type"in projected.get("$def",{})[ref.split("/")[-1]]for ref in refs)
    from jsonschema import Draft202012Validator
    assert Draft202012Validator(projected).is_valid({"measurement":{"value":42,"uncertainty":None}})
    assert not Draft202012Validator(projected).is_valid({"measurement":{"value":42}})


def test_source_aliases_are_lossless_and_never_rewrite_scientific_text():
    from backend.rag.deepseek_strict import request_view,restore_source_ids
    file_id="a"*32;block_id="b"*64
    quote={"type":"object","properties":{"file_id":{"$ref":"#/$defs/CurrentSourceFile"},
      "block_id":{"$ref":"#/$defs/CurrentSourceBlock"}}, "required":["file_id","block_id"],"additionalProperties":False}
    schema={"type":"object","properties":{"evidences":{"type":"array","items":quote}},"required":["evidences"],"additionalProperties":False,
      "$defs":{"CurrentSourceFile":{"type":"string","enum":[file_id]},"CurrentSourceBlock":{"type":"string","enum":[block_id]}}}
    payload={"file_id":file_id,"pages":[{"blocks":[{"block_id":block_id,"text":block_id}]}]}
    original=json.dumps(schema,sort_keys=True)
    view=request_view({"system_prompt":"JSON","user_prompt":"section: test\n\n"+json.dumps(payload),"response_schema":schema})
    packed=json.loads(view["user_prompt"].split("\n\n",1)[1])
    assert packed["file_id"].startswith("sref_")
    assert packed["pages"][0]["blocks"][0]["text"]==block_id
    assert restore_source_ids(packed,view["source_ids"])==payload
    assert json.dumps(schema,sort_keys=True)==original
    marker=packed["pages"][0]["blocks"][0]["block_id"]
    restored=restore_source_ids({"block_id":marker,"value_text":marker},view["source_ids"])
    assert restored=={"block_id":block_id,"value_text":marker}
    # 编码过的旧上下文没有足够可见身份时不偷偷生成无法对应的短引用。
    hidden=request_view({"system_prompt":"JSON","user_prompt":json.dumps({"file_id":file_id}),"response_schema":schema})
    assert not hidden["source_ids"]


def test_real_sdk_source_alias_response_is_restored_before_canonical_validation(monkeypatch):
    file_id="a"*32;block_id="b"*64
    quote={"type":"object","properties":{"file_id":{"$ref":"#/$defs/CurrentSourceFile"},
        "block_id":{"$ref":"#/$defs/CurrentSourceBlock"}},"required":["file_id","block_id"],"additionalProperties":False}
    schema={"type":"object","properties":{"evidences":{"type":"array","items":quote}},"required":["evidences"],"additionalProperties":False,
      "$defs":{"CurrentSourceFile":{"type":"string","enum":[file_id]},"CurrentSourceBlock":{"type":"string","enum":[block_id]}}}
    config=NS(model="deepseek-flash",base_url="https://api.deepseek.com")
    monkeypatch.setattr(llm,"get_llm_config",lambda:config)
    requests=[];clients=[]
    def handle(request):
        body=json.loads(request.content);requests.append(body)
        wire=body["tools"][0]["function"]["parameters"]
        fields=wire["properties"]["evidences"]["items"]["properties"]
        f=fields["file_id"]["enum"][0];b=fields["block_id"]["enum"][0]
        payload=json.loads(body["messages"][1]["content"].split("\n\n",1)[1])
        assert payload["file_id"]==f and payload["block_id"]==b
        assert payload["text"]==block_id
        assert f.startswith("sref_") and b.startswith("sref_")
        args={"evidences":[{"file_id":f,"block_id":b}]}
        chunk={"id":"alias-sse","object":"chat.completion.chunk","created":0,"model":"fixture","choices":[{"index":0,
          "delta":{"tool_calls":[{"index":0,"id":"real-source-ids","type":"function","function":{"name":"report_structured_output","arguments":json.dumps(args)}}]}, "finish_reason":"tool_calls"}]}
        return httpx.Response(200,headers={"content-type":"text/event-stream"},content="data: "+json.dumps(chunk)+"\n\ndata: [DONE]\n\n")
    def factory(_):
        c=OpenAI(api_key="isolated-fixture",base_url=config.base_url,max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)));clients.append(c);return c
    monkeypatch.setattr(llm,"_client",factory)
    try:
        result=llm.complete_json("JSON","section\n\n"+json.dumps({"file_id":file_id,"block_id":block_id,"text":block_id}),response_schema=schema)
    finally:
        for c in clients:c.close()
    assert result=={"evidences":[{"file_id":file_id,"block_id":block_id}]}
    assert len(requests)==1


def test_uploaded_page_pair_has_one_wire_identity_and_restores_before_validation():
    from backend.rag.deepseek_strict import request_view,restore_source_ids
    from backend.rag.structured_output import validate_output,StructuredOutputError
    from backend.ingest.scientific_output_schema import obj,array
    schema=obj({"read_pages":array({"anyOf":[obj({"file_id":{"type":"string","enum":["main"]},"page":{"type":"integer","enum":[1,2]}}),
      obj({"file_id":{"type":"string","enum":["si"]},"page":{"type":"integer","enum":[30]}})]})})
    view=request_view({"system_prompt":"JSON","user_prompt":"original sources","response_schema":schema})
    wire=view["tool_definitions"][0]["function"]["parameters"]
    assert wire["properties"]["read_pages"]["items"]=={"type":"string","enum":["pref_0","pref_1","pref_2"]}
    restored=restore_source_ids({"read_pages":["pref_2"]},view["source_ids"])
    assert restored=={"read_pages":[{"file_id":"si","page":30}]}
    validate_output(restored,schema)
    with pytest.raises(StructuredOutputError):validate_output({"read_pages":[{"file_id":"main","page":30}]},schema)
    with pytest.raises(StructuredOutputError):validate_output({"read_pages":["main/30"]},wire)
