"""#224：生产调用包装的持续重试、停止及检查点恢复。"""
import threading
from contextlib import nullcontext
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIStatusError
from backend.rag import llm


def setup_runtime(tmp_path, monkeypatch):
    from backend.ingest.model_runtime import ModelRuntime, execution_context
    state = {'task_id':'a'*32,'status':'reading','execution_generation':1,'files':[], 'user_id':1}
    def update(**changes):state.update(changes);return dict(state)
    runtime=ModelRuntime('a'*32,1,tmp_path,lambda:dict(state),update,lambda:nullcontext(), identity={'model':'fixture'})
    monkeypatch.setattr(runtime,'wait',lambda seconds:runtime.check())
    return runtime,execution_context,state


def test_four_503s_are_recorded_then_complete_and_replayed(tmp_path,monkeypatch):
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    request=httpx.Request('POST','https://model.invalid')
    calls=[]
    def complete(*args,**kwargs):
        calls.append(1)
        if len(calls)<5:raise APIStatusError('private',response=httpx.Response(503,request=request),body={'error':{'code':'service_unavailable','message':'temporary','request_id':'req-123','retry_after_seconds':0}})
        return {'value':42}
    monkeypatch.setattr(llm,'_complete_json',complete)
    with context(runtime): assert llm.complete_json('fixed contract','current original')=={'value':42}
    assert len(calls)==5
    assert len(list(tmp_path.rglob('failure-*.json')))==4
    second,context,_=setup_runtime(tmp_path,monkeypatch)
    with context(second): assert llm.complete_json('fixed contract','current original')=={'value':42}
    assert len(calls)==5


def test_stop_during_blocked_request_rejects_late_result(tmp_path,monkeypatch):
    from backend.ingest.model_runtime import ExecutionStopped
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    entered=threading.Event();release=threading.Event();finished=threading.Event()
    def complete(*args,**kwargs):entered.set();release.wait(3);finished.set();return {'value':'late'}
    monkeypatch.setattr(llm,'_complete_json',complete)
    def stop():
        assert entered.wait(2)
        state.update(status='pausing',execution_generation=2)
    thread=threading.Thread(target=stop);thread.start()
    with context(runtime),pytest.raises(ExecutionStopped):llm.complete_json('system','source')
    release.set();thread.join();assert finished.wait(2)
    assert not list(tmp_path.rglob('result.json'))
    import time,json
    end=time.monotonic()+2
    while not list((tmp_path/'late').glob('*.json')) and time.monotonic()<end:time.sleep(.01)
    late=json.loads(next((tmp_path/'late').glob('*.json')).read_text())
    assert late['status']=='late_ignored' and late['result']=={'value':'late'}


def test_fixed_error_stops_and_does_not_publish_secrets(tmp_path,monkeypatch):
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    req=httpx.Request('POST','https://model.invalid')
    def complete(*args,**kwargs):raise APIStatusError('Bearer super-secret',response=httpx.Response(401,request=req),body={'error':{'message':'api_key=super-secret Bearer secret-token'}})
    monkeypatch.setattr(llm,'_complete_json',complete)
    with context(runtime),pytest.raises(Exception):llm.complete_json('s','u')
    assert 'super-secret' not in str(state.get('model_activity'))
    assert len(list(tmp_path.rglob('failure-*.json')))==1


def test_paused_state_cannot_be_revived_by_late_progress():
    from backend.ingest.upload_contracts import apply_state_changes
    from backend.ingest.model_runtime import ExecutionStopped
    with pytest.raises(ExecutionStopped):apply_state_changes({'status':'paused'},now=100,status='ready')
    paused=apply_state_changes({'status':'reading'},now=100,status='paused')
    assert paused['cleanup_at'] is None


