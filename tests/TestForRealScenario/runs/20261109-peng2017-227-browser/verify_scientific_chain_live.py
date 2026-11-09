"""原生产编排的隔离整理链；复用本轮已完成提取，重新执行未完成模型步骤。"""
from dotenv import load_dotenv
load_dotenv('.env')

from contextlib import ExitStack, nullcontext
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
from unittest.mock import patch

from sqlalchemy import event
from backend.database import engine
from backend.ingest import upload_jobs, upload_tasks
from backend.ingest.model_runtime import ModelRuntime, execution_context, atomic_json
from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config

ROOT = Path(__file__).resolve().parent
ACTIVE = json.loads((ROOT / 'active-task.json').read_text())
TASK = ACTIVE['task_id']
OUT = ROOT / 'inventory-chain-live'
DATA = OUT / 'data'
OUT.mkdir(exist_ok=True)
state = deepcopy(upload_tasks.get_state(TASK))
assert state and state['completed_chunks'] == 29 and not state.get('paper_id')
original_artifacts = upload_tasks.artifact_directory(TASK)
ARTIFACTS = DATA / 'review_artifacts' / TASK
shutil.copytree(original_artifacts, ARTIFACTS, dirs_exist_ok=True)
shutil.copytree(upload_tasks.data_path('parsed_markdown') / TASK,
                DATA / 'parsed_markdown' / TASK, dirs_exist_ok=True)
state.update(status='queued', execution_generation=1, processing_error=None,
             error_code=None, is_shadow=True, parent_task_id='isolated-parent',
             reparse_expected_draft_hash=None)
case = json.loads((ROOT / 'case-grobid-fix.json').read_text())
pdfs = {row['role']: Path(row['path']) for row in case['files']}
for row in case['files']:
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256']
for row in state['files']:
    # 隔离副本使用同哈希原PDF本地路径，不把真实对象存储路径当成本地缓存。
    row['stored_path'] = str(pdfs[row['role']])
    row['source_file_path'] = str(pdfs[row['role']])
state['file_path'] = str(pdfs['main'])
state['source_file_path'] = str(pdfs['main'])


def data_path(name):
    path = DATA / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def read(_):
    return deepcopy(state)


def write(_, **changes):
    state.update(changes)
    atomic_json(OUT / 'state.json', state)
    return deepcopy(state)


class ScientificChainFinished(BaseException):
    pass


class BusinessWriteBlocked(BaseException):
    pass


def readonly_sql(_connection, _cursor, statement, *_):
    if statement.lstrip().split(None, 1)[0].upper() not in {'SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN', 'SET'}:
        raise BusinessWriteBlocked('隔离验证阻止业务数据库写入')


def boundary(_, draft):
    # 此处位于结构归属和最终科学门之后、引用匹配/业务持久化之前。
    assert (draft.get('form_filling_report') or {}).get('status') == 'completed'
    assert 'ModelRequestError' not in json.dumps(draft.get('generation_issues') or [])
    # 正式JSON边界允许元组转数组、整数对象键转字符串；非有限数仍明确拒绝。
    canonical = json.loads(json.dumps(draft, ensure_ascii=False, allow_nan=False))
    atomic_json(OUT / 'draft.json', draft)
    assert json.loads((OUT / 'draft.json').read_text()) == canonical
    summary = {
        'scope': '正式生产编排至结构归属及最终来源/遗漏门；隔离JSON保存重读',
        'reused': '本轮原PDF/SI已核对文字/IR、29段候选及完整模型响应；未改字段不伪称重新提取',
        'not_covered': 'is_shadow跳过逐字段建议/科学复核；引用匹配、业务保存、谱、角色交接及五阶段仍须正式网页',
        'states': len(draft['material_states']),
        'structures': sum(bool(row.get('structure')) for row in draft['material_states']),
        'filling_status': (draft.get('form_filling_report') or {}).get('status'),
        'generation_issues': draft.get('generation_issues'),
        'paper_doi': draft['paper'].get('doi'),
        'code_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'model_memory_sha256': hashlib.sha256(Path('backend/ingest/model_memory.py').read_bytes()).hexdigest(),
        'status': 'scientific_chain_finished',
    }
    atomic_json(OUT / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    raise ScientificChainFinished


config = catalog_config('LLM2')
token = set_llm_config(config)
runtime = ModelRuntime(TASK, 1, ARTIFACTS / 'model-runtime' / state['execution_input_hash'],
                       lambda: deepcopy(state), lambda **changes: write(TASK, **changes),
                       lambda: nullcontext(), identity=state['execution_model'])
atomic_json(OUT / 'scope.json', {'task_id': TASK, 'provider': config.provider, 'model': config.model,
    'real_business_state_before': upload_tasks.get_state(TASK)['status'], 'database_writes': 'blocked',
    'source_files': case['files'], 'source_sha': ACTIVE['source_sha']})
event.listen(engine, 'before_cursor_execute', readonly_sql)
try:
    with ExitStack() as patches:
        for module in (upload_tasks, upload_jobs):
            patches.enter_context(patch.object(module, 'get_state', read))
            patches.enter_context(patch.object(module, 'update_state', write))
            patches.enter_context(patch.object(module, 'data_path', data_path))
            patches.enter_context(patch.object(module, 'artifact_directory', lambda _: ARTIFACTS))
        patches.enter_context(patch.object(upload_tasks, 'get_draft', lambda _: None))
        patches.enter_context(patch.object(upload_jobs, '_original_path', lambda _: pdfs['main']))
        patches.enter_context(patch.object(upload_jobs, '_source_path', lambda _state, item, _: pdfs[item['role']]))
        patches.enter_context(patch.object(upload_jobs, '_schedule_terminal_cleanup', lambda _: None))
        patches.enter_context(patch('backend.storage.paths.object_mode', lambda: False))
        patches.enter_context(patch('backend.services.citation_matching.complete_upload_matching', boundary))
        with execution_context(runtime):
            try:
                upload_jobs._process_conventional_upload_task(TASK)
            except ScientificChainFinished:
                pass
finally:
    event.remove(engine, 'before_cursor_execute', readonly_sql)
    reset_llm_config(token)
