"""重放本轮原始失败总结请求；真实模型、隔离检查点，不写业务状态。"""
from contextlib import nullcontext
from pathlib import Path
import hashlib
import json
import subprocess

from dotenv import load_dotenv
load_dotenv('.env')

from backend.ingest.context_encoding import decode_context
from backend.ingest.model_memory import prepare_fixed_request, _fixed_token_estimate
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm import complete_json, call_phase
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config

ROOT = Path(__file__).resolve().parent / 'summary-live'
ROOT.mkdir(exist_ok=True)
source_root = Path('.data/review_artifacts/90427eb91a05495fb671a705b5ece82f/model-runtime')
source = next(path for path in source_root.rglob('request.json')
              if json.loads(path.read_text()).get('phase') == 'paper_summary')
request = json.loads(source.read_text())['request']
prepared = prepare_fixed_request(request)
assert decode_context(json.loads(prepared['user_prompt'])) == json.loads(request['user_prompt'])
config = catalog_config('LLM2')
token = set_llm_config(config)
state = {'status': 'summarizing', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(ROOT / 'state.json', state)
runtime = ModelRuntime('f' * 32, 1, ROOT / 'runtime', lambda: dict(state), write,
                       lambda: nullcontext(), identity={'provider': config.provider, 'model': config.model})
atomic_json(ROOT / 'source-snapshot.json', {
    'source_request': str(source), 'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'model': config.model, 'provider': config.provider,
    'original_tokens': _fixed_token_estimate(request), 'prepared_tokens': _fixed_token_estimate(prepared),
    'whole_tree_equal': True, 'reused': '29段已完成候选及未改动原文；总结重新真实请求',
    'code': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        Path('backend/ingest/model_memory.py'), Path('backend/ingest/context_encoding.py'))},
})
try:
    with execution_context(runtime), call_phase('paper_summary'):
        result = complete_json(request['system_prompt'], request['user_prompt'],
                               **{key: request[key] for key in ('response_schema', 'images') if request.get(key)})
    atomic_json(ROOT / 'result.json', result)
    print(json.dumps({'status': 'completed', 'keys': list(result), 'paper': result.get('paper')}, ensure_ascii=False))
finally:
    reset_llm_config(token)