@pytest.mark.parametrize('first_response',['503','empty_sse'])
def test_real_openai_stream_recovers_unanswered_attempts_and_disk_resume(tmp_path,monkeypatch,first_response):
    """真实OpenAI客户端/HTTP/SSE/严格校验/落盘/重读；不访问业务API。"""
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from openai import OpenAI
    import json
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if len(seen)<5 and first_response=='empty_sse':
                body=b'data: [DONE]\n\n'
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            elif len(seen)<5:
                body=json.dumps({'error':{'code':'service_unavailable','message':'fixture-503','output_started':False,'retryable':True}}).encode()
                self.send_response(503);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            else:
                body=('data: '+json.dumps({'id':'fixture','object':'chat.completion.chunk','choices':[{'index':0,'delta':{'content':'{"answer":42}'},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode()
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(llm,'_client',lambda timeout:OpenAI(api_key='isolated-fixture',base_url=f'http://127.0.0.1:{server.server_port}/v1',max_retries=0))
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='fixture'))
    schema={'type':'object','properties':{'answer':{'type':'integer'}},'required':['answer'],'additionalProperties':False}
    try:
        runtime,context,state=setup_runtime(tmp_path,monkeypatch)
        with context(runtime):assert llm.complete_json('fixed schema','original evidence',response_schema=schema)=={'answer':42}
        assert len(seen)==5 and all(request==seen[0] for request in seen)
        runtime2,context,_=setup_runtime(tmp_path,monkeypatch)
        with context(runtime2):assert llm.complete_json('fixed schema','original evidence',response_schema=schema)=={'answer':42}
        assert len(seen)==5
    finally:server.shutdown();server.server_close()


def test_resume_is_idempotent_and_rejects_changed_draft(monkeypatch):
    from backend.ingest import upload_tasks,model_runtime
    from backend.ingest.upload_contracts import apply_state_changes
    state={'status':'paused','execution_generation':2,'user_id':1,'files':[],'execution_draft_hash':model_runtime.digest({'value':'current'})}
    draft={'value':'current'};enqueued=[]
    monkeypatch.setattr(upload_tasks,'get_state',lambda _:dict(state))
    monkeypatch.setattr(upload_tasks,'get_draft',lambda _:dict(draft))
    monkeypatch.setattr(upload_tasks,'upload_task_lock',lambda _:nullcontext())
    monkeypatch.setattr(upload_tasks,'redis_client',lambda:NS(get=lambda _:None,persist=lambda _:None))
    def update(_,**changes):state.update(apply_state_changes(state,now=100,**changes));return dict(state)
    monkeypatch.setattr(upload_tasks,'update_state',update)
    monkeypatch.setattr(upload_tasks,'enqueue_processing',lambda _:enqueued.append(1))
    from backend.rag import llm_context
    monkeypatch.setattr(llm_context,'get_llm_config',lambda:NS(provider='fixture',model='fixture',catalog_id=None))
    assert model_runtime.resume_task('a'*32)['status']=='queued'
    assert model_runtime.resume_task('a'*32)['status']=='queued'
    assert len(enqueued)==1
    state['status']='paused';draft['value']='human changed'
    with pytest.raises(ValueError,match='草稿已变化'):model_runtime.resume_task('a'*32)
    assert len(enqueued)==1


def test_pause_and_resume_require_owner_even_for_admin(monkeypatch):
    from backend.api.upload_tasks import pause_upload_task,resume_upload_task
    from backend.ingest import upload_tasks
    from fastapi import HTTPException
    monkeypatch.setattr(upload_tasks,'get_state',lambda _:dict(user_id=1,status='reading'))
    admin=NS(id=2,role='superadmin',is_approved=True)
    for operation in [pause_upload_task,resume_upload_task]:
        with pytest.raises(HTTPException) as raised:operation('a'*32,admin)
        assert raised.value.status_code==403


def test_pause_stops_only_its_own_started_rq_job(monkeypatch):
    from backend.ingest import model_runtime,upload_tasks
    from rq.job import Job
    import rq.command
    task_id='a'*32;connection=object();stops=[]
    monkeypatch.setattr(upload_tasks,'upload_queue',lambda:NS(connection=connection))
    monkeypatch.setattr(model_runtime,'_pause_task_state',lambda _:dict(status='pausing',job_id='owned-job'))
    monkeypatch.setattr(upload_tasks,'redis_client',lambda: (_ for _ in ()).throw(AssertionError('不能用decode_responses=True的Redis读取RQ二进制作业')))
    monkeypatch.setattr(Job,'fetch',lambda identifier,connection:NS(id=identifier,args=[task_id],get_status=lambda **_: 'started'))
    monkeypatch.setattr(rq.command,'send_stop_job_command',lambda connection,identifier:stops.append(identifier))
    assert model_runtime.pause_task(task_id)['status']=='pausing'
    assert stops==['owned-job']
    monkeypatch.setattr(Job,'fetch',lambda identifier,connection:NS(id=identifier,args=['other-task'],get_status=lambda **_: 'started'))
    model_runtime.pause_task(task_id)
    assert stops==['owned-job']


def test_stopped_rq_job_reconciles_but_live_job_does_not(monkeypatch):
    from backend.ingest import model_runtime,upload_tasks
    from rq.job import Job
    state={'status':'pausing','job_id':'owned-job','execution_generation':4,'model_activity':{'phase':'structure_reading'}}
    status=['stopped'];writes=[]
    monkeypatch.setattr(upload_tasks,'upload_queue',lambda:NS(connection=object()))
    monkeypatch.setattr(upload_tasks,'upload_task_lock',lambda _:nullcontext())
    monkeypatch.setattr(upload_tasks,'get_state',lambda _:dict(state))
    monkeypatch.setattr(upload_tasks,'get_draft',lambda _: {'current':'draft'})
    monkeypatch.setattr(Job,'fetch',lambda *_,**__:NS(get_status=lambda **_:status[0]))
    def update(_,**changes):writes.append(changes);state.update(changes);return dict(state)
    monkeypatch.setattr(upload_tasks,'update_state',update)
    assert model_runtime.reconcile_execution('a'*32,dict(state))['status']=='paused'
    assert state['execution_generation']==5 and state['model_activity']['status']=='paused'
    state['status']='pausing';status[0]='started'
    assert model_runtime.reconcile_execution('a'*32,dict(state))['status']=='pausing'
    assert len(writes)==1


def test_context_overflow_keeps_provider_code_for_compression(monkeypatch):
    request=httpx.Request('POST','https://model.invalid')
    error=APIStatusError('context limit',response=httpx.Response(400,request=request),body={'error':{'code':'context_length_exceeded'}})
    def stream(*args,**kwargs):raise error
    monkeypatch.setattr(llm,'_stream_json',stream)
    from backend.ingest.model_runtime import context_overflow
    with pytest.raises(APIStatusError) as raised:llm._complete_json('contract','evidence',response_schema={'type':'object','properties':{},'additionalProperties':False},_single_attempt=True)
    assert context_overflow(raised.value)


def test_explicit_non_retryable_service_error_is_not_retried():
    from backend.ingest.model_runtime import transient
    req=httpx.Request('POST','https://model.invalid')
    error=APIStatusError('fixed failure',response=httpx.Response(503,request=req),body={'error':{'retryable':False}})
    assert not transient(error)


def test_receiving_transition_is_logged_once_per_request(tmp_path,monkeypatch):
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    import time
    def complete(*args,**kwargs):
        for _ in range(5):runtime.receiving.set();time.sleep(.25)
        return {'value':42}
    monkeypatch.setattr(llm,'_complete_json',complete)
    with context(runtime):assert llm.complete_json('system','source')=={'value':42}
    assert sum(event['status']=='receiving' for event in state['model_activity']['history'])==1


def test_full_event_journal_keeps_earlier_entries(tmp_path,monkeypatch):
    from backend.ingest.model_runtime import read_events
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    for i in range(120):runtime.event('requesting',attempt=i+1)
    assert len(state['model_activity']['history'])==100
    latest=read_events(tmp_path,limit=100)
    assert latest['has_more'] and latest['events'][0]['attempt']==21
    earlier=read_events(tmp_path,before=latest['events'][0]['updated_at'],limit=100)
    assert not earlier['has_more'] and [row['attempt'] for row in earlier['events']]==list(range(1,21))


def test_history_api_reads_owned_journal_with_pagination(tmp_path,monkeypatch):
    import json
    from backend.api import upload_tasks as api
    from backend.ingest import upload_tasks
    state={'status':'paused','user_id':1,'execution_input_hash':'input-hash'}
    monkeypatch.setattr(upload_tasks,'get_state',lambda _:dict(state))
    monkeypatch.setattr(upload_tasks,'artifact_directory',lambda _:tmp_path)
    monkeypatch.setattr(upload_tasks,'upload_task_lock',lambda _:nullcontext())
    directory=tmp_path/'model-runtime'/'input-hash';directory.mkdir(parents=True)
    (directory/'events.jsonl').write_text('\n'.join(json.dumps({'status':'requesting','updated_at':i}) for i in range(1,5))+'\n')
    user=NS(id=1,role='user',is_approved=True)
    result=api.get_model_activity('a'*32,before=4,limit=2,current_user=user)
    assert result['data']=={'events':[{'status':'requesting','updated_at':2},{'status':'requesting','updated_at':3}],'has_more':True}


def test_dns_failure_remains_transport_error_and_retries(tmp_path,monkeypatch):
    from backend.rag.llm_context import UserCredentialError
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    calls=[]
    def client(_):
        calls.append(1)
        if len(calls)==1:raise UserCredentialError('无法解析 Base URL 主机',code='LLM_URL_UNRESOLVABLE')
        return NS(chat=NS(completions=NS(create=lambda **_:iter([NS(choices=[NS(delta=NS(content='{"value":42}',tool_calls=None),finish_reason='stop')])]))))
    monkeypatch.setattr(llm,'_client',client)
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='fixture'))
    schema={'type':'object','properties':{'value':{'type':'integer'}},'required':['value'],'additionalProperties':False}
    with context(runtime):assert llm.complete_json('fixed contract','original evidence',response_schema=schema)=={'value':42}
    assert len(calls)==2
    import json
    failure=json.loads(next(tmp_path.rglob('failure-*.json')).read_text())
    assert failure['error']['code']=='LLM_URL_UNRESOLVABLE'
    assert failure['error']['error_type']=='UserCredentialError'


def test_unsafe_url_stops_with_original_code_without_retry(tmp_path,monkeypatch):
    from backend.rag.llm_context import UserCredentialError
    runtime,context,state=setup_runtime(tmp_path,monkeypatch)
    calls=[]
    def client(_):calls.append(1);raise UserCredentialError('Base URL 不允许访问内网地址',code='LLM_URL_PRIVATE')
    monkeypatch.setattr(llm,'_client',client)
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='fixture'))
    with context(runtime),pytest.raises(Exception):llm.complete_json('contract','source',response_schema={'type':'object','properties':{},'additionalProperties':False})
    assert len(calls)==1
    assert state['model_activity']['error']['code']=='LLM_URL_PRIVATE'


