"""真实失败字段请求重放；完整工具历史/图片保留，隔离检查点，不写业务状态。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import json

from backend.ingest.upload_tasks import artifact_directory
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm import complete_json, call_phase
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'history-request-live'
OUT.mkdir(exist_ok=True)
source = artifact_directory('02b23f7c5e524f8ba718f48d92a07f75') / 'model-runtime'
failure = next(path for path in source.rglob('failure-*.json')
    if json.loads((path.parent / 'request.json').read_text()).get('phase') == 'field_evidence_and_suggestions'
    and (json.loads(path.read_text()).get('error') or {}).get('code') == 'ContextBudgetError')
request = json.loads((failure.parent / 'request.json').read_text())['request']
config = catalog_config('LLM2')
token = set_llm_config(config)
state = {'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
runtime = ModelRuntime('b' * 32, 1, OUT / 'runtime', lambda: dict(state), write,
    lambda: nullcontext(), identity={'provider': config.provider, 'model': config.model})
atomic_json(OUT / 'scope.json', {'source_request': str(failure.parent / 'request.json'),
    'provider': config.provider, 'model': config.model,
    'scope': '完整原字段请求及独立科学工具历史新模型请求；不写字段结果或业务状态'})
try:
    with execution_context(runtime), call_phase('field_evidence_and_suggestions'):
        result = complete_json(request['system_prompt'], request['user_prompt'],
            **{key: request[key] for key in ('images', 'response_schema', 'tool_definitions', 'tool_history')
               if request.get(key)})
    atomic_json(OUT / 'result.json', result)
    print(json.dumps({'status': 'completed', 'keys': list(result),
        'result_count': len(result.get('results') or []), 'tool_calls': len(result.get('_tool_calls') or [])},
        ensure_ascii=False))
finally:
    reset_llm_config(token)
