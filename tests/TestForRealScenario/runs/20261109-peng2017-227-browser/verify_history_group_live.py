"""真实失败字段组完整只读工具循环；不保存字段决定或修改业务草稿。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from copy import deepcopy
import json

from backend.ingest.upload_tasks import get_state, get_draft, artifact_directory
from backend.ingest.document_ir import DocumentIR
from backend.ingest.scientific_form_filling import form_sources
from backend.ingest.model_review import review_fields
from backend.ingest.property_evidence import upload_snapshot
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm import call_phase
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'history-group-live'
OUT.mkdir(exist_ok=True)
TASK = '02b23f7c5e524f8ba718f48d92a07f75'
original = get_state(TASK)
artifacts = artifact_directory(TASK)
failure = next(path for path in (artifacts / 'model-runtime').rglob('failure-*.json')
    if json.loads((path.parent / 'request.json').read_text()).get('phase') == 'field_evidence_and_suggestions'
    and (json.loads(path.read_text()).get('error') or {}).get('code') == 'ContextBudgetError')
request = json.loads((failure.parent / 'request.json').read_text())['request']
requested = json.loads(request['user_prompt'])['records']
draft = get_draft(TASK)
snapshot = upload_snapshot(TASK, int(original['user_id']), parsing_draft=draft)
by_key = {row['key']: row for row in snapshot['records']}
records = []
from backend.ingest.scientific_form_filling import filling_review_context
for row in requested:
    full = deepcopy(by_key[row['key']])
    assert full['current_value'] == row['current_value'], row['field']
    context = filling_review_context(draft.get('form_filling_report') or {}, full.get('record_key'))
    if context:
        full['organization_context'] = context
    records.append(full)
documents = {row['file_id']: DocumentIR.model_validate_json(
    (artifacts / 'document_ir' / (row['file_id'] + '.json')).read_text()) for row in original['files']}
chunks = snapshot['chunks']
case = json.loads((ROOT / 'case-grobid-fix.json').read_text())
manifest = deepcopy(original['files'])
for row in manifest:
    file = next(f for f in case['files'] if f['role'] == row['role'])
    row['stored_path'] = file['path']
    row['source_file_path'] = file['path']
config = catalog_config('LLM2')
token = set_llm_config(config)
state = {'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
runtime = ModelRuntime('c' * 32, 1, OUT / 'runtime', lambda: dict(state), write,
    lambda: nullcontext(), identity={'provider': config.provider, 'model': config.model})
events = []
def activity(event):
    events.append(event)
    atomic_json(OUT / 'activity.json', events)
try:
    with patch('backend.storage.paths.object_mode', lambda: False), execution_context(runtime), call_phase('field_evidence_and_suggestions'):
        result = review_fields(records, chunks, manifest=manifest, model_name=config.model,
            allow_condition_additions=False, on_activity=activity,
            on_response=lambda req, answer: atomic_json(OUT / 'last-model-result.json', {'request': req, 'answer': answer}))
    atomic_json(OUT / 'results.json', result)
    summary = {'provider': config.provider, 'model': config.model,
        'fields': len(result), 'statuses': {}, 'review_errors': [],
        'scope': '原失败字段组，原PDF/IR及正式review_fields完整工具循环；不写字段决定或业务草稿'}
    for value in result.values():
        status = value.get('status')
        summary['statuses'][status] = summary['statuses'].get(status, 0) + 1
        if value.get('review_error'): summary['review_errors'].append(value['review_error'])
    atomic_json(OUT / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False))
finally:
    reset_llm_config(token)
