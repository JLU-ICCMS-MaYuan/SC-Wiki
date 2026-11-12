"""#224：真正调用LangMem，科学依据不作为摘要替代。"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda


def test_identical_current_observation_is_referenced_without_summarizing_science(tmp_path):
    import json
    from copy import deepcopy
    from backend.ingest.model_memory import prepare_request, _fixed_token_estimate
    receipt={'action':'read_complete_object','file_id':'original',
             'text_observations':[{'text':f'Original unabridged row {i}: value 4.4788'}for i in range(600)]}
    request={'system_prompt':'Read the original source.', 'user_prompt':json.dumps({'observation':receipt}),
             'tool_history':[{'role':'assistant','content':None,'tool_calls':[{'id':'actual',
                'type':'function','function':{'name':'read_complete_object','arguments':'{}'}}]},
                {'role':'tool','tool_call_id':'actual','content':json.dumps(receipt)}]}
    original=deepcopy(request)
    prepared=prepare_request(request,tmp_path,budget=_fixed_token_estimate(request)+500)
    assert json.loads(prepared['user_prompt'])['observation']==receipt
    reference=json.loads(prepared['tool_history'][1]['content'])
    assert reference['source_text_location']=='request.observation'
    assert prepared['tool_history'][0]==request['tool_history'][0]
    assert prepared['tool_history'][1]['tool_call_id']=='actual'
    assert request==original and not (tmp_path/'memory.json').exists()


def test_repeated_long_source_identifiers_fit_without_losing_identity(tmp_path):
    import hashlib,json
    from backend.ingest.model_memory import prepare_request, expand_source_texts, _fixed_token_estimate
    file_id = hashlib.sha256(b'file').hexdigest()[:32]
    sha = hashlib.sha256(b'original PDF').hexdigest()
    rows = [{'file_id': file_id, 'sha256': sha, 'source_sha256': sha,
             'block_id': hashlib.sha256(f'block-{i % 6}'.encode()).hexdigest(),
             'quote': f'Original coordinate row {i}', 'pressure': i} for i in range(70)]
    payload = {'candidates': rows}
    request = {'system_prompt': 'Read exact original identifiers.', 'user_prompt': json.dumps(payload)}
    budget = _fixed_token_estimate(request) // 2
    prepared = prepare_request(request, tmp_path, budget=budget)
    assert _fixed_token_estimate(prepared) < budget
    assert expand_source_texts(json.loads(prepared['user_prompt'])) == payload
    assert request['user_prompt'] == json.dumps(payload)


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


def test_scientific_tool_history_reserves_space_before_fixed_input_compaction(tmp_path):
    from backend.ingest.model_memory import prepare_request, _fixed_token_estimate, expand_source_texts
    import json
    quote = 'Original YH10 evidence: Tc 303 K at 400 GPa, mu*=0.1. ' * 90
    payload = {'records': [{'id': i, 'tc': 303, 'quote': quote} for i in range(12)]}
    history = [
        {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'page-4', 'type': 'function',
            'function': {'name': 'read_original_page', 'arguments': '{"page":4}'}}]},
        {'role': 'tool', 'tool_call_id': 'page-4', 'content': json.dumps({
            'file_id': 'original', 'blocks': [{'text': f'Independent scientific row {i}, pressure 400 GPa'}
                                             for i in range(150)], 'original_page': 4})},
    ]
    request = {'system_prompt': 'Read all current evidence.', 'user_prompt': json.dumps(payload),
               'tool_history': history, 'images': ['data:image/png;base64,UNCHANGED']}
    budget = _fixed_token_estimate(request) + 100
    prepared = prepare_request(request, tmp_path, budget=budget)
    assert prepared['tool_history'] == history
    assert prepared['images'] == request['images']
    assert expand_source_texts(json.loads(prepared['user_prompt'])) == payload
    assert _fixed_token_estimate(prepared) < _fixed_token_estimate(request) / 2


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


def test_large_repeated_sources_are_losslessly_encoded_before_budget_gate(tmp_path):
    from backend.ingest.model_memory import prepare_request
    import json
    quote='Original scientific evidence YH10 303 K at 400 GPa, mu*=0.1. '*30
    payload={'candidates':[{'candidate_id':f'c{i}','material':'YH10','tc':303.0,'mu_star':0.1,'file_id':'actual-file','block_id':'actual-block','quote':quote} for i in range(10)]}
    request={'system_prompt':'Fixed scientific fields.','user_prompt':json.dumps(payload),'images':[]}
    prepared=prepare_request(request,tmp_path,budget=2400)
    from backend.ingest.model_memory import expand_source_texts
    encoded=json.loads(prepared['user_prompt'])
    assert expand_source_texts(encoded)==payload
    assert request['user_prompt']==json.dumps(payload)
    assert len(prepared['user_prompt'])<len(request['user_prompt'])/2
    assert all(row['file_id']=='actual-file' and row['block_id']=='actual-block' and row['tc']==303 for row in encoded['candidates'])


def test_unique_required_evidence_is_not_truncated_to_fit(tmp_path):
    from backend.ingest.model_memory import prepare_request,ContextBudgetError
    import json,pytest
    payload={'sources':[{'source_id':f's{i}','content':('distinct original evidence '+str(i)+' ')*100} for i in range(10)]}
    original=json.dumps(payload)
    with pytest.raises(ContextBudgetError):prepare_request({'system_prompt':'contract','user_prompt':original},tmp_path,budget=100)
    assert json.loads(original)==payload


def test_transport_dictionary_references_are_not_valid_field_output():
    from backend.ingest.model_memory import validate_context_output
    from backend.rag.structured_output import StructuredOutputError
    import json,pytest
    request={'user_prompt':json.dumps({'_context_texts':{'ctx_unique':'original source'}})}
    with pytest.raises(StructuredOutputError):validate_context_output({'paper':{'summary':'ctx_unique'}},request)
    with pytest.raises(StructuredOutputError):validate_context_output({'paper':{'summary':{'_context_text_ref':'ctx_unique'}}},request)
    validate_context_output({'paper':{'summary':'actual supported summary'}},request)


def test_citation_catalog_keeps_all_text_and_server_owned_binding(tmp_path):
    from backend.ingest.model_memory import prepare_request
    from backend.ingest.state_inventory import _evidence
    import json,hashlib
    file_id=hashlib.sha256(b'file').hexdigest()[:32];file_hash=hashlib.sha256(b'original PDF bytes').hexdigest()
    sources=[{'source_id':f'src-{i}','file_id':file_id,'file_role':'main','source_sha256':file_hash,'source_version':1,
              'block_id':hashlib.sha256(f'original block {i}'.encode()).hexdigest(),'page_start':i+1,'page_end':i+1,
              'content':f'Original scientific row {i}: YH10 Tc 303 K at 400 GPa.'} for i in range(25)]
    payload={'sources':sources,'candidates':[{'candidate_state_key':'existing','evidences':[{'file_id':file_id,'block_id':sources[0]['block_id']}]}]}
    schema={'type':'object','properties':{'source_ids':{'type':'array','items':{'type':'string'}}},'required':['source_ids'],'additionalProperties':False}
    request={'system_prompt':'Read all original text, cite source_ids.','user_prompt':json.dumps(payload),'response_schema':schema}
    prepared=prepare_request(request,tmp_path,budget=2400)
    wire=json.loads(prepared['user_prompt']);groups=wire['sources']['_context_source_catalog']['file_groups']
    rows=[row for group in groups for row in group['sources']]
    assert [(row['source_id'],row['content'],row['page_start']) for row in rows]==[(row['source_id'],row['content'],row['page_start']) for row in sources]
    assert groups[0]['file_id']==file_id and groups[0]['source_sha256']==file_hash
    assert wire['candidates']==payload['candidates']
    assert wire['sources']['_context_source_catalog']['candidate_source_anchors'][0]['block_id']==sources[0]['block_id']
    bound=_evidence(['src-0'],{row['source_id']:row for row in sources})[0]
    assert bound['file_id']==file_id and bound['block_id']==sources[0]['block_id'] and bound['source_version']==1
    assert request['user_prompt']==json.dumps(payload)
