"""#186：显式隔离数据库中的真实单字段保存；不调用模型，不连接业务库。"""
import os,json,time,statistics,hashlib,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests/01_decentralized_uploading'))
from test_upload_extraction_timing import MemoryRedis
from backend import models,database
from backend.ingest import upload_tasks,field_drafts
from backend.services.workdrafts import open_draft

url=make_url(os.environ['SCWIKI_PERF_DATABASE_URL'])
assert url.drivername.startswith('mysql') and url.host in {'127.0.0.1','localhost'}
assert (url.database or '').startswith('scwiki_issue139_test_six_')
engine=create_engine(url);factory=sessionmaker(engine,expire_on_commit=False)
client=MemoryRedis();task=uuid4().hex
draft=json.loads(Path(os.environ['WORKDRAFT_PERF_DRAFT']).read_text())
draft['_field_edit_format']=1
with factory.begin() as session:
    user=models.User(username='perf'+task[:12],email=task+'@perf.invalid',real_name='隔离性能验证',
        password_hash='isolated',role='user',is_approved=True)
    session.add(user);session.flush()
owner=user
state={'task_id':task,'user_id':owner.id,'status':'ready','stage':'ready','processing_status':'succeeded'}
client.set(upload_tasks.task_key(task),json.dumps(state))
client.set(upload_tasks.draft_key(task),json.dumps(draft))
database.SessionLocal=factory
upload_tasks.redis_client=lambda:client
with factory.begin() as session:
    lease=open_draft(session,'upload',task,owner)
    version=lease.write_epoch+':initial'
sql=[]
@event.listens_for(engine,'before_cursor_execute')
def before(conn,cursor,statement,parameters,context,executemany):
    context.workdraft_perf_start=time.perf_counter()
@event.listens_for(engine,'after_cursor_execute')
def after(conn,cursor,statement,parameters,context,executemany):
    sql.append((time.perf_counter()-context.workdraft_perf_start)*1000)
samples=[]
old=draft['paper']['knowledge_graph_title']
for index in range(5):
    sql.clear();start=time.perf_counter()
    value='Isolated benchmark '+str(index)
    changes=[{'path':['paper','knowledge_graph_title'],'before':old,'value':value}]
    with factory.begin() as session:
        result=field_drafts.save_fields(session,'upload',task,owner,version,changes)
    assert result['changed']
    total=(time.perf_counter()-start)*1000
    samples.append({'service_and_commit_ms':total,'sql_driver_and_loopback_ms':sum(sql),
        'sql_statements':len(sql),'http_delta_bytes':len(json.dumps(changes).encode())})
    old=value;version=result['version']
report={'database':url.database,'host':'本机127.0.0.1','fixture_bytes':len(json.dumps(draft).encode()),
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
    ['backend/ingest/field_drafts.py','backend/ingest/upload_tasks.py']},
    'samples':samples,'mean_service_and_commit_ms':statistics.mean(s['service_and_commit_ms'] for s in samples),
    'mean_sql_driver_and_loopback_ms':statistics.mean(s['sql_driver_and_loopback_ms'] for s in samples),
    'limits':['SQL时间含驱动及本机传输；其余时间含Python、JSON、缓存发布及提交，不等于纯CPU',
        '未测真实浏览器HTTP网络；浏览器测量采用隔离立即响应API，不冒充端到端生产延迟']}
Path(os.environ['WORKDRAFT_BACKEND_OUTPUT']).write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:report[k] for k in ['fixture_bytes','mean_service_and_commit_ms','mean_sql_driver_and_loopback_ms']},ensure_ascii=False))
engine.dispose()
