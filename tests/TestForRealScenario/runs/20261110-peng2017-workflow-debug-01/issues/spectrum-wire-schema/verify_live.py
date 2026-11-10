"""同原PDF的真实谱工具请求；隔离标定、后处理、保存及重读。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import hashlib, io, json, sys
import numpy as np
from PIL import Image
from backend.ingest.model_runtime import ModelRuntime, atomic_json, digest, execution_context
from backend.ingest.upload_tasks import get_state, artifact_directory
from backend.rag.llm import call_phase, complete_json
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
from backend.spectra.discovery import pdf_figures, calibrate
from backend.spectra.engine import extract_panel
from backend.spectra.context import references_for

ROOT = Path(__file__).resolve().parent
OUT = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'live')
OUT.mkdir(exist_ok=True)
TASK = 'd789acceee124022b3257f84780d1156'
case = json.loads((ROOT.parents[1] / 'case.json').read_text())
business = get_state(TASK)
art = artifact_directory(TASK)
states = json.loads((art / 'material-stage.json').read_text())['draft']['material_states']
config = catalog_config('LLM2')
assert digest(config.base_url) == business['execution_model']['endpoint_hash']
token = set_llm_config(config)
state = {'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT/'state.json', state)
runtime = ModelRuntime('ce'*16, 1, OUT/'runtime', lambda:dict(state), write,
    lambda:nullcontext(), identity={'provider':config.provider,'model':config.model})
results = []
try:
    with execution_context(runtime), call_phase('automatic_spectra'):
        for role, page in [('main', 1), ('supplementary', 14)]:
            source = next(s for s in case['files'] if s['role']==role)
            path = Path(source['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256']
            file = next(f for f in business['files'] if f['role']==role)
            ir = json.loads((art/'document_ir'/f"{file['file_id']}.json").read_text())
            figure = next(f for f in pdf_figures(path, ir=ir) if f['pdf_page']==page)
            panels, issues = calibrate(figure, states, complete=complete_json)
            if role == 'main':
                assert not panels, '非目标页不得伪造谱面板'
            else:
                assert panels, '原Fig.S15目标谱未识别'
            rgb = np.asarray(Image.open(io.BytesIO(figure['image'])).convert('RGB'))
            extracted = [extract_panel(rgb,panel,references=references_for(next(
                (s for s in states if s.get('state_key')==panel.get('state_key')),None))) for panel in panels]
            item = {'role':role,'page':page,'source_sha256':source['sha256'],
                    'region_locator':figure['region_locator'],'panels':panels,'issues':issues,'extracted':extracted}
            output = OUT/f'{role}-{page}.json'
            atomic_json(output,item)
            assert json.loads(output.read_text()) == json.loads(json.dumps(item))
            results.append({'role':role,'page':page,'panels':len(panels),'failures':
                [row for result in extracted for row in result.get('failures',[])], 'saved_reread':True})
            print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    atomic_json(OUT/'result.json',{'model':config.model,'provider':config.provider,'results':results,
        'scope':'真原页模型谱工具、标定和正式谱engine及隔离保存重读；不写业务任务，非整篇谱或业务验收'})
finally:
    reset_llm_config(token)
