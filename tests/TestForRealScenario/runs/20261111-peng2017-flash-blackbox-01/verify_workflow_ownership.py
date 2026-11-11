"""复用已核实的原文窗口响应，只以真实模型重做丢失来源角色的汇总。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import hashlib,json
from backend.ingest.parsing_workflows import assess
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json,digest
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.rag.llm import complete_json,call_phase
from backend.ingest.upload_tasks import get_state

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'live-workflow-ownership'
OUT.mkdir(exist_ok=False)
TASK=json.loads((ROOT/'active-task.json').read_text())['task_id']
base=Path('.data/review_artifacts')/TASK/'model-runtime'
windows=[]
old_final=None
for f in base.glob('*/calls/*/request.json'):
    q=json.loads(f.read_text())['request']
    if not q['system_prompt'].startswith('判断当前论文应进入'):continue
    body=json.loads(q['user_prompt']);res=f.parent/'result.json'
    if not res.exists():continue
    answer=json.loads(res.read_text())['response']
    if 'sources' in body:windows.append((body['sources'],answer))
    else:old_final=answer
windows.sort(key=lambda w:int(w[0][0]['source_id'].rsplit('-',1)[1]))
assert len(windows)==2 and old_final
sources=[{k:v for k,v in row.items() if k!='source_id'} for rows,_ in windows for row in rows]
for f in json.loads((ROOT/'case.json').read_text())['files']:
    assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']
config=catalog_config('LLM1');business=get_state(TASK)
assert digest(config.base_url)==business['execution_model']['endpoint_hash']
token=set_llm_config(config)
state={'status':'reading','execution_generation':1}
def write(**changes):state.update(changes);atomic_json(OUT/'state.json',state)
runtime=ModelRuntime('fd82'*8,1,OUT/'runtime',lambda:dict(state),write,lambda:nullcontext(),identity={'provider':config.provider,'model':config.model})
calls=[]
def model(prompt,payload,**options):
    body=json.loads(payload)
    if 'sources' in body:
        expected,answer=windows[len(calls)]
        assert body['sources']==expected
        calls.append('reused_original_window')
        return answer
    assert len(calls)==2 and len(body['source_index'])==len(sources)
    calls.append('new_model_aggregation')
    atomic_json(OUT/'aggregate-input.json',body)
    return complete_json(prompt,payload,**options)
try:
    with execution_context(runtime),call_phase('workflow_scope'):
        report=assess(sources,complete=model,model=config.model)
    atomic_json(OUT/'old-final.json',old_final)
    atomic_json(OUT/'report.json',report)
    assert report['status']=='matched'
    assert json.loads((OUT/'report.json').read_text())==report
    result={'model':config.model,'provider':config.provider,'calls':calls,
        'status':report['status'],'contribution_source_ids':report['contribution_source_ids'],
        'source_files':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in (
            'backend/ingest/parsing_workflows.py','backend/ingest/theoretical_subtype.py','backend/ingest/source_ownership.py')},
        'scope':'相同原文窗口及失败汇总，真实新模型汇总及原校验、绑定与JSON重读；不写业务任务'}
    atomic_json(OUT/'result.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
finally:reset_llm_config(token)
