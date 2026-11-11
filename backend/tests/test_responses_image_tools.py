import json
import io
import base64
from types import SimpleNamespace as NS
from PIL import Image

import pytest

from backend.rag import llm
from backend.tests.test_pdf_review_tools import TOOL


def image_url():
    out=io.BytesIO();Image.new('RGB',(16,16),'red').save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def test_official_gpt_responses_preserves_pixels_call_ids_and_usage(monkeypatch):
    calls=[]
    events=[NS(type='response.output_item.done', item=NS(type='function_call',
        call_id='call-fixed', name='read_original_page', arguments='{"file_id":"si","page":1}')),
        NS(type='response.completed', response=NS(status='completed', usage=NS(model_dump=lambda:{'input_tokens':20,'output_tokens':10,'total_tokens':30})))]
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='gpt-6.1-sol',base_url='https://api.openai.com/v1'))
    monkeypatch.setattr(llm,'_client',lambda _:NS(responses=NS(create=lambda **kw:(calls.append(kw) or iter(events)))))
    result=llm.complete_json('JSON','inspect',images=[image_url()],tool_definitions=[TOOL])
    assert result['_tool_call']['id']=='call-fixed'
    assert calls[0]['input'][0]['content'][1]['type']=='input_image'
    assert calls[0]['tools'][0]['name']=='read_original_page'
    assert llm._call_stats.get()['api_protocol']=='responses'


def test_responses_history_keeps_native_tool_pair(monkeypatch):
    calls=[]
    events=[NS(type='response.output_text.delta',delta='{"ok":true}'),
        NS(type='response.completed',response=NS(status='completed',usage=None))]
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='gpt-6.1-sol',base_url='https://api.openai.com/v1'))
    monkeypatch.setattr(llm,'_client',lambda _:NS(responses=NS(create=lambda **kw:(calls.append(kw) or iter(events)))))
    result=llm.complete_json('JSON','continue',tool_definitions=[TOOL],tool_history=[
        {'role':'assistant','content':None,'tool_calls':[{'id':'call-fixed','function':{'name':'read_original_page','arguments':'{"file_id":"si","page":1}'}}]},
        {'role':'tool','tool_call_id':'call-fixed','content':'{"receipt":"one"}'}])
    assert result=={'ok':True}
    assert calls[0]['input'][1]['call_id']==calls[0]['input'][2]['call_id']=='call-fixed'


def test_known_nonvisual_selection_refused_without_call_or_switch(monkeypatch):
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='deepseek-v4-pro',base_url='https://api.deepseek.com'))
    monkeypatch.setattr(llm,'_client',lambda _:pytest.fail('must not call unsupported model'))
    with pytest.raises(Exception,match='图片'):
        llm.complete_json('JSON','image',images=[image_url()])


def test_official_flash_schema_uses_same_strict_native_tool(monkeypatch):
    from backend.tests.test_pdf_review_tools import tool_part
    calls=[]
    schema={'type':'object','properties':{'code':{'type':'string'}},'required':['code'],'additionalProperties':False}
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='deepseek-flash',base_url='https://api.deepseek.com'))
    monkeypatch.setattr(llm,'_client',lambda _:NS(chat=NS(completions=NS(create=lambda **kw:(calls.append(kw) or iter([
        NS(id='id',choices=[NS(delta=NS(content=None,tool_calls=[NS(index=0,id='native',function=NS(name='report_structured_output',arguments='{"code":"seen"}'))]),finish_reason='tool_calls')])]))))))
    assert llm.complete_json('JSON','read',response_schema=schema)=={'code':'seen'}
    assert 'response_format' not in calls[0]
    assert calls[0]['tools'][0]['function']['parameters']==schema
    assert calls[0]['tools'][0]['function']['strict'] is True