def test_dns_does_not_destroy_snapshot_and_actual_connection_still_checks_private_ip(monkeypatch):
    import json
    from backend.ingest import upload_tasks
    from backend.rag import llm_context,llm_client
    from backend.rag.llm_context import UserCredentialError
    deleted=[]
    stored={'provider':'server:fixture','base_url':'https://model.example.invalid/v1','model':'fixture','api_key':'test-only-key','catalog_id':'fixture'}
    monkeypatch.setattr(upload_tasks,'redis_client',lambda:NS(get=lambda _:json.dumps(stored),delete=lambda key:deleted.append(key)))
    def dns(_):raise UserCredentialError('无法解析 Base URL 主机',code='LLM_URL_UNRESOLVABLE')
    monkeypatch.setattr(upload_tasks,'validate_base_url',dns)
    config=upload_tasks.load_llm_config('a'*32)
    assert config is not None and config.model=='fixture' and not deleted
    monkeypatch.setattr(llm_context.socket,'getaddrinfo',lambda *_,**__:[(None,None,None,None,('10.0.0.1',443))])
    token=llm_context.set_llm_config(config)
    try:
        with pytest.raises(UserCredentialError) as error:llm_client.get_llm_client()
        assert error.value.code=='LLM_URL_PRIVATE'
    finally:llm_context.reset_llm_config(token)


def test_nonempty_invalid_json_remains_blocked_without_regeneration(tmp_path,monkeypatch):
    runtime,context,state=setup_runtime(tmp_path,monkeypatch);calls=[]
    def create(**_):calls.append(1);return iter([NS(choices=[NS(delta=NS(content='{broken',tool_calls=None),finish_reason='stop')])])
    monkeypatch.setattr(llm,'_client',lambda _:NS(chat=NS(completions=NS(create=create))))
    monkeypatch.setattr(llm,'get_llm_config',lambda:NS(model='fixture'))
    schema={'type':'object','properties':{},'additionalProperties':False}
    with context(runtime),pytest.raises(Exception):llm.complete_json('contract','source',response_schema=schema)
    assert len(calls)==1
    assert state['model_activity']['error']['error_type']=='StructuredOutputError'
