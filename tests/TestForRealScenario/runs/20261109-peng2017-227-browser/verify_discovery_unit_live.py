"""原SI第7—12页重新模型盘点，保留整图/面板及排除原因，不写真实任务。"""
from dotenv import load_dotenv
load_dotenv('.env')
from contextlib import nullcontext
from pathlib import Path
import base64
import hashlib
import json
import pymupdf

from backend.ingest.upload_tasks import artifact_directory
from backend.ingest.chart_reading import DISCOVERY_PROMPT, discovery_schema, page_inventory
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm import complete_json, call_phase
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'discovery-unit-live'
OUT.mkdir(exist_ok=True)
failure = json.loads((ROOT / 'discovery-shared-caption-before.json').read_text())
old_request = json.loads(Path(failure['source_request']).read_text())['request']
payload = json.loads(old_request['user_prompt'])
case = json.loads((ROOT / 'case-grobid-fix.json').read_text())
file = next(row for row in case['files'] if row['role'] == 'supplementary')
assert hashlib.sha256(Path(file['path']).read_bytes()).hexdigest() == file['sha256']
pages = payload['image_pages']
with pymupdf.open(file['path']) as document:
    images = ['data:image/png;base64,' + base64.b64encode(
        document[page - 1].get_pixmap(dpi=75, alpha=False).tobytes('png')).decode() for page in pages]
    geometries = {page: (document[page - 1].rect.width, document[page - 1].rect.height) for page in pages}
assert images == old_request['images']
config = catalog_config('LLM2')
token = set_llm_config(config)
state = {'status': 'reading', 'execution_generation': 1}
def write(**changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
runtime = ModelRuntime('d' * 32, 1, OUT / 'runtime', lambda: dict(state), write,
    lambda: nullcontext(), identity={'provider': config.provider, 'model': config.model})
try:
    with execution_context(runtime), call_phase('chart_discovery'):
        answer = complete_json(DISCOVERY_PROMPT, json.dumps(payload, ensure_ascii=False),
                               images=images, response_schema=discovery_schema())
    atomic_json(OUT / 'response.json', answer)
    targets, excluded = page_inventory(answer, geometries)
    result = {'provider': config.provider, 'model': config.model, 'pages': pages,
        'source_sha256': file['sha256'], 'original_images_byte_equal': True,
        'targets': targets, 'excluded': excluded, 'status': 'inventory_valid',
        'scope': '原SI图片重新渲染/哈希一致；模型新盘点及正式区域校验；未写业务任务或科学字段'}
    atomic_json(OUT / 'summary.json', result)
    print(json.dumps({'status': result['status'], 'pages': pages,
                     'targets': len(targets), 'excluded': len(excluded)}, ensure_ascii=False))
finally:
    reset_llm_config(token)
