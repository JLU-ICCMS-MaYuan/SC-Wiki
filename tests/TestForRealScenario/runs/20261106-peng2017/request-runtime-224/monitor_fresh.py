"""只读记录本轮新任务；不调用业务操作、不读取凭据或其他任务。"""
import json,time,datetime,sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[5]/'.env')
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
from backend.ingest.upload_tasks import get_state
root=Path(__file__).parent;task='d2ca41e5f16b4d65bf744f5d5325e855';previous=None
while True:
    state=get_state(task) or {};activity=state.get('model_activity') or {}
    row={'status':state.get('status'),'stage':state.get('stage'),'chunks':[state.get('completed_chunks'),state.get('total_chunks')],
         'activity':{key:activity.get(key) for key in ['status','phase','filename','pages','attempt']},'paper_id':state.get('paper_id')}
    if activity.get('error'):row['error']={key:activity['error'].get(key) for key in ['status_code','code','message','request_id']}
    signature=json.dumps(row,ensure_ascii=False,sort_keys=True)
    if signature!=previous:
        row['recorded_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (root/'fresh-progress.jsonl').open('a') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True);previous=signature
    if state.get('status') in {'ready','failed','paused','cancelled','submitted','needs_workflow','duplicate'}:break
    time.sleep(20)
