"""#224：真正调用LangMem，科学依据不作为摘要替代。"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda


def test_langmem_summary_is_reused_and_recent_tool_pair_stays(tmp_path):
    from backend.ingest.model_memory import compact_history
    calls=[]
    model=RunnableLambda(lambda value:(calls.append(value) or AIMessage(content='已完成旧步骤；待继续当前步骤')))
    history=[]
    for i in range(8):
        history += [{'role':'assistant','content':None,'tool_calls':[{'id':f'c{i}','type':'function','function':{'name':'read_page','arguments':'{}'}}]},
                    {'role':'tool','tool_call_id':f'c{i}','content':'previous observation '*160}]
    result=compact_history(history,tmp_path/'memory.json',model=model,budget=650)
    assert calls
    assert result[-2:]==history[-2:]
    assert len(str(result))<len(str(history))
    again=compact_history(history,tmp_path/'memory.json',model=model,budget=650)
    assert again==result and len(calls)==1


def test_required_current_evidence_is_never_truncated(tmp_path):
    from backend.ingest.model_memory import prepare_request, ContextBudgetError
    payload={'user_prompt':'current original YH10 4.4788 '*200,'images':['data:image/png;base64,REAL'],'tool_history':[]}
    import pytest
    with pytest.raises(ContextBudgetError): prepare_request(payload,tmp_path,budget=100)
    assert payload['images']==['data:image/png;base64,REAL']
    assert '4.4788' in payload['user_prompt']


def test_prepare_compacts_only_referenced_receipts_preserving_current_source(tmp_path):
    from backend.ingest.model_memory import prepare_request
    import json
    calls=[]
    model=RunnableLambda(lambda prompt:(calls.append(prompt) or AIMessage(content='旧页已读取，当前页待完成')))
    original='YH10 at 400 GPa; a=4.4788 angstrom; original row retained.'
    history=[]
    for i in range(8):
        history.extend([{'role':'assistant','content':None,'tool_calls':[{'id':f't{i}','type':'function','function':{'name':'read_page','arguments':'{}'}}]},
            {'role':'tool','tool_call_id':f't{i}','content':json.dumps({'source_ids':['s1']*100,'source_text_location':'request.sources'})}])
    request={'system_prompt':'fixed scientific contract','user_prompt':json.dumps({'sources':[{'source_id':'s1','content':original}]}),
             'images':['data:image/png;base64,UNCHANGED'],'tool_history':history}
    prepared=prepare_request(request,tmp_path,model=model,budget=6000,force=True)
    assert calls
    assert prepared['user_prompt']==request['user_prompt']
    assert prepared['images']==request['images']
    assert prepared['tool_history'][-2:]==history[-2:]
    assert len(str(prepared))<len(str(request))


def test_summary_calls_use_persistent_runtime_and_resume_without_model(tmp_path,monkeypatch):
    from backend.ingest.model_runtime import ModelRuntime,execution_context
    from backend.ingest.model_memory import compact_history
    from backend.rag import llm_client
    from contextlib import nullcontext
    from types import SimpleNamespace as NS
    import json
    calls=[]
    class Model:
        root_client=NS(close=lambda:None)
        def bind(self,**kwargs):return self
        def invoke(self,prompt):calls.append(prompt);return AIMessage(content='旧操作已完成，保留当前页',usage_metadata={'input_tokens':100,'output_tokens':20,'total_tokens':120})
    monkeypatch.setattr(llm_client,'get_langchain_llm',lambda **_:Model())
    state={'status':'reading','execution_generation':1}
    def runtime():return ModelRuntime('a'*32,1,tmp_path/'runtime',lambda:dict(state),lambda **changes:state.update(changes),lambda:nullcontext(),identity={'model':'fixture'})
    history=[]
    for i in range(5):history.extend([{'role':'assistant','content':None,'tool_calls':[{'id':f't{i}','type':'function','function':{'name':'read_page','arguments':'{}'}}]}, {'role':'tool','tool_call_id':f't{i}','content':'old operation '*100}])
    with execution_context(runtime()):first=compact_history(history,tmp_path/'summary-a.json',budget=1000)
    assert len(calls)==1
    # 模拟摘要产物写入前中断：完整模型响应已存，重建摘要时仍不重发。
    with execution_context(runtime()):second=compact_history(history,tmp_path/'summary-b.json',budget=1000)
    assert first==second and len(calls)==1
    results=[json.loads(p.read_text()) for p in (tmp_path/'runtime').rglob('result.json')]
    assert results[0]['response']['usage']['input_tokens']==100
