"""显式指定任务，先生成可审计计划，再用 --apply-plan 应用相同版本的条件补空。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from backend.ingest.calculation_backfill import classify_approximations, projection, condition_proposal, assert_conditions_only, assert_current, revalidate_prior_candidates
from backend.ingest.scientific_context import build_context, fingerprint, generate_context_associations, READ_PROMPT, CONTEXT_VERSION
from backend.ingest.property_evidence import source_chunks
from backend.ingest.upload_tasks import get_draft, get_state, data_path, save_draft, upload_task_lock, available_published_path
from backend.rag.llm import complete_json
from backend.rag.llm_context import get_llm_config, llm_display_metadata
from backend.storage.paths import resolve_file


def sources(task, state):
    chunks = []
    for item in state.get('files') or []:
        if item.get('role') not in {'main', 'supplementary'}:
            continue
        path = resolve_file(item['stored_path'], size=int(item['size']), sha256=item['sha256'], namespace=task)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('原文件哈希变化')
        markdown = available_published_path(task, data_path('parsed_markdown') / task / f"{item['file_id']}.md")
        if not markdown.is_file():
            raise ValueError('缺少完整已解析原文')
        chunks.extend({**c, 'file_role': item['role'], 'source_sha256': item['sha256']}
                      for c in source_chunks(markdown.read_text(), item['file_id']))
    if not chunks:
        raise ValueError('没有有效主文或补充来源')
    return chunks


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def record_checks(task, draft, owner, applied):
    from backend.database import SessionLocal
    from backend.ingest import property_evidence as evidence, scientific_evidence as science
    from backend.ingest.scientific_context import targets
    snapshot = evidence.upload_snapshot(task, owner, parsing_draft=draft)
    affected = {item['target'] for item in applied}
    lookup = targets(draft)
    results = {}
    for row in snapshot['records']:
        identity = '/'.join([row.get('state_key') or '', row.get('module_key') or '', row.get('record_key') or ''])
        if identity not in affected:
            continue
        record = lookup[identity][2]
        quotes = { (e.get('file_id'), e.get('quote')): e for a in record['payload'].get('source_associations', [])
                   for e in [*a.get('fact_evidences', []), *a.get('scope_evidences', [])] }
        result = evidence.checked_result(row, {'status': 'uncertain',
            'reason': '计算条件依据完整原文推断适用范围，仍需人工核对；本次未重新核对 Tc 等原有科学值。',
            'evidences': list(quotes.values())}, snapshot['chunks'])
        result.update(adopted_basis='paper_inference', auto_filled=True,
                      auto_filled_content_hash=row['content_hash'], auto_filled_source_hash=row['source_hash'])
        results[row['key']] = result
    with SessionLocal.begin() as session:
        science.save_results(session, snapshot, results, owner)
    return len(results)


def prepare(task, resume=None, revalidate=None):
    with upload_task_lock(task):
        state, draft = deepcopy(get_state(task)), deepcopy(get_draft(task))
        if not state or not draft:
            raise ValueError('任务或草稿不存在')
        version = int(state.get('revision') or 0)
        assert_current(fingerprint(draft), version, draft, state)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        directory = data_path('review_artifacts') / task / 'calculation_backfill' / stamp
        directory.mkdir(parents=True, exist_ok=False)
        write(directory / 'backup.json', {'state': state, 'draft': draft})
    context = build_context(sources(task, state))
    config = get_llm_config()
    identity = {'provider': config.provider, 'model': config.model, 'endpoint': config.base_url}
    if resume:
        old = json.loads((resume / 'backup.json').read_text())
        ledger = json.loads((resume / 'ledger.json').read_text())
        if (fingerprint(old['draft']) != fingerprint(draft) or old['state']['files'] != state['files']
                or ledger['source_fingerprint'] != context['source_fingerprint']):
            raise ValueError('不能复用不同草稿或来源版本的真实模型响应')
    calls, exclusions = [], []
    def condition_model(system, body, **kwargs):
        reused = None
        if resume and system == READ_PROMPT:
            window_id = json.loads(body)['window_id']
            window = next(w for w in context['windows'] if w['window_id'] == window_id)
            signature = fingerprint([CONTEXT_VERSION, context['source_fingerprint'], window, identity, READ_PROMPT])
            found = sorted((resume / 'cache' / (signature+'.attempts')).glob('*/raw.json'), key=lambda p: p.stat().st_mtime)
            if found:
                reused = found[-1]
        raw = json.loads(reused.read_text()) if reused else complete_json(system, body, **kwargs)
        write(directory / f'model_call_{len(calls)}.json', raw)
        calls.append({'stage': 'read' if system == READ_PROMPT else 'associate', 'reused': str(reused) if reused else None})
        if system == READ_PROMPT:
            # 本工具只补计算条件；结果参数属于其他流程，不让无关 μ* 候选阻断独立 Methods。
            parameter_keys = {'lambda_ep', 'omega_log', 'omega_log_k', 'mu_star', 'mu_star_reported_range'}
            exclusions.extend({'key': s.get('key'), 'reason': '本次定向任务不写结果参数'} for s in raw.get('settings', []) if s.get('key') in parameter_keys)
            raw = {**raw, 'settings': [s for s in raw.get('settings', []) if s.get('key') not in parameter_keys]}
        return raw
    print(json.dumps({'stage': 'reading', 'directory': str(directory), 'model': config.model}), flush=True)
    table_model = (lambda *args, **kwargs: json.loads((resume / 'table_assignments_raw.json').read_text())) if resume else condition_model
    approximations = classify_approximations(draft, context, table_model,
        on_response=lambda value: write(directory / 'table_assignments_raw.json', value))
    write(directory / 'table_assignments.json', approximations)
    project = projection(draft, approximations)
    if revalidate:
        old_backup = json.loads((revalidate / 'backup.json').read_text())
        old_ledger = json.loads((revalidate / 'ledger.json').read_text())
        for window in context['windows']:
            signature = fingerprint([old_ledger['version'], old_ledger['source_fingerprint'], window, identity, READ_PROMPT])
            if not (revalidate / 'cache' / (signature+'.json')).is_file():
                raise ValueError('旧完整阅读缓存与当前模型签名不一致')
        associations = revalidate_prior_candidates(draft, project, context, old_backup['draft'], old_ledger)
        ledger = {**old_ledger, 'associations': associations, 'revalidation': {
            'prior_directory': str(revalidate), 'current_source_fingerprint': context['source_fingerprint'],
            'original_draft_hash_verified': fingerprint(draft), 'policy': '当前原文数值/引用/近似/作用域校验全部重跑，不增加科学数值'}}
    else:
        ledger = generate_context_associations(project, context, condition_model, cache_dir=directory / 'cache', model_identity=identity)
    write(directory / 'call_sources.json', {'calls': calls, 'out_of_scope': exclusions})
    write(directory / 'ledger.json', ledger)
    proposed, applied, gaps = condition_proposal(draft, project, ledger['associations'], context | {'complete': ledger['complete']})
    write(directory / 'plan.json', {'task_id': task, 'draft_hash': fingerprint(draft), 'revision': version,
        'files': state['files'], 'proposed': proposed, 'applied': applied, 'gaps': gaps,
        'complete': ledger['complete'], 'model': llm_display_metadata(config)})
    print(json.dumps({'stage': 'prepared', 'plan': str(directory / 'plan.json'), 'complete': ledger['complete'],
                      'applied': len(applied), 'gaps': len(gaps)}), flush=True)


def apply(path):
    plan = json.loads(path.read_text())
    if not plan['complete'] or not plan['applied']:
        raise ValueError('读取不完整或没有通过校验的条件补全')
    task = plan['task_id']
    with upload_task_lock(task):
        state, draft = get_state(task), get_draft(task)
        assert_current(plan['draft_hash'], plan['revision'], draft, state)
        if state['files'] != plan['files']:
            raise ValueError('来源或角色变化，拒绝旧候选')
        sources(task, state)
        assert_conditions_only(draft, plan['proposed'])
        # 原始状态、草稿和模型账本已保存，不改 AI 初始产物或核对结论。
        saved = save_draft(task, plan['proposed'])
        if get_draft(task) != saved:
            raise ValueError('保存重读结果不同')
        checks = record_checks(task, saved, int(state['user_id']), plan['applied'])
    write(path.parent / 'applied.json', {'task_id': task, 'applied': len(plan['applied']), 'draft_hash': fingerprint(saved), 'uncertain_checks': checks})
    print(json.dumps({'stage': 'applied', 'task_id': task, 'count': len(plan['applied'])}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--task-id')
    group.add_argument('--apply-plan', type=Path)
    parser.add_argument('--resume-from', type=Path, help='仅复用相同来源与模型签名的真实读取响应；所有计算条件重新验证，关系阶段在线生成')
    parser.add_argument('--revalidate-prior', type=Path, help='真实旧候选的来源/草稿/目标/模型签名全部一致时，以现行验证及表行近似限制重新核对')
    args = parser.parse_args()
    prepare(args.task_id, args.resume_from, args.revalidate_prior) if args.task_id else apply(args.apply_plan)
