"""#142：隔离 MySQL/Redis、真实 HTTP 模型与 RQ 消费者验收。"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text, inspect, select
    from sqlalchemy.engine import make_url
    values = dotenv_values(ROOT/'.env')
    # 只读配置；新建隔离库，绝不修改配置所指向的业务库。
    original = make_url(values['DATABASE_URL'])
    schema = 'scwiki_issue143_test_'+uuid4().hex[:10]
    admin_url = original.set(username='root', password=values['MYSQL_ROOT_PASSWORD'], database=None)
    admin = create_engine(admin_url)
    with admin.begin() as conn: conn.execute(text(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'))
    test_url = admin_url.set(database=schema)
    directory = Path(tempfile.mkdtemp(prefix='scwiki-143-'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); redis_port=sock.getsockname()[1]
    redis_process = subprocess.Popen([str(Path(sys.executable).parent/'redis-server'),'--bind','127.0.0.1','--port',str(redis_port),'--save','','--appendonly','no','--dir',str(directory)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    os.environ.update(DATABASE_URL=test_url.render_as_string(hide_password=False),RAG_DATABASE_URL=test_url.set(drivername='mysql+asyncmy').render_as_string(hide_password=False),REDIS_URL=f'redis://127.0.0.1:{redis_port}/0',JWT_SECRET_KEY='isolated-community-test-secret')
    upstream=None
    try:
        from redis import Redis
        connection=Redis.from_url(os.environ['REDIS_URL'])
        for _ in range(50):
            try: connection.ping();break
            except Exception: time.sleep(.1)
        from backend.database import Base, engine
        from backend.models import User, Paper
        from backend.community.models import CommunityEntry as Entry, CommunityAIBatch as Batch, CommunityAITask as Task
        from sqlalchemy.orm import Session
        # 只建立所需基础表，社区表先走旧迁移，再走真实新增迁移。
        Base.metadata.create_all(engine,tables=[User.__table__,Paper.__table__])
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        def migration(filename):
            spec=importlib.util.spec_from_file_location('test_migration',ROOT/'alembic/versions'/filename)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        old=migration('20260917_0107_community_discussion.py')
        base=migration('20261020_0142_community_ai.py')
        threads=migration('20261020_0143_answer_threads.py')
        new=migration('20261020_0143b_answer_groups.py')
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                old.upgrade();base.upgrade();threads.upgrade();new.upgrade();new.downgrade();new.upgrade()
        print('PASS migration upgrade/downgrade/upgrade',flush=True)
        with Session(engine) as db,db.begin():
            user=User(email='owner@example.test',username='owner',real_name='Owner',password_hash='unused',role='superadmin',account_status='active',is_email_verified=True)
            db.add(user);db.flush();owner_id=user.id
            # Paper 有必要字段默认值，由现有模型负责。
            paper=Paper(year=2026,title='公开测试文献',doi='10.0000/test142',review_status='approved',content_revision=1,approved_revision=1)
            db.add(paper);db.flush();paper_id=paper.id
        observed=[];fail_models=set();mode={'conflict':False,'invalid':False,'stall':False}; stalled=threading.Event(); release_stall=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                observed.append((self.headers.get('Authorization'),payload))
                model=payload['model']
                if mode['stall']:
                    stalled.set();release_stall.wait(timeout=20)
                if model in fail_models:
                    self.send_response(503);self.end_headers();return
                system=payload['messages'][0]['content']
                if '生成一个超导研究问题' in system: result={'title':'为什么超导体排斥磁场？','body':'讨论平衡态磁响应。'}
                elif '判断候选问题' in system: result={'duplicate':False}
                else:
                    context=json.loads(payload['messages'][1]['content']).get('previous_answers',[])
                    result={'body':'这是模型 '+model+' 的新角度 [S1]。'+('回应 ['+context[-1]['key']+']。' if context else '')}
                    if mode['invalid']:result={'body':'假引用 [S99]'}
                    if mode['conflict']:
                        mode['conflict']=False
                        with engine.begin() as conn:
                            conn.execute(text("UPDATE community_entries SET body='并发人工修订', revision=revision+1, human_edited=1 WHERE kind='answer' AND model_id='LLM1'"))
                content=json.dumps(result,ensure_ascii=False)
                if payload.get('stream'):
                    events=[{'id':'test','object':'chat.completion.chunk','created':0,'model':model,'choices':[{'index':0,'delta':{'role':'assistant','content':content},'finish_reason':None}]},
                            {'id':'test','object':'chat.completion.chunk','created':0,'model':model,'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
                    data=(''.join('data: '+json.dumps(event)+'\n\n' for event in events)+'data: [DONE]\n\n').encode()
                    content_type='text/event-stream'
                else:
                    data=json.dumps({'id':'test','object':'chat.completion','created':0,'model':model,'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]}).encode()
                    content_type='application/json'
                self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
            def log_message(self,*args):pass
        upstream=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=upstream.serve_forever,daemon=True).start()
        from backend.rag.llm_context import LlmConfig
        from backend.community import configuration, generation, jobs, service, answers
        configs=[('LLM1','DeepSeek',LlmConfig('server:LLM1',f'http://127.0.0.1:{upstream.server_port}/v1','model-one','fixture-key-one',False,'LLM1','DeepSeek')),('LLM2','OpenAI',LlmConfig('server:LLM2',f'http://127.0.0.1:{upstream.server_port}/v1','model-two','fixture-key-two',False,'LLM2','OpenAI'))]
        configuration.models=lambda:configs
        service.models=lambda:configs
        answers.models=lambda:configs
        source_calls=[]
        def fixture_retrieval(question):
            source_calls.append(question)
            return [{'paper_id':paper_id,'content':'超导体在平衡态表现出迈斯纳效应。','id':'fixture-public-chunk'}]
        # 检索传输使用固定片段；公开论文/版本过滤、引用验证、生成与发布使用真实生产逻辑。
        jobs.retrieve_sources=fixture_retrieval
        answers.retrieve_sources=fixture_retrieval
        from rq import Queue, SimpleWorker
        queue=Queue(configuration.QUEUE,connection=connection)
        def consume():
            SimpleWorker([queue],connection=connection).work(burst=True,logging_level='ERROR')
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.api import community_ai
        from backend.security import get_current_user
        app=FastAPI();app.include_router(community_ai.router)
        role={'value':'superadmin'}
        def user_dependency():
            with Session(engine) as db:
                value=db.get(User,owner_id);db.expunge(value)
            value.role=role['value'];return value
        app.dependency_overrides[get_current_user]=user_dependency
        client=TestClient(app, headers={"Authorization":"Bearer fixture-auth"})
        for value in ('user','admin'):
            role['value']=value
            assert client.post('/api/community/ai/questions/generate',json={'request_id':str(uuid4())}).status_code==403
        role['value']='superadmin'
        from backend.community.models import CommunityAnswerRequest as AnswerRequest, CommunityAnswerTurn as Turn, CommunityModelAnswer as Card, CommunityAnswerGroup as Group
        request_id=str(uuid4())
        payload={'request_id':request_id,'title':'为什么零电阻不等于证明迈斯纳效应？','body':''}
        response=client.post('/api/community/ai/questions',json=payload)
        assert response.status_code==202,response.text
        question_id=response.json()['question_id']
        assert queue.count==0, 'question creation must not schedule answers'
        options=client.get('/api/community/ai/models').json()['items']
        def add(index, rid=None):
            result=client.post(f'/api/community/ai/questions/{question_id}/answers',json={'request_id':rid or str(uuid4()),'model_key':options[index]['key']})
            assert result.status_code==202,result.text
            return result.json()
        first_id=str(uuid4());r1=add(0,first_id);assert add(0,first_id)['id']==r1['id']
        r2=add(1);r3=add(0)
        assert queue.count==1,'only the head should be dispatched'
        consume()
        with Session(engine) as db:
            requests=list(db.scalars(select(AnswerRequest).order_by(AnswerRequest.sequence)))
            assert [r.state for r in requests]==['succeeded']*3,[(r.state,r.error) for r in requests]
            assert len(list(db.scalars(select(Card))))==2
            assert len(list(db.scalars(select(Turn))))==1
            first_answer=db.get(Entry,requests[0].answer_id)
            first_body=first_answer.body
            assert requests[0].answer_id==requests[2].answer_id
            assert len(requests[1].context_snapshot)==1 and len(requests[2].context_snapshot)==2
        actual=[json.loads(p['messages'][1]['content']) for _,p in observed]
        assert [len(p['previous_answers']) for p in actual]==[0,1,2]
        assert actual[2]['previous_answers'][0]['body']==first_body
        assert 'secret' not in str(client.get(f'/api/community/ai/questions/{question_id}/queue').json())
        assert not list(connection.scan_iter('community-ai:credentials:*'))
        print('PASS manual question does not answer, FIFO A-B-A, two cards/three responses, full context at execution, idempotency',flush=True)
        # 无效模型或第二个凭据写入失败时整组回滚，不得留下第一项。
        def batch(keys,rid=None):
            return client.post(f'/api/community/ai/questions/{question_id}/answers/batch',json={'request_id':rid or str(uuid4()),'model_keys':keys})
        with Session(engine) as db: before=len(list(db.scalars(select(AnswerRequest))));groups_before=len(list(db.scalars(select(Group))))
        assert batch([options[0]['key'],'f'*64]).status_code==409
        assert batch([options[0]['key'],options[0]['key']]).status_code==409
        assert batch([]).status_code==422
        from redis.exceptions import RedisError
        original_save=answers.save_configs;credential_calls=[]
        def fail_second(conn,job_id,configs):
            original_save(conn,job_id,configs);credential_calls.append(job_id)
            if len(credential_calls)==2:raise RedisError('isolated second-write failure')
        answers.save_configs=fail_second
        try: assert batch([options[0]['key'],options[1]['key']]).status_code==503
        finally: answers.save_configs=original_save
        with Session(engine) as db:
            assert len(list(db.scalars(select(AnswerRequest))))==before
            assert len(list(db.scalars(select(Group))))==groups_before
        assert not list(connection.scan_iter('community-ai:credentials:*'))
        for role_value in ('user','admin'):
            role['value']=role_value
            assert batch([options[0]['key']]).status_code==403
        role['value']='superadmin'
        batch_id=str(uuid4());group=batch([options[1]['key'],options[0]['key']],batch_id)
        assert group.status_code==202,group.text
        original_ids=[item['id'] for item in group.json()['items']]
        assert [item['model_name'] for item in group.json()['items']]==['OpenAI','DeepSeek']
        assert [item['id'] for item in batch([options[1]['key'],options[0]['key']],batch_id).json()['items']]==original_ids
        assert batch([options[0]['key'],options[1]['key']],batch_id).status_code==409
        assert queue.count==1
        consume()
        with Session(engine) as db: assert all(db.get(AnswerRequest,i).state=='succeeded' for i in original_ids)
        from concurrent.futures import ThreadPoolExecutor
        concurrent_uuid=str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:batch([options[0]['key'],options[1]['key']],concurrent_uuid),range(2)))
        assert all(response.status_code==202 for response in responses)
        assert [item['id'] for item in responses[0].json()['items']]==[item['id'] for item in responses[1].json()['items']]
        consume()
        fail_models.add('model-two')
        partial=batch([options[1]['key'],options[0]['key']]);assert partial.status_code==202
        consume();fail_models.clear()
        with Session(engine) as db:
            assert [db.get(AnswerRequest,item['id']).state for item in partial.json()['items']]==['failed','succeeded']
        print('PASS atomic multi-model submission, concurrency/idempotency, invalid model/Redis rollback, role checks, partial generation failure continues',flush=True)

        fail_models.add('model-two');failed=add(1);following=add(0);consume();fail_models.clear()
        with Session(engine) as db:
            assert db.get(AnswerRequest,failed['id']).state=='failed'
            assert db.get(AnswerRequest,following['id']).state=='succeeded'
        retry=client.post(f"/api/community/ai/answer-requests/{failed['id']}/retry",json={'request_id':str(uuid4())})
        assert retry.status_code==202 and retry.json()['sequence']>following['sequence']
        consume()
        with Session(engine) as db:assert db.get(AnswerRequest,retry.json()['id']).state=='succeeded'
        mode['conflict']=True;conflict=add(0);consume()
        with Session(engine) as db:
            assert db.get(AnswerRequest,conflict['id']).error=='generation_conflict'
            turn=db.scalar(select(Turn).order_by(Turn.id));turn_id,rev=turn.id,turn.revision
        edited=client.patch(f'/api/community/ai/turns/{turn_id}',json={'body':'人工补充修订','revision':rev})
        assert edited.status_code==200,edited.text
        assert client.patch(f'/api/community/ai/turns/{turn_id}',json={'body':'过期覆盖','revision':rev}).status_code==409
        assert client.get(f'/api/community/ai/turns/{turn_id}/revisions').json()['items'][0]['revision']==rev
        print('PASS failure continues, retry at end, concurrent edit protection, segment editing/revisions',flush=True)
        # 先派发再模拟进程中断，监督必须恢复并继续题内队列。
        interrupted=add(1);after=add(0)
        with Session(engine) as db,db.begin():
            r=db.get(AnswerRequest,interrupted['id']);r.state='running';r.started_at=service.now()-__import__('datetime').timedelta(seconds=800)
        answers.reconcile_answers();consume()
        with Session(engine) as db:
            assert db.get(AnswerRequest,interrupted['id']).state=='failed'
            assert db.get(AnswerRequest,after['id']).state=='succeeded'
            # 隐藏卡片不能再追加。
            entry=db.get(Entry,r1['answer_id']) if r1.get('answer_id') else db.get(Entry,db.get(AnswerRequest,r1['id']).answer_id)
            card_id=entry.id
        with engine.begin() as conn:conn.execute(text("UPDATE community_entries SET status='hidden',revision=revision+1 WHERE id=:id"),{'id':card_id})
        rejected=client.post(f'/api/community/ai/questions/{question_id}/answers',json={'request_id':str(uuid4()),'model_key':options[0]['key']})
        assert rejected.status_code==404
        with Session(engine) as db:
            assert all(row['entry_id']!=card_id for row in answers.context_rows(db,question_id))
        with engine.begin() as conn:conn.execute(text("UPDATE community_entries SET status='visible',revision=revision+1 WHERE id=:id"),{'id':card_id})
        random=client.post('/api/community/ai/questions/generate',json={'request_id':str(uuid4())});assert random.status_code==202
        consume()
        with Session(engine) as db:
            batch=db.get(Batch,random.json()['id']);assert batch.state=='succeeded'
            assert not list(db.scalars(select(Entry).where(Entry.question_id==batch.question_id,Entry.kind=='answer')))
        print('PASS worker recovery, hidden-card protection, random question does not auto-answer',flush=True)
        # 在正式 SpawnWorker 的 HTTP 请求期间中断进程，再验证后续任务继续。
        with Session(engine) as db,db.begin():
            p=db.get(Paper,paper_id);p.review_status='rejected';p.approved_revision=None
        mode['stall']=True
        live_request=add(1)
        worker_log=(directory/'worker.log').open('w')
        actual_worker=subprocess.Popen([sys.executable,'-m','backend.community','worker'],cwd=ROOT,env=os.environ.copy(),start_new_session=True,stdout=worker_log,stderr=worker_log)
        try:
            assert stalled.wait(timeout=20),'real worker did not reach HTTP upstream'
        finally:
            import signal
            pairs=[tuple(map(int,line.split())) for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines()]
            descendants={actual_worker.pid}
            while True:
                found={pid for pid,parent in pairs if parent in descendants}
                if found.issubset(descendants):break
                descendants.update(found)
            for pid in descendants:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            actual_worker.wait(timeout=5);worker_log.close();mode['stall']=False;release_stall.set()
        with Session(engine) as db,db.begin():
            request=db.get(AnswerRequest,live_request['id']);assert request.state=='running';request.started_at=service.now()-__import__('datetime').timedelta(seconds=800)
            p=db.get(Paper,paper_id);p.review_status='approved';p.approved_revision=p.content_revision
        answers.reconcile_answers()
        connection.delete('community-ai:slot:0','community-ai:slot:1')
        resumed=client.post(f"/api/community/ai/answer-requests/{live_request['id']}/retry",json={'request_id':str(uuid4())})
        assert resumed.status_code==202
        consume()
        with Session(engine) as db:assert db.get(AnswerRequest,resumed.json()['id']).state=='succeeded'
        print('PASS real worker interruption, tail retry and next-answer recovery',flush=True)

        with engine.begin() as conn:
            try:
                with Operations.context(MigrationContext.configure(conn)):new.downgrade()
            except RuntimeError:pass
            else:raise AssertionError('destructive downgrade allowed')
        if '--browser' in sys.argv:
            app.dependency_overrides.clear()
            from ai_browser_fixture import run as browser_run
            os.environ['COMMUNITY_BROWSER_SCRIPT']='answer-threads-browser.mjs'
            browser_run(ROOT,directory,app,owner_id,question_id)
        # 只导出本次迁移涉及表的结构供部署清单更新，不读取业务数据。
        from scripts.local_deploy.schema import structure
        tables=['community_model_answers','community_answer_requests','community_answer_turns','community_answer_turn_revisions','community_answer_groups']
        (directory/'schema.json').write_text(json.dumps({name:structure(inspect(engine),name) for name in tables},ensure_ascii=False,indent=2))
        (directory/'result.json').write_text(json.dumps({'status':'passed','database':schema,'models':2,'source_transport':'fixture; real publication/version checks','schema_file':str(directory/'schema.json')},ensure_ascii=False,indent=2))
        print('RESULT '+str(directory/'result.json'),flush=True)
    finally:
        if upstream:upstream.shutdown();upstream.server_close()
        redis_process.terminate();redis_process.wait(timeout=10)
        # 只清理此进程新建的隔离数据库。
        with admin.begin() as conn:conn.execute(text(f'DROP DATABASE `{schema}`'))
        admin.dispose()

if __name__=='__main__':main()
