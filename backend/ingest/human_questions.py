"""上传人工科学问题的SQL权威队列；答案不等于应用或审核通过。"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
import json
from backend import models

VERSION = 1
PENDING = {'waiting', 'investigating', 'answer_received', 'resuming'}

QUESTION_PROMPT = '''
当前支持request_human_question。先读完相关正文/SI、自纠能唯一确定的普通错误；只有
真实source_conflict、assignment_ambiguous、subject_ambiguous才请求人工。提供当前key、
实际已读source_ids、双方事实、checked_context及具体推荐处理。技术失败、格式错误、
预算耗尽、普通unknown或合法未报告不属于人工科学问题。不要求修改程序或绕过保护。
问题只暂挂该字段，继续处理无关字段；人工方向不是原文，也不是审核通过。
每条最终results还必须给出resolution：resolved（可由原文确定）、not_reported（合法未报告）、
unresolved（普通科学疑点、尚无明确冲突）或human_required（补读后仍有真实冲突/归属分歧）。
human_required还须同条填写reason_code、checked_context、recommendation，source_ids列双方实际依据；
程序会保存为人工问题，不能一边说明真实反证无法裁决、一边仅凭一侧来源返回resolved/supported。
若当前条只是某一结构的空间群，应分清“该结构表的符号有依据”和“同条件的结果归属已解决”，
不能把存在一侧支持当成已裁决双来源冲突；已有人工方向可以解决相应取舍但不抹除反证。
'''


def question_tool_definition():
    props = {key: {'type': 'string', 'minLength': 1} for key in
             ('key', 'reason', 'checked_context', 'recommendation')}
    props['reason_code'] = {'type': 'string', 'enum': ['source_conflict', 'assignment_ambiguous', 'subject_ambiguous']}
    props['source_ids'] = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}
    return {'type': 'function', 'function': {'name': 'request_human_question', 'strict': True,
        'description': '相关原文已读而真实科学冲突或归属仍无法决定时请求人工；继续其他字段。',
        'parameters': {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}}}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def enabled(state):
    policy = state.get('human_questions_policy') or {}
    return policy.get('version') == VERSION and policy.get('enabled') is True


def input_token(state):
    return digest([state.get('task_id'), sorted((f.get('file_id'), f.get('role'), f.get('sha256'))
        for f in state.get('files') or []), state.get('_parsing_workflow')])


def _row(session, state, owner=None, initial_draft=None):
    if owner is not None and int(state.get('user_id') or 0) != owner:
        raise PermissionError('只有上传者可以回答此任务的问题')
    row = session.get(models.ScientificUploadDraft, state['task_id'], with_for_update=True)
    if row is not None and row.owner_id != int(state['user_id']):
        raise PermissionError('问题队列所属用户不一致')
    if row is None:
        row = models.ScientificUploadDraft(task_id=state['task_id'], owner_id=int(state['user_id']),
            state=deepcopy(state), draft=deepcopy(initial_draft or state.get('partial_draft') or {'paper': {}, 'material_states': []}))
        session.add(row); session.flush()
    return row


def _queue(row):
    return deepcopy(row.state.get('human_questions') or {'version': VERSION, 'revision': 0, 'questions': []})


def _write(session, row, queue):
    queue['revision'] += 1
    row.state = {**row.state, 'human_questions': queue, 'cleanup_at': None}
    session.flush()


def append_question(session, state, route, *, recommendation, title=None, initial_draft=None):
    if not enabled(state) or route.get('kind') != 'human_required' or not route.get('requires_human'):
        raise ValueError('当前任务不接受新的人工科学问题')
    if state.get('paper_id') or state.get('status') in {'submitted', 'cancelled', 'duplicate'}:
        raise ValueError('稿件已交出或结束，不能追加上传问题')
    targets = deepcopy(route.get('target_refs') or [])
    sources = deepcopy(route.get('source_refs') or [])
    if not targets or not sources or not str(recommendation).strip():
        raise ValueError('人工问题必须有稳定目标、实际来源与推荐方向')
    row = _row(session, state, initial_draft=initial_draft); queue = _queue(row)
    source_identity = sorted(digest({k:s.get(k) for k in
        ('file_id', 'block_id', 'chunk_index', 'page_start', 'pdf_page', 'content', 'quote')}) for s in sources)
    target_identity = sorted(digest({k:t.get(k) for k in
        ('item_key', 'state_key', 'module_key', 'record_key', 'candidate_id', 'reading_id', 'content_hash', 'source_hash')}) for t in targets)
    logical = digest([route['reason_code'], target_identity, source_identity, input_token(state)])
    same = next((q for q in queue['questions'] if q['logical_key'] == logical), None)
    if same: return deepcopy(same)
    for q in queue['questions']:
        if q['state'] not in PENDING: continue
        old = {t.get('item_key') or t.get('candidate_id'): t for t in q['target_refs']}
        for t in targets:
            before = old.get(t.get('item_key') or t.get('candidate_id'))
            if before and any(before.get(k) != t.get(k) for k in ('content_hash', 'source_hash')):
                q['state'] = 'stale'
    question = {'question_id': uuid4().hex, 'logical_key': logical, 'prompt_revision': 1,
        'kind': route['reason_code'], 'title': str(title or route['reason'])[:4000],
        'checked_context': route.get('checked_context', ''), 'target_refs': targets, 'source_refs': sources,
        'dependency_refs': deepcopy(route.get('dependency_refs') or []),
        'target_token': digest(targets), 'input_token': input_token(state), 'state': 'waiting',
        'created_at': datetime.now(timezone.utc).isoformat(), 'answers': [],
        'options': [{'choice_id': 'recommended', 'label': '采用推荐处理', 'description': str(recommendation)[:4000]},
                    {'choice_id': 'investigate', 'label': '需要进一步查证', 'description': '保留问题，仅补查相关原文或原图'},
                    {'choice_id': 'manual', 'label': '人工填写', 'description': '填写本问题的处理方向与理由'}]}
    queue['questions'].append(question); _write(session, row, queue)
    return deepcopy(question)


def answer_question(session, state, owner, question_id, payload, *, current_targets=None):
    row = _row(session, state, owner); queue = _queue(row)
    q = next((q for q in queue['questions'] if q['question_id'] == question_id), None)
    if q is None: raise LookupError('人工问题不存在')
    body = {k:deepcopy(payload.get(k)) for k in ('answer_id', 'choice_id', 'manual_text', 'reason', 'prompt_revision', 'target_token')}
    signature = digest(body)
    previous = next((a for a in q['answers'] if a['answer_id'] == body['answer_id']), None)
    if previous:
        if previous['signature'] != signature: raise ValueError('同一答案编号对应不同内容')
        return deepcopy(previous['response'])
    if int(payload.get('expected_queue_revision', queue['revision'])) > queue['revision']:
        raise ValueError('问题队列版本超前，请刷新后重试')
    if state.get('paper_id') or state.get('status') in {'submitted', 'cancelled', 'duplicate'}:
        raise PermissionError('稿件已交出或结束，不能回答旧上传问题')
    if not body['answer_id'] or body['choice_id'] not in {'recommended', 'investigate', 'manual'}:
        raise ValueError('答案编号或选择无效')
    if body['choice_id'] == 'manual' and (not str(body.get('manual_text') or '').strip() or not str(body.get('reason') or '').strip()):
        raise ValueError('人工填写需要处理方向与理由')
    stale = (q['state'] not in {'waiting', 'investigating'} or q['input_token'] != input_token(state)
        or body['prompt_revision'] != q['prompt_revision'] or body['target_token'] != q['target_token'])
    if current_targets is not None:
        for target in q['target_refs']:
            key = target.get('item_key') or target.get('candidate_id')
            current = current_targets.get(key)
            stale |= current is None or any(current.get(k) != target.get(k) for k in ('content_hash', 'source_hash'))
    if stale:
        q.update(state='stale', rejected_answer={**body, 'actor_user_id': owner})
        _write(session, row, queue)
        return {'accepted': False, 'state': 'stale', 'answer_id': body['answer_id'], 'queue_revision': queue['revision']}
    q['state'] = 'investigating' if body['choice_id'] == 'investigate' else 'answer_received'
    direction = (body.get('manual_text') if body['choice_id'] == 'manual' else
        next(o['description'] for o in q['options'] if o['choice_id'] == body['choice_id']))
    answer = {**body, 'signature': signature, 'direction': direction, 'actor_user_id': owner,
              'occurred_at': datetime.now(timezone.utc).isoformat()}
    response = {'accepted': True, 'state': q['state'], 'answer_id': body['answer_id'], 'queue_revision': queue['revision']+1}
    answer['response'] = deepcopy(response)
    q['answers'].append(answer); _write(session, row, queue)
    return response


def public_queue(state):
    queue = state.get('human_questions') or {'version': VERSION, 'revision': 0, 'questions': []}
    questions = []
    for q in queue['questions']:
        item = {k:deepcopy(q[k]) for k in ('question_id', 'prompt_revision', 'kind', 'title', 'checked_context',
            'target_refs', 'target_token', 'state', 'created_at', 'options')}
        item['source_refs'] = [{k:deepcopy(s[k]) for k in ('file_id', 'source_name', 'block_id', 'chunk_index',
            'page_start', 'page_end', 'pdf_page', 'quote', 'content') if k in s} for s in q['source_refs']]
        if q.get('rejected_answer'): item['answer_draft'] = deepcopy(q['rejected_answer'])
        if q.get('answers'): item['last_answer'] = {k:deepcopy(q['answers'][-1].get(k)) for k in
            ('answer_id', 'choice_id', 'direction', 'reason', 'occurred_at')}
        questions.append(item)
    writable = not state.get('paper_id') and state.get('status') not in {'submitted', 'cancelled', 'duplicate'}
    return {'queue_revision': queue['revision'], 'pending_count': sum(q['state'] in PENDING for q in questions),
        'can_create_questions': enabled(state) and writable,
        'can_answer_existing': (enabled(state) or bool(questions)) and writable, 'questions': questions}


def merge_state(state, previous):
    """普通工作稿／进度保存不能用旧state覆盖刚提交的问题或答案。"""
    old = (previous or {}).get('human_questions')
    new = state.get('human_questions') or {}
    if old and old.get('revision', 0) >= new.get('revision', 0):
        state['human_questions'] = deepcopy(old)
        state.setdefault('human_questions_policy', deepcopy(previous.get('human_questions_policy')))
    return state


def _mirror(task_id):
    from backend.database import SessionLocal
    from .upload_tasks import redis_client, task_key, user_tasks_key
    with SessionLocal() as session:
        row = session.get(models.ScientificUploadDraft, task_id)
        state = deepcopy(row.state)
    client = redis_client()
    client.set(task_key(task_id), json.dumps(state, ensure_ascii=False))
    client.zadd(user_tasks_key(int(state['user_id'])), {task_id: state.get('updated_at', 0)})
    return state


def report_question(task_id, route, *, recommendation, title=None, draft=None):
    from backend.database import SessionLocal
    from .upload_tasks import upload_task_lock, get_state
    from .model_runtime import current_execution, ExecutionStopped
    with upload_task_lock(task_id):
        state = get_state(task_id)
        runtime = current_execution()
        if runtime and state.get('execution_generation') != runtime.generation:
            raise ExecutionStopped('旧执行不能追加人工问题')
        with SessionLocal.begin() as session:
            q = append_question(session, state, route, recommendation=recommendation, title=title, initial_draft=draft)
        try: _mirror(task_id)
        except Exception: pass  # SQL已经提交，缓存故障不能撤销题目或谎报为未保存。
    return q


def read_public(task_id, owner):
    from backend.database import SessionLocal
    from .upload_tasks import get_state
    state = get_state(task_id)
    if not state or int(state.get('user_id') or 0) != owner: raise PermissionError('只有上传者可以查看问题队列')
    with SessionLocal() as session:
        row = session.get(models.ScientificUploadDraft, task_id)
        if row and row.owner_id != owner: raise PermissionError('问题队列所属用户不一致')
        return public_queue(row.state if row else state)


def receive_answer(task_id, owner, question_id, payload):
    from backend.database import SessionLocal
    from .upload_tasks import get_state, get_draft, upload_task_lock
    with upload_task_lock(task_id):
        state = get_state(task_id)
        if not state: raise LookupError('任务不存在')
        with SessionLocal() as session:
            row = session.get(models.ScientificUploadDraft, task_id)
            if row is None: raise LookupError('问题不存在')
            q = next((q for q in _queue(row)['questions'] if q['question_id'] == question_id), None)
        if q is None: raise LookupError('问题不存在')
        targets = None
        if any(t.get('item_key') for t in q['target_refs']):
            from .property_evidence import upload_snapshot
            snapshot = upload_snapshot(task_id, owner, parsing_draft=get_draft(task_id))
            targets = {r['item_key']:r for r in snapshot['records']}
        else:
            targets = state.get('human_question_candidates') or {}
        with SessionLocal.begin() as session:
            result = answer_question(session, state, owner, question_id, payload, current_targets=targets)
        try: _mirror(task_id)
        except Exception: result['cache_sync_pending'] = True
    if result['accepted']:
        try: result['resume'] = dispatch_ready_answer(task_id)
        except Exception as error: result['resume_error'] = {'code': 'human_answer_resume_blocked', 'error_type': type(error).__name__}
    return result


def dispatch_ready_answer(task_id):
    from .upload_tasks import get_state, load_llm_config
    state = get_state(task_id)
    if state.get('status') != 'paused' or state.get('pause_reason') != 'human_questions':
        return 'safe_point_pending'
    from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
    from .model_runtime import resume_task
    reference = state.get('execution_model') or {}
    config = load_llm_config(state.get('job_id') or task_id) or load_llm_config(task_id)
    if config is None and str(reference.get('provider', '')).startswith('server:') and reference.get('catalog_id'):
        config = catalog_config(reference['catalog_id'])
    if config is None: raise ValueError('原模型配置引用不可用，已保留答案')
    token = set_llm_config(config)
    try: resume_task(task_id)
    finally:
        reset_llm_config(token)
    return 'queued'


def ready_answers(state):
    return [q for q in (state.get('human_questions') or {}).get('questions', [])
            if q['state'] in {'answer_received', 'investigating', 'resuming'} and q.get('answers')]


def finish_candidate_answers(task_id, outcomes):
    from backend.database import SessionLocal
    from .upload_tasks import upload_task_lock, get_state
    with upload_task_lock(task_id), SessionLocal.begin() as session:
        row = _row(session, get_state(task_id)); queue = _queue(row); changed = False
        for q in ready_answers(row.state):
            ids = [t.get('candidate_id') for t in q['target_refs']]
            if not ids or not all(key in outcomes for key in ids):
                continue
            current = next(item for item in queue['questions'] if item['question_id'] == q['question_id'])
            resolved = all(outcomes[key] for key in ids)
            current['state'] = 'resolved' if resolved else 'waiting'
            current['processing_note'] = ('已依据人工方向补查；字段审核保持独立' if resolved else
                                         '已按人工方向补查，但归属仍未确定；保留原文与已有成功结构，等待进一步方向')
            if not resolved:
                current['prompt_revision'] += 1
            changed = True
        if changed: _write(session, row, queue)
    if changed:
        try: _mirror(task_id)
        except Exception: pass


def question_pending(state, question_ids):
    ids = set(question_ids)
    return [q for q in (state.get('human_questions') or {}).get('questions', []) if q['question_id'] in ids and q['state'] in PENDING]


def invalidate_changed_targets(task_id, records):
    """回答接受到安全点之间值也可能改变；不能拿旧方向覆盖新值或循环重排。"""
    from backend.database import SessionLocal
    from .upload_tasks import upload_task_lock, get_state
    current = {r['item_key']: r for r in records}
    with upload_task_lock(task_id), SessionLocal.begin() as session:
        row = _row(session, get_state(task_id)); queue = _queue(row); changed = False
        for q in queue['questions']:
            if q['state'] not in PENDING:
                continue
            for target in q['target_refs']:
                key = target.get('item_key')
                if not key or key not in current:
                    continue  # 当前材料小组以外的目标不凭局部快照判为删除。
                if any(current[key].get(k) != target.get(k) for k in ('content_hash', 'source_hash')):
                    q['state'] = 'stale'
                    q['processing_note'] = '安全点核验目标版本已变化，未应用旧答案；当前值和回答均保留'
                    changed = True
                    break
        if changed: _write(session, row, queue)
    if changed:
        try: _mirror(task_id)
        except Exception: pass


def mark_processed(task_id, item_keys):
    from backend.database import SessionLocal
    from .upload_tasks import upload_task_lock, get_state
    with upload_task_lock(task_id), SessionLocal.begin() as session:
        state = get_state(task_id); row = _row(session, state); queue = _queue(row); changed = False
        for q in queue['questions']:
            if q['state'] not in {'answer_received', 'resuming', 'investigating'}: continue
            if any((t.get('item_key') or t.get('candidate_id')) in item_keys for t in q['target_refs']):
                q['state'] = 'waiting' if q['answers'][-1]['choice_id'] == 'investigate' else 'resolved'
                q['processing_note'] = '相关查证已执行；原科学审核资格保持独立'
                changed = True
        if changed: _write(session, row, queue)
    if changed:
        try: _mirror(task_id)
        except Exception: pass


def answer_material(question, answer):
    """同一份人工材料先供本次模型读取，再按原文本附件契约保存。"""
    content = ('解析问题 ' + question['question_id'] + ' / 答案 ' + answer['answer_id'] + '\n' +
        answer['direction'] + '\n理由：' + (answer.get('reason') or answer['direction']) +
        '\n原始分歧：' + question['title'] + '\n原文依据：\n' + json.dumps(question['source_refs'], ensure_ascii=False))
    return {'kind': 'text_file', 'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(),
        'filename': 'parsing-question-' + question['question_id'] + '-' + answer['answer_id'] + '.txt',
        'source_description': '解析问题人工方向，非论文原句', 'submitted_by_user_id': answer['actor_user_id']}


def answer_context(state, records):
    """仅向对应稳定字段投影已接受方向，永远不设置审核通过。"""
    by_item = {r['item_key']:r for r in records}; result = {}
    for q in (state.get('human_questions') or {}).get('questions', []):
        if q['state'] not in {'answer_received', 'resuming', 'resolved', 'investigating'} or not q.get('answers'): continue
        answer = q['answers'][-1]
        for target in q['target_refs']:
            record = by_item.get(target.get('item_key'))
            if not record or any(record.get(k) != target.get(k) for k in ('content_hash', 'source_hash')): continue
            entry = result.setdefault(record['key'], {'decisions': [], 'items': [], 'images': [], 'pdf_refs': []})
            entry['decisions'].append({'reason': answer.get('reason') or answer['direction'],
                'submitted_by_user_id': answer['actor_user_id']})
            entry['items'].append(answer_material(q, answer))
    return result


def waiting_item_keys(state):
    return {t['item_key'] for q in (state.get('human_questions') or {}).get('questions', [])
            if q['state'] == 'waiting' for t in [*q['target_refs'], *(q.get('dependency_refs') or [])] if t.get('item_key')}


def persist_directions(session, state, snapshot, item_keys, *, model_read=False):
    """人工方向沿既有人工材料写入；不创建审核决定、不覆盖已有材料。"""
    from . import manual_evidence as manual
    by_item = {r['item_key']: r for r in snapshot['records']}
    applied = set()
    for q in ready_answers(state):
        answer = q['answers'][-1]
        if answer['choice_id'] == 'investigate':
            continue
        for target in q['target_refs']:
            key = target.get('item_key')
            if key not in item_keys or key not in by_item:
                continue
            existing = manual.read_field(session, snapshot, snapshot, key, include_history=False)
            material = answer_material(q, answer)
            if any(item.get('sha256') == material['sha256'] and item.get('filename') == material['filename']
                   for item in existing.get('items') or []):
                applied.add(key)
                continue
            saved = manual.add_file(session, snapshot, snapshot, key, answer['actor_user_id'],
                filename=material['filename'], raw=material['content'].encode(), source_description=material['source_description'])
            if not existing.get('reason'):
                manual.save_explanation(session, snapshot, snapshot, key, answer['actor_user_id'],
                    reason=(answer.get('reason') or answer['direction'])[:4000], no_evidence_reason='',
                    text_items=[], changed_fields={'reason'})
            if model_read:
                item = next(item for item in saved['items'] if item.get('sha256') == material['sha256'])
                manual.mark_ai_read(session, [{'row_id': saved['id'], 'item_id': item['id']}], read=True)
            applied.add(key)
    return applied


def pause_for_questions(task_id, *, allow_ready=False):
    """仅在检查点已保存、只剩人工待答时释放当前Worker。"""
    from .upload_tasks import upload_task_lock, get_state, get_draft, update_state
    from .model_runtime import ExecutionStopped, digest as draft_digest
    with upload_task_lock(task_id):
        state = get_state(task_id)
        if not any(q['state'] in PENDING for q in (state.get('human_questions') or {}).get('questions', [])):
            return False
        # 若答案在最后一个安全点刚到达，让现有Worker再领取；不制造第二份并发作业。
        if allow_ready and ready_answers(state):
            return False
        update_state(task_id, status='pausing', processing_status='pausing', pause_reason='human_questions',
            execution_generation=int(state.get('execution_generation') or 0) + 1,
            execution_draft_hash=draft_digest(get_draft(task_id)), execution_resumable=True,
            cleanup_at=None, processing_error=None)
    raise ExecutionStopped('仅剩人工待答，检查点已保存')
