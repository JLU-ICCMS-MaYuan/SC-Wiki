"""通过实际SDK序列化请求，复现JSON mode消息缺少JSON的请求错误。"""
import json
from types import SimpleNamespace

import httpx
from openai import OpenAI
import pytest

from backend.rag import llm
from backend.ingest.structure_reading import PROMPT


SCHEMA = {'type':'object','properties':{'ok':{'type':'boolean'}},
          'required':['ok'],'additionalProperties':False}
TOOLS = [{'type':'function','function':{'name':'read_page','description':'Read current page.',
    'strict':True,'parameters':{'type':'object','properties':{'page':{'type':'integer'}},
                              'required':['page'],'additionalProperties':False}}}]


def install(monkeypatch, *, mode='text', invalid=False):
    requests=[]
    def handler(request):
        assert request.url.path=='/v1/chat/completions'
        body=json.loads(request.content);requests.append(body)
        messages=body['messages']
        if body['response_format']['type']=='json_object' and not any(
                'json' in str(m.get('content') or '').lower() for m in messages):
            return httpx.Response(400,json={'error':{'type':'invalid_request_error',
                'message':"messages must contain the word 'json' to use json_object"}})
        if mode=='tool':
            arguments={'page':1,**({'undeclared':True} if invalid else {})}
            delta={'tool_calls':[{'index':0,'id':'call_current','type':'function',
                'function':{'name':'read_page','arguments':json.dumps(arguments)}}]}
            finish='tool_calls'
        else:
            delta={'content':json.dumps({'ok':True,**({'undeclared':True} if invalid else {})})}
            finish='stop'
        chunk={'id':'isolated','object':'chat.completion.chunk','created':0,'model':'gpt-6.1-sol',
               'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
        return httpx.Response(200,headers={'content-type':'text/event-stream'},
            content='data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n')
    client=OpenAI(api_key='isolated-test-only',base_url='https://json-mode.invalid/v1',
                  http_client=httpx.Client(transport=httpx.MockTransport(handler)),max_retries=0)
    monkeypatch.setattr(llm,'_client',lambda _:client)
    monkeypatch.setattr(llm,'get_llm_config',lambda:SimpleNamespace(model='gpt-6.1-sol'))
    return client,requests


def test_plain_json_mode_works_when_caller_never_mentions_json(monkeypatch):
    client,requests=install(monkeypatch)
    try:assert llm.complete_json('Read the supplied source.','Current source contents.')=={'ok':True}
    finally:client.close()
    body=requests[0]
    assert len(requests)==1 and body['response_format']=={'type':'json_object'}
    assert 'JSON' in body['messages'][0]['content']
    assert body['messages'][0]['content'].count(llm.JSON_OUTPUT_INSTRUCTION)==1
    assert 'thinking' not in body and 'extra_body' not in body


def test_actual_structure_prompt_native_tools_and_history_keep_ids(monkeypatch):
    client,requests=install(monkeypatch,mode='tool')
    history=[{'role':'assistant','tool_calls':[{'id':'call_previous','type':'function',
        'function':{'name':'read_page','arguments':'{"page":1}'}}]},
        {'role':'tool','tool_call_id':'call_previous','content':'Original page text.'}]
    try:result=llm.complete_json(PROMPT,'Original current source.',tool_definitions=TOOLS,tool_history=history)
    finally:client.close()
    assert result['action']=={'name':'read_page','arguments':{'page':1}}
    assert result['_tool_call']['id']=='call_current'
    assert requests[0]['messages'][2:]==history and requests[0]['tools']==TOOLS
    assert requests[0]['parallel_tool_calls'] is False


def test_existing_json_instruction_stays_byte_equal_for_valid_cache(monkeypatch):
    client,requests=install(monkeypatch)
    prompt='只返回JSON，使用既定字段，保留原文依据。'
    try:assert llm.complete_json(prompt,'Current source.')=={'ok':True}
    finally:client.close()
    assert requests[0]['messages'][0]['content']==prompt


@pytest.mark.parametrize('native',[False,True])
def test_json_instruction_does_not_weaken_local_field_or_tool_contract(monkeypatch,native):
    from backend.rag.structured_output import StructuredOutputError
    client,requests=install(monkeypatch,mode='tool' if native else 'text',invalid=True)
    try:
        with pytest.raises(StructuredOutputError,match='固定字段结构'):
            llm.complete_json(PROMPT,'Source.',retries=3,
                **({'tool_definitions':TOOLS} if native else {'response_schema':SCHEMA}))
    finally:client.close()
    assert len(requests)==1
    if not native:assert requests[0]['response_format']['json_schema']['schema']==SCHEMA
