"""原SI结构重新提取与正式几何校验，独立运行器保存重读，不修改业务草稿。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import hashlib
import json
import sys
from backend.ingest.structure_reading import extract_structure_candidates
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json, digest
from backend.ingest.upload_tasks import get_state
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
from backend.rag.llm import call_phase
from backend.services.structure_candidates import read_atoms

ROOT = Path(__file__).resolve().parent
OUT = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'live')
OUT.mkdir(exist_ok=True)
case = json.loads((ROOT.parents[1] / 'case.json').read_text())
entry = next(row for row in case['files'] if row['role'] == 'supplementary')
path = Path(entry['path'])
assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
source = dict(file_id='311d9c17cfa04095bcd3cb613872f4ce', role=entry['role'],
              filename=path.name, sha256=entry['sha256'])
current = get_state('d789acceee124022b3257f84780d1156')
config = catalog_config('LLM2')
assert digest(config.base_url) == current['execution_model']['endpoint_hash']
token = set_llm_config(config)
state = {'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
runtime = ModelRuntime('ef25' * 8, 1, OUT / 'runtime', lambda: dict(state), write,
    lambda: nullcontext(), identity={'provider': config.provider, 'model': config.model})
def event(value):
    atomic_json(OUT / f"call-{value['iteration']}-{value['status']}.json", value)
try:
    with execution_context(runtime), call_phase('structure_reading', filename=path.name):
        candidates = extract_structure_candidates('', source=source, pdf_path=path, on_event=event)
    atomic_json(OUT / 'candidates.json', candidates)
    reread = json.loads((OUT / 'candidates.json').read_text())
    assert reread == json.loads(json.dumps(candidates, ensure_ascii=False))
    for candidate in reread:
        if candidate['status'] == 'valid':
            for representation in candidate.get('representations', {}).values():
                if representation.get('cif'):
                    assert len(read_atoms('cif', representation['cif']['text'])) > 0
    reports = []
    for file in OUT.glob('call-*-completed.json'):
        response = json.loads(file.read_text())['response']
        action = response.get('action') or {}
        if action.get('name') == 'report_structures':
            reports.append({'iteration': int(file.name.split('-')[1]),
                'structures': len(action['arguments']['structures'])})
    atomic_json(OUT / 'result.json', {'provider': config.provider, 'model': config.model,
        'source_sha256': entry['sha256'], 'valid': sum(c['status'] == 'valid' for c in reread),
        'blocked': sum(c['status'] == 'blocked' for c in reread), 'saved_reread_equal': True,
        'model_reports': sorted(reports, key=lambda row: row['iteration']),
        'source_files': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
            'backend/ingest/structure_reading.py', 'backend/ingest/model_memory.py', 'backend/ingest/review_tool_contract.py')},
        'scope': '原SI新AI结构提取、正式几何展开校验及JSON/CIF重读；非整篇科学或业务通过'})
    print((OUT / 'result.json').read_text(), flush=True)
finally:
    reset_llm_config(token)
