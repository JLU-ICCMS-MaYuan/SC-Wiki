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
    schema = 'scwiki_issue142_test_'+uuid4().hex[:10]
    admin_url = original.set(username='root', password=values['MYSQL_ROOT_PASSWORD'], database=None)
    admin = create_engine(admin_url)
    with admin.begin() as conn: conn.execute(text(f'CREATE DATABASE `{schema}` CHARACTER SET utf8mb4'))
    test_url = admin_url.set(database=schema)
    directory = Path(tempfile.mkdtemp(prefix='scwiki-142-'))
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
        new=migration('20261020_0142_community_ai.py')
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                old.upgrade();new.upgrade();new.downgrade();new.upgrade()
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
                    result={'body':'这是模型 '+model+' 的独立解释 [S1]。'}
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
        from backend.community import configuration, generation, jobs, service
        configs=[('LLM1','模型一',LlmConfig('server:LLM1',f'http://127.0.0.1:{upstream.server_port}/v1','model-one','fixture-key-one',False,'LLM1','模型一')),('LLM2','模型二',LlmConfig('server:LLM2',f'http://127.0.0.1:{upstream.server_port}/v1','model-two','fixture-key-two',False,'LLM2','模型二'))]
        configuration.models=lambda:configs
        service.models=lambda:configs
        source_calls=[]
        def fixture_retrieval(question):
            source_calls.append(question)
            return [{'paper_id':paper_id,'content':'超导体在平衡态表现出迈斯纳效应。','id':'fixture-public-chunk'}]
        # 检索传输使用固定片段；公开论文/版本过滤、引用验证、生成与发布使用真实生产逻辑。
        jobs.retrieve_sources=fixture_retrieval
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
        request_id=str(uuid4())
        payload={'request_id':request_id,'title':'为什么零电阻不等于证明迈斯纳效应？','body':''}
        response=client.post('/api/community/ai/questions',json=payload)
        assert response.status_code==202,response.text
        assert client.post('/api/community/ai/questions',json=payload).json()['id']==request_id
        assert client.post('/api/community/ai/questions',json={**payload,'title':'更换问题内容'}).status_code==409
        fail_models.add('model-two');consume()
        with Session(engine) as db:
            batch=db.get(Batch,request_id);tasks=service.batch_tasks(db,request_id)
            assert batch.state=='partial',(batch.state,[(t.state,t.error) for t in tasks])
            assert [t.state for t in tasks]==['succeeded','failed']
            task1,task2=tasks[0].id,tasks[1].id
            answer1=tasks[0].answer_id
            assert db.get(Entry,answer1).author_id is None
        assert len(source_calls)==1
        requests=[x[1] for x in observed]
        assert requests[0]['messages']==requests[1]['messages']
        assert observed[0][0]=='Bearer fixture-key-one' and observed[1][0]=='Bearer fixture-key-two'
        fail_models.clear()
        assert client.post(f'/api/community/ai/tasks/{task2}/retry').status_code==202
        consume()
        with Session(engine) as db:
            assert db.get(Batch,request_id).state=='succeeded'
            assert len(list(db.scalars(select(Entry).where(Entry.kind=='answer'))))==2
        assert not list(connection.scan_iter('community-ai:credentials:*'))
        print('PASS API role/idempotency, shared sources, real HTTP models, partial failure/retry and credential cleanup',flush=True)
        mode['conflict']=True
        client.post(f'/api/community/ai/tasks/{task1}/retry');consume()
        with Session(engine) as db:
            assert db.get(Entry,answer1).body=='并发人工修订'
            assert db.get(Task,task1).error=='generation_conflict'
        # Worker 中断恢复不更改已发布答案。
        with Session(engine) as db,db.begin():
            task=db.get(Task,task1);task.state='running';task.job_id='missing-job';task.started_at=service.now()-__import__('datetime').timedelta(seconds=800)
        service.reconcile()
        with Session(engine) as db: assert db.get(Task,task1).error=='worker_interrupted'
        # 隐藏期间不能再生成。
        with engine.begin() as conn: conn.execute(text("UPDATE community_entries SET status='hidden',revision=revision+1 WHERE id=:id"),{'id':answer1})
        assert client.post(f'/api/community/ai/tasks/{task1}/retry').status_code==404
        # 两个模型同时完成时，批次汇总不留下 running；重复任务不多发答案。
        concurrent_id=str(uuid4())
        created=client.post('/api/community/ai/questions',json={'request_id':concurrent_id,'title':'如何区分超导能隙与超流刚度？','body':''})
        assert created.status_code==202
        SimpleWorker([queue],connection=connection).work(burst=True,max_jobs=1,logging_level='ERROR')
        with Session(engine) as db:
            task_args=[(t.id,t.job_id) for t in service.batch_tasks(db,concurrent_id)]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair:jobs.run('task',pair[0],pair[1]),task_args))
        consume()  # 队列中同一任务重放不得再次发布。
        with Session(engine) as db:
            batch=db.get(Batch,concurrent_id)
            assert batch.state=='succeeded',batch.state
            assert len(list(db.scalars(select(Entry).where(Entry.question_id==batch.question_id,Entry.kind=='answer'))))==2
        print('PASS concurrent model completion and duplicate task replay',flush=True)
        # 随机提问与全部模型的完整链路。
        generated=client.post('/api/community/ai/questions/generate',json={'request_id':str(uuid4())});assert generated.status_code==202,generated.text
        consume()
        with Session(engine) as db:
            batch=db.get(Batch,generated.json()['id']);assert batch.state=='succeeded',batch.error
            question=db.get(Entry,batch.question_id);assert question.origin=='ai' and question.author_id is None and question.category in generation.CATEGORIES
        print('PASS revision conflict, interrupted worker recovery, hidden content guard, random question pipeline',flush=True)
        # 启动正式双消费者入口，在真实上游请求期间杀掉该测试进程组，再验收恢复。
        mode['stall']=True
        assert client.post(f'/api/community/ai/tasks/{task2}/retry').status_code==202
        worker_log=(directory/'worker.log').open('w')
        actual_worker=subprocess.Popen([sys.executable,'-m','backend.community','worker'],cwd=ROOT,env=os.environ.copy(),start_new_session=True,stdout=worker_log,stderr=worker_log)
        try:
            assert stalled.wait(timeout=15),'real worker did not reach isolated HTTP upstream'
        finally:
            import signal
            # RQ 的 work horse 会另建进程组；逐个清理本测试父进程的后代。
            pairs=[tuple(map(int,line.split())) for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines()]
            descendants={actual_worker.pid}
            while True:
                found={pid for pid,parent in pairs if parent in descendants}
                if found.issubset(descendants):break
                descendants.update(found)
            for pid in reversed(sorted(descendants)):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            actual_worker.wait(timeout=5)
            worker_log.close();mode['stall']=False;release_stall.set()
        with Session(engine) as db,db.begin():
            task=db.get(Task,task2);assert task.state=='running';task.started_at=service.now()-__import__('datetime').timedelta(seconds=800)
        service.reconcile()
        with Session(engine) as db:assert db.get(Task,task2).error=='worker_interrupted'
        connection.delete('community-ai:slot:0','community-ai:slot:1')  # 模拟隔离时钟推进后的租约到期。
        assert not list(connection.scan_iter('community-ai:credentials:*'))
        print('PASS real worker process interruption and task recovery',flush=True)
        with Session(engine) as db,db.begin():
            p=db.get(Paper,paper_id);p.review_status='rejected';p.approved_revision=None
        assert client.post(f'/api/community/ai/tasks/{task2}/retry').status_code==202
        consume()
        with Session(engine) as db: assert db.get(Task,task2).error=='sources_changed'
        # 新迁移降级保护非空数据。
        with engine.begin() as conn:
            try:
                with Operations.context(MigrationContext.configure(conn)):new.downgrade()
            except RuntimeError:pass
            else:raise AssertionError('destructive downgrade allowed')
        print('PASS source revocation and populated migration downgrade guard',flush=True)
        # Go 对同一隔离 MySQL 验证身份、修订及治理。
        go_env={**os.environ,'COMMUNITY_TEST_DSN':f'root:{values["MYSQL_ROOT_PASSWORD"]}@tcp({original.host}:{original.port or 3306})/{schema}?charset=utf8mb4&parseTime=True&loc=UTC','COMMUNITY_TEST_REDIS':f'127.0.0.1:{redis_port}'}
        subprocess.run([str(ROOT/'.local/go/bin/go'),'test','./handlers','-run','TestCommunityMySQL','-count=1'],cwd=ROOT/'goserver',env=go_env,check=True)
        if '--browser' in sys.argv:
            with Session(engine) as db,db.begin():
                p=db.get(Paper,paper_id);p.review_status='approved';p.approved_revision=p.content_revision
                batch=db.get(Batch,generated.json()['id']);question_id=batch.question_id
            from ai_browser_fixture import run as browser_run
            browser_run(ROOT,directory,app,owner_id,question_id)
        # 只导出本次迁移涉及表的结构供部署清单更新，不读取业务数据。
        from scripts.local_deploy.schema import structure
        tables=['community_entries','community_ai_batches','community_ai_tasks','community_entry_revisions']
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
