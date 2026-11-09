"""从原PDF重新盘点及精读；旧失败IR仅在隔离副本恢复，禁止写业务任务。"""
from dotenv import load_dotenv
load_dotenv('.env')
from contextlib import nullcontext
from pathlib import Path
import json, shutil, hashlib
from backend.ingest.chart_cache import load_document_ir
from backend.ingest.chart_reading import enrich_document
from backend.ingest.document_ir import DocumentIR
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm import complete_json
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'chart-cache-recovery'
source = next(f for f in json.loads((ROOT / 'case-grobid-fix.json').read_text())['files'] if f['role'] == 'main')
assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
path = OUT / 'isolated-main-ir.json'
shutil.copyfile(OUT / 'failed-main-ir.json', path)
ir = load_document_ir(path)
config = catalog_config('LLM2'); token = set_llm_config(config)
state = {'status':'reading', 'execution_generation':1}
def write(**changes):
    state.update(changes); atomic_json(OUT / 'live-state.json', state)
runtime = ModelRuntime('e'*32,1,OUT/'runtime',lambda:dict(state),write,lambda:nullcontext(),
    identity={'provider':config.provider,'model':config.model})
def event(value):
    key = hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    atomic_json(OUT / ('live-'+value['stage']+'-'+key+'.json'),value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('request','response')},ensure_ascii=False),flush=True)
try:
    with execution_context(runtime):
        report = enrich_document(ir, source['path'], {'file_id':'a6013d5bea8d473b936d8cb8abe143c0',
            'sha256':source['sha256'],'filename':Path(source['path']).name,'role':'main'},complete_json,on_event=event)
    atomic_json(OUT/'live-ir.json',ir.model_dump(mode='json'))
    reread = DocumentIR.model_validate_json((OUT/'live-ir.json').read_text())
    values = [b.metadata['chart_reading'] for b in reread.blocks if 'chart_reading' in b.metadata
              and b.metadata.get('selected_for_reading') is not False]
    summary = {'provider':config.provider,'model':config.model,'report':report,'readings':values,
               'scope':'原PDF全页新盘点、独立区域新模型精读、正式标定及IR保存重读；未写业务草稿/数据库'}
    atomic_json(OUT/'live-summary.json',summary)
    print(json.dumps({'status':'completed','readings':len(values),'targets':len(report['targets'])},ensure_ascii=False),flush=True)
finally: reset_llm_config(token)
