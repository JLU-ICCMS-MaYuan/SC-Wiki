"""同原PDF受影响窗口重新提取；仅存储/运行器状态隔离，不替换科学校验。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import hashlib, json, shutil
from backend.ingest import upload_jobs as jobs
from backend.ingest.upload_tasks import artifact_directory, get_state
from backend.ingest.document_ir import DocumentIR
from backend.ingest.domain_extraction import structured_chunks
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json, digest
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
from backend.storage import paths

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'live'
OUT.mkdir(exist_ok=True)
TASK, FID, FAKE = 'd789acceee124022b3257f84780d1156', '311d9c17cfa04095bcd3cb613872f4ce', 'c8'*16
retired = 'chart-reading-8787c5ca2ceee313bf4d7845f8414a7d1f8f514f'
business = get_state(TASK)
case = json.loads((ROOT.parents[1] / 'case.json').read_text())
source = next(file for file in case['files'] if file['role'] == 'supplementary')
assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
art = OUT / 'artifacts'
(art / 'document_ir').mkdir(parents=True, exist_ok=True)
(art / 'chunks' / FID).mkdir(parents=True, exist_ok=True)
for name in ('material_state_inventory_request.json', 'material_state_inventory.json'):
    shutil.copy2(ROOT / name, art / name)
shutil.copy2(ROOT / (FID+'.json'), art / 'document_ir' / (FID+'.json'))
shutil.copy2(ROOT / 'affected-chunk-before.json', art / 'chunks' / FID / '00002.json')
ir = DocumentIR.model_validate_json((art / 'document_ir' / (FID+'.json')).read_text())
chunk = next(c for c in structured_chunks(ir) if c.chunk_index == 2)
state = {'task_id': FAKE, 'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
config = catalog_config('LLM2')
assert digest(config.base_url) == business['execution_model']['endpoint_hash']
token = set_llm_config(config)
scope = (business.get('workflow_assessment') or {}).get('tc_material_scope')
source_files = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
    'backend/ingest/extraction_sources.py', 'backend/ingest/image_catalog.py',
    'backend/ingest/scientific_form_filling.py', 'backend/ingest/upload_jobs.py')}
atomic_json(OUT / 'source.json', {'files':source_files, 'scope_policy':scope})
runtime = ModelRuntime(FAKE, 1, OUT / 'runtime', lambda:dict(state), write,
    lambda:nullcontext(), identity={'provider':config.provider, 'model':config.model})
jobs.artifact_directory = lambda _:art
real_get = jobs.get_state
jobs.get_state = lambda task:dict(state) if task == FAKE else real_get(task)
paths.object_mode = lambda:False
try:
    with execution_context(runtime):
        result = jobs._read_chunk(FAKE, chunk, FID, {'file_id':FID, 'kind':'pdf',
            'parser_profile':'complementary', 'role':'supplementary',
            'original_filename':Path(source['path']).name, 'stored_path':source['path'],
            'sha256':source['sha256'], 'tc_material_scope':scope})
    saved = json.loads((art / 'chunks' / FID / '00002.json').read_text())
    assert saved == json.loads(json.dumps(result))
    assert retired not in json.dumps(result.get('_source_resolution') or {})
    ce = [s for s in result['material_states'] if s.get('material') == 'CeH10']
    assert ce
    assert all(s.get('reported_space_group_symbol') in (None, '', 'Fm-3m') for s in ce)
    evidence_ids = {e.get('block_id') for s in ce for m in s.get('property_modules', [])
        for r in m.get('records', []) for e in r.get('evidences', [])}
    assert retired not in evidence_ids
    current = {b.block_id for b in ir.blocks if b.metadata.get('selected_for_reading') is not False}
    dos = [r for s in ce for m in s.get('property_modules', []) for r in m.get('records', [])
           if r.get('property_code') == 'dos_fermi']
    assert dos and all(any(e.get('block_id') in current for e in r.get('evidences', [])) for r in dos)
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha for name,sha in source_files.items())
    atomic_json(OUT / 'result.json', {'provider':config.provider, 'model':config.model,
        'source_sha256':source['sha256'], 'scope_policy_included':scope is not None,
        'ceh10':ce, 'retired_source_absent':True, 'current_source_retained':True,
        'saved_reread_equal':True, 'source_resolution':result.get('_source_resolution'),
        'scope':'原SI受影响窗口真实新提取、正式normalize/来源/类型校验及隔离保存重读；非完整业务或角色权限验证'})
    print(json.dumps({'ceh10_groups':[s.get('reported_space_group_symbol') for s in ce],
        'dos_values':[r.get('value_number') for r in dos], 'retired_source_absent':True},ensure_ascii=False),flush=True)
finally:
    reset_llm_config(token)
