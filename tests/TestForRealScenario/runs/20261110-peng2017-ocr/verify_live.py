"""原PDF+保存的互补原块，经正式_read_chunk重提受影响窗口；隔离禁止业务写入。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from copy import deepcopy
from contextlib import nullcontext,ExitStack
from unittest.mock import patch
import json,hashlib,shutil
from types import SimpleNamespace
from backend.ingest import upload_jobs as jobs
from backend.ingest.upload_tasks import artifact_directory,get_state
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.ingest.document_ir import DocumentIR
from backend.ingest.document_claims import claims_from_candidates
from backend.ingest.coverage_audit import audit_coverage
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'live';OUT.mkdir(exist_ok=True)
TASK='02b23f7c5e524f8ba718f48d92a07f75';a=artifact_directory(TASK);state=get_state(TASK)
fileid='a6013d5bea8d473b936d8cb8abe143c0'
case=json.loads((ROOT.parent/'20261109-peng2017-227-browser/case-grobid-fix.json').read_text())
file=next(f for f in case['files'] if f['role']=='main');pdf=Path(file['path'])
assert hashlib.sha256(pdf.read_bytes()).hexdigest()==file['sha256']
realchunk=a/f'chunks/{fileid}/00001.json';localchunk=OUT/'00001.json';shutil.copyfile(realchunk,localchunk)
irdir=OUT/'artifacts/document_ir';irdir.mkdir(parents=True,exist_ok=True)
shutil.copyfile(a/f'document_ir/{fileid}.json',irdir/f'{fileid}.json')
input_path=max((realchunk.parent/'extraction_attempts/00001').glob('*/input.json'),key=lambda p:p.stat().st_mtime)
content=json.loads(input_path.read_text())['prompt'].split('\n\n',1)[1]
chunk=SimpleNamespace(chunk_index=1,content=content,section_name='Document IR',source_page=3,source_page_end=4)
source={**next(f for f in state['files'] if f['file_id']==fileid),'stored_path':str(pdf),
        'parser_profile':'complementary','tc_material_scope':(state.get('workflow_assessment') or {}).get('tc_material_scope')}
config=catalog_config('LLM2');token=set_llm_config(config)
local={'status':'reading','execution_generation':1}
def update(**changes):local.update(changes);atomic_json(OUT/'state.json',local)
runtime=ModelRuntime('f'*32,1,OUT/'runtime',lambda:dict(local),update,lambda:nullcontext(),
 identity={'provider':config.provider,'model':config.model})
try:
 with ExitStack() as stack:
  stack.enter_context(patch.object(jobs,'_chunk_result_path',lambda *_:localchunk))
  stack.enter_context(patch.object(jobs,'artifact_directory',lambda *_:OUT/'artifacts'))
  stack.enter_context(patch.object(jobs,'_ensure_not_cancelled',lambda *_:None))
  stack.enter_context(patch('backend.storage.paths.object_mode',lambda:False))
  stack.enter_context(execution_context(runtime))
  result=jobs._read_chunk(TASK,chunk,fileid,source)
  again=jobs._read_chunk(TASK,chunk,fileid,source)
  assert again==result
 ir=DocumentIR.model_validate_json((irdir/f'{fileid}.json').read_text())
 claims=claims_from_candidates(result,{fileid:ir})
 summary={'model':config.model,'provider':config.provider,'source_sha256':file['sha256'],
   'source_resolution':result.get('_source_resolution'),'same_input_reused':again==result,
   'claims':len(claims),'invalid_claims':[c.model_dump(mode='json') for c in claims if c.status!='validated'],
   'unreadable':[e for e in result.get('coverage_exclusions',[]) if e.get('category')=='unreadable'],
   'states':result['material_states'],'scope':'原PDF4页真实新图像+未修改OCR/Marker原块，正式提取/后处理/claim及保存重读；仅隔离结果，无业务写入'}
 atomic_json(OUT/'summary.json',summary)
 print(json.dumps({'claims':len(claims),'invalid':len(summary['invalid_claims']),'unreadable':len(summary['unreadable']),
  'states':len(result['material_states']),'source_resolution':result.get('_source_resolution')},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)
