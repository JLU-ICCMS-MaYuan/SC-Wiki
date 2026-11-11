"""从同一原PDF验证工具协议和结构局部修订；隔离运行，不回填业务草稿。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import base64
import hashlib
import json
import sys
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json, digest
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
from backend.ingest.upload_tasks import get_state
from backend.rag.llm import call_phase, complete_json

ROOT = Path(__file__).resolve().parent
MODE = sys.argv[1]
OUT = ROOT / ('live-' + MODE)
OUT.mkdir(exist_ok='--resume' in sys.argv)
TASK = json.loads((ROOT/'active-task.json').read_text())['task_id']
business = get_state(TASK)
case = json.loads((ROOT/'case.json').read_text())
file = next(x for x in case['files'] if x['role']=='supplementary')
path = Path(file['path'])
assert hashlib.sha256(path.read_bytes()).hexdigest()==file['sha256']
fid = next(x['file_id'] for x in business['files'] if x['role']=='supplementary')
config = catalog_config('LLM1')
assert config.model=='deepseek-flash' and digest(config.base_url)==business['execution_model']['endpoint_hash']
token = set_llm_config(config)
state = {'status':'reading','execution_generation':1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT/'state.json',state)
runtime = ModelRuntime('fb47'*8,1,OUT/'runtime',lambda:dict(state),write,lambda:nullcontext(),
    identity={'provider':config.provider,'model':config.model})
events = []
def event(value):
    events.append(value)
    atomic_json(OUT/f'event-{len(events):03d}.json',value)
source = dict(file_id=fid,role='supplementary',filename=path.name,sha256=file['sha256'])
files = ['backend/ingest/structure_reading.py','backend/ingest/chart_reading.py']
metadata = dict(model=config.model,provider=config.provider,source_sha256=file['sha256'],
    source_files={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files})
atomic_json(OUT/'source.json',metadata)
try:
    with execution_context(runtime),call_phase(MODE,filename=path.name):
        if MODE=='chart':
            from backend.ingest.document_ir import DocumentIR
            from backend.ingest.chart_reading import READING_PROMPT,calibrate_panel,append_readings
            from backend.ingest.image_feedback import read_chart
            from backend.ingest.pdf_regions import region_locator,render_region_image
            from PIL import Image
            import io
            art=Path('.data/review_artifacts')/TASK
            saved=next((art/'chart_reading'/fid).glob('reading-*.json'))
            request=json.loads(saved.read_text())['request']
            assert request['pdf_page']==13
            ir=DocumentIR.model_validate_json((art/'document_ir'/(fid+'.json')).read_text())
            loc=region_locator(path,fid,file['sha256'],13,request['crop_bbox'],parent_region_id=request['complete_figure']['region_id'])
            full=render_region_image(path,request['complete_figure'])['png']
            crop=render_region_image(path,loc)['png']
            answer,box,feedback=read_chart(complete_json,READING_PROMPT,request,
                ['data:image/png;base64,'+base64.b64encode(x).decode() for x in (full,crop)],
                ir,path,source,request['crop_bbox'],cancelled=lambda:False,on_event=event)
            loc=region_locator(path,fid,file['sha256'],13,box,parent_region_id=request['complete_figure']['region_id'])
            png=render_region_image(path,loc)['png']
            readings,unresolved=[],[]
            for panel in answer['panels']:
                found,missing=calibrate_panel(panel,Image.open(io.BytesIO(png)),{**source,'page':13},box)
                readings.extend(found);unresolved.extend(missing)
            append_readings(ir,readings)
            # 正式IR验证会补入新派生块的已知页面几何；科学值和来源不改写。
            before=ir.model_dump(mode='json')
            ir=DocumentIR.model_validate(before)
            atomic_json(OUT/'pre-validation-ir.json',before)
            atomic_json(OUT/'document-ir.json',ir.model_dump(mode='json'))
            reread=DocumentIR.model_validate_json((OUT/'document-ir.json').read_text())
            assert reread.model_dump(mode='json')==ir.model_dump(mode='json')
            result=dict(**metadata,readings=len(readings),unresolved=unresolved,answer=answer,feedback=feedback,
                saved_reread_equal=True,scope='原SI第13页新AI读图、正式标定与IR保存重读，非整篇或业务验收')
        elif MODE=='structure':
            from backend.ingest.structure_reading import extract_structure_candidates
            result_candidates=extract_structure_candidates('',source=source,pdf_path=path,on_event=event,
                material_scope=(business.get('workflow_assessment') or {}).get('tc_material_scope'))
            atomic_json(OUT/'candidates.json',result_candidates)
            assert json.loads((OUT/'candidates.json').read_text())==json.loads(json.dumps(result_candidates))
            repairs=[e for e in events if e['status']=='structure-repair']
            result=dict(**metadata,valid=sum(c['status']=='valid' for c in result_candidates),
                blocked=sum(c['status']=='blocked' for c in result_candidates),repairs=repairs,
                saved_reread_equal=True,scope='原SI新结构提取、正式校验及局部修订，非整篇或业务验收')
        else:
            raise ValueError('未知隔离模式')
    assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==sha for f,sha in metadata['source_files'].items())
    atomic_json(OUT/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'answer','source_files'}},ensure_ascii=False),flush=True)
finally:
    reset_llm_config(token)
