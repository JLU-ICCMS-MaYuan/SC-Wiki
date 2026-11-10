"""复用未改的逐页盘点，原PDF图表用新协议真实重读；仅隔离IR，不写业务稿。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import json,shutil,hashlib
from backend.ingest.upload_tasks import artifact_directory
from backend.ingest.chart_reading import enrich_document,discovery_schema
from backend.ingest.document_ir import DocumentIR
from backend.rag.structured_output import validate_output
from backend.rag.llm import complete_json
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'live';OUT.mkdir(exist_ok=True)
TASK='d789acceee124022b3257f84780d1156';FID='418df5b86f64460d95c52e754c2f7bfb';a=artifact_directory(TASK)
case=json.loads((ROOT.parents[1]/'case.json').read_text());source=next(f for f in case['files'] if f['role']=='main')
assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()==source['sha256']
ir=DocumentIR.model_validate_json((a/f'document_ir/{FID}.json').read_text())
discovery=next(json.loads(p.read_text()) for p in (a/'chart_reading'/FID).glob('*.json')
 if json.loads(p.read_text()).get('stage')=='discovery' and json.loads(p.read_text()).get('status')=='completed')
validate_output(discovery['response'],discovery_schema())
config=catalog_config('LLM2');token=set_llm_config(config);state={'status':'reading','execution_generation':1}
def write(**changes):state.update(changes);atomic_json(OUT/'state.json',state)
runtime=ModelRuntime('ab'*16,1,OUT/'runtime',lambda:dict(state),write,lambda:nullcontext(),identity={'provider':config.provider,'model':config.model})
def model(prompt,content,**options):
 if 'image_pages' in json.loads(content):return discovery['response']
 return complete_json(prompt,content,**options)
def event(value):
 key=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
 atomic_json(OUT/(value['stage']+'-'+key+'.json'),value)
 print({k:v for k,v in value.items() if k not in ('request','response')},flush=True)
try:
 with execution_context(runtime):report=enrich_document(ir,source['path'],{'file_id':FID,'sha256':source['sha256'],
  'filename':Path(source['path']).name,'role':'main'},model,on_event=event)
 atomic_json(OUT/'ir.json',ir.model_dump(mode='json'))
 reread=DocumentIR.model_validate_json((OUT/'ir.json').read_text())
 values=[b.metadata['chart_reading'] for b in reread.blocks if b.metadata.get('chart_reading')
  and b.metadata.get('selected_for_reading') is not False]
 summary={'model':config.model,'provider':config.provider,'report':report,'values':values,
  'discovery_reused':True,'source_sha256':source['sha256'],'scope':'原PDF原图新模型读数/正式标定及IR保存重读，旧盘点未变复用；无业务写入，非整篇或五阶段验收'}
 atomic_json(OUT/'summary.json',summary)
 print(json.dumps({'readings':len(values),'unresolved':len(report['unresolved']),'context_notes':len(report['context_notes'])},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)
