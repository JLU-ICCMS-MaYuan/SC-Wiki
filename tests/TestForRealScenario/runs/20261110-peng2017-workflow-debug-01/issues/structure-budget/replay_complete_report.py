"""固定重放本轮新模型响应，用最新覆盖检查核验请求相等；不是新模型提取。"""
import hashlib, json, sys
from pathlib import Path
from backend.ingest.structure_reading import extract_structure_candidates
from backend.services.structure_candidates import read_atoms

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'live-complete-report'
case = json.loads((ROOT.parents[1] / 'case.json').read_text())
entry = next(row for row in case['files'] if row['role'] == 'supplementary')
path = Path(entry['path'])
assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
source = dict(file_id='311d9c17cfa04095bcd3cb613872f4ce', role=entry['role'],
              filename=path.name, sha256=entry['sha256'])
events = sorted(OUT.glob('call-*-completed.json'), key=lambda f: int(f.name.split('-')[1]))
captured = [json.loads(file.read_text()) for file in events]
index = 0
def normal(value):
    return json.loads(json.dumps(value, ensure_ascii=False))
def model(system, payload, **options):
    global index
    event = captured[index]
    assert json.loads(payload) == event['request'], f'request changed at {index}'
    assert normal(options.get('tool_history', [])) == event['tool_history'], f'history changed at {index}'
    index += 1
    return event['response']
output = extract_structure_candidates('', source=source, pdf_path=path, model=model)
assert index == len(captured)
assert normal(output) == json.loads((OUT / 'candidates.json').read_text())
for row in output:
    if row['status'] == 'valid':
        for value in row.get('representations', {}).values():
            if value.get('cif'):
                assert len(read_atoms('cif', value['cif']['text'])) > 0
result = {'replay': True, 'new_model_calls': 0, 'requests_equal': True,
    'saved_reread_equal': True, 'valid': sum(c['status'] == 'valid' for c in output),
    'blocked': sum(c['status'] == 'blocked' for c in output),
    'source_sha256': entry['sha256'], 'latest_guard_sha256': hashlib.sha256(
        Path('backend/ingest/structure_reading.py').read_bytes()).hexdigest()}
(ROOT / 'latest-guard-replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
