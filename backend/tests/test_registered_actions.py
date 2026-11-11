from types import SimpleNamespace as NS
from copy import deepcopy
import json
import httpx
import pytest
from openai import OpenAI
from backend.rag import llm
from backend.rag.registered_actions import action_schema,MARKER
from backend.rag.structured_output import StructuredOutputError

TOOLS=[{'type':'function','function':{'name':'read_page','description':'Read actual current page','strict':True,
    'parameters':{'type':'object','properties':{'page':{'type':'integer','enum':[1]}},'required':['page'],'additionalProperties':False}}}]


@pytest.mark.parametrize('bad',[False,True])
def test_actual_responses_sdk_closed_action_and_no_fake_provider_receipt(monkeypatch,bad):
    sent=[]
    def handle(request):
        body=json.loads(request.content);sent.append(body)
        assert request.url.path=='/responses' and 'tools' not in body
        assert body['reasoning']=={'effort':'none'}
        assert body['stream'] is False
        assert body['text']['format']['schema']==action_schema(TOOLS)
        value={'action':{'name':'read_page','arguments':{'page':1,**({'invented':True}if bad else{})}}}
        return httpx.Response(200,json={'id':'actual-response','object':'response','status':'completed','usage':None,
            'output':[{'type':'message','id':'message','role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':json.dumps(value),'annotations':[]}]}]})
    config=NS(model='deepseek-flash',base_url='https://api.deepseek.com',provider='fixture')
    client=OpenAI(api_key='isolated-placeholder',base_url=config.base_url,max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(llm,'_client',lambda _:client);monkeypatch.setattr(llm,'get_llm_config',lambda:config)
    original=deepcopy(TOOLS)
    try:
        if bad:
            with pytest.raises(StructuredOutputError):llm.complete_json('JSON','source',tool_definitions=TOOLS,**{MARKER:True})
        else:
            result=llm.complete_json('JSON','source',tool_definitions=TOOLS,**{MARKER:True})
            assert result['action']=={'name':'read_page','arguments':{'page':1}}
            assert '_tool_call'not in result and result['_tool_transport']=='registered-json-actions-v1'
    finally:client.close()
    assert TOOLS==original and len(sent)==1


def test_actual_schema_budget_and_independent_function_refs():
    from backend.ingest.model_memory import _fixed_token_estimate
    tools=deepcopy(TOOLS)
    tools[0]['function']['parameters']={'type':'object','properties':{'page':{'$ref':'#/$defs/Page'}},
        'required':['page'],'additionalProperties':False,'$defs':{'Page':{'type':'integer','enum':[1]}}}
    from backend.rag.structured_output import output_format,validate_output
    schema=action_schema(tools);output_format(schema)
    validate_output({'action':{'name':'read_page','arguments':{'page':1}}},schema)
    request={'system_prompt':'JSON','user_prompt':'source','tool_definitions':tools,MARKER:True}
    assert _fixed_token_estimate(request)==_fixed_token_estimate({'system_prompt':'JSON','user_prompt':'source','response_schema':schema})


def test_atomic_incomplete_response_never_uses_even_complete_looking_json():
    from backend.rag.responses_json import call
    client=NS(responses=NS(create=lambda **kwargs:NS(status='incomplete',output_text='{"action":{"name":"read_page","arguments":{"page":1}}}',usage=None)))
    with pytest.raises(StructuredOutputError,match='完成标记'):
        call(client,NS(model='deepseek-flash'),'JSON','source',images=[],definitions=None,history=[],
            response_format=None,on_partial=None,on_usage=lambda _:None,on_started=lambda:None,atomic=True)
