"""问题内 FIFO 回答队列与同模型追加；模型调用不持有数据库事务。"""
from datetime import timedelta
import hashlib
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from backend.database import engine
from backend.rag.llm_context import set_llm_config, reset_llm_config
from .models import (CommunityEntry as Entry, CommunityModelAnswer as Card,
                     CommunityAnswerRequest as Request, CommunityAnswerTurn as Turn,
                     CommunityTurnRevision as Revision)
from .configuration import models, identity, redis_connection, save_configs, load_config, key, QUEUE, TIMEOUT, TTL
from .generation import GenerationError, retrieve_sources, approved_sources, sources_current, create_answer
from .service import actor_allowed, locked, now

ACTIVE = ('queued', 'running')


def model_options():
    return [{'key': identity(c), 'model_id': i, 'name': name, 'model': c.model} for i, name, c in models()]


def question_locked(db, question_id):
    question = locked(db, Entry, question_id)
    if question.kind != 'question' or question.status != 'visible':
        raise GenerationError('content_unavailable')
    return question


def dto(request):
    return {k: getattr(request, k) for k in ('id', 'request_id', 'question_id', 'sequence', 'model_name', 'model',
            'state', 'error', 'answer_id', 'turn_id', 'retry_of', 'created_at', 'started_at', 'finished_at')}


def enqueue_answer(actor_id, question_id, request_id, model_key, retry_of=None):
    # 幂等复读不依赖模型仍在目录中。
    with Session(engine) as db:
        existing = db.scalar(select(Request).where(Request.request_id == request_id))
        if existing:
            if (existing.actor_id, existing.question_id, existing.config_hash, existing.retry_of) != (actor_id, question_id, model_key, retry_of):
                raise GenerationError('request_conflict')
            return dto(existing)
    chosen = next(((i, name, c) for i, name, c in models() if identity(c) == model_key), None)
    if chosen is None:
        raise GenerationError('model_config_changed')
    model_id, name, config = chosen
    connection = redis_connection()
    job_id = 'community-answer-' + request_id
    try:
        connection.ping()
        with Session(engine) as db, db.begin():
            actor_allowed(db, actor_id)
            question_locked(db, question_id)
            existing = db.scalar(select(Request).where(Request.request_id == request_id).with_for_update())
            if existing:
                if (existing.actor_id, existing.question_id, existing.config_hash, existing.retry_of) != (actor_id, question_id, model_key, retry_of):
                    raise GenerationError('request_conflict')
                return dto(existing)
            card = db.scalar(select(Card).where(Card.question_id == question_id, Card.config_hash == model_key))
            if card and db.get(Entry, card.entry_id).status != 'visible':
                raise GenerationError('content_unavailable')
            last_request = db.scalar(select(Request.sequence).where(Request.question_id == question_id).order_by(Request.sequence.desc()).limit(1).with_for_update()) or 0
            last_card = db.scalar(select(Card.first_sequence).where(Card.question_id == question_id).order_by(Card.first_sequence.desc()).limit(1).with_for_update()) or 0
            request = Request(request_id=request_id, question_id=question_id, sequence=max(last_request, last_card)+1,
                              actor_id=actor_id, model_id=model_id, model_name=name[:200], model=config.model,
                              config_hash=model_key, state='queued', error='', job_id=job_id, retry_of=retry_of, created_at=now())
            db.add(request); db.flush()
            save_configs(connection, job_id, {model_id: config})
            result = dto(request)
        try:
            dispatch(question_id)
        except Exception:
            pass  # 已持久化的请求由监督补投递，不让用户误以为入队失败。
        return result
    finally:
        connection.close()


def retry_answer(actor_id, identifier, request_id):
    with Session(engine) as db:
        request = db.get(Request, identifier)
        if not request or request.state != 'failed':
            raise GenerationError('request_conflict')
        question_id, model_key = request.question_id, request.config_hash
    return enqueue_answer(actor_id, question_id, request_id, model_key, identifier)


def dispatch(question_id):
    connection = redis_connection()
    try:
        with Session(engine) as db, db.begin():
            locked(db, Entry, question_id)
            head = db.scalar(select(Request).where(Request.question_id == question_id, Request.state.in_(ACTIVE)).order_by(Request.sequence).limit(1).with_for_update())
            if not head or head.state != 'queued':
                return
            try:
                Job.fetch(head.job_id, connection=connection)
                return
            except NoSuchJobError:
                pass
            # 先前事务已保存请求及凭据；投递遗漏由监督周期再次补齐。
            Queue(QUEUE, connection=connection).enqueue('backend.community.answers.run', head.id,
                job_id=head.job_id, job_timeout=TIMEOUT, result_ttl=TTL, failure_ttl=TTL,
                on_failure='backend.community.answers.on_failure')
    finally:
        connection.close()


def dependencies_visible(db, snapshot):
    for item in snapshot or []:
        entry = db.get(Entry, item['entry_id'])
        if not entry or entry.status != 'visible':
            return False
    return True


def context_rows(db, question_id):
    rows = []
    entries = list(db.scalars(select(Entry).where(Entry.question_id == question_id, Entry.kind == 'answer', Entry.origin == 'ai', Entry.status == 'visible').order_by(Entry.id)))
    for entry in entries:
        first_request = db.scalar(select(Request).where(Request.answer_id == entry.id, Request.turn_id.is_(None), Request.state == 'succeeded'))
        if not sources_current(db, entry.citations) or (first_request and not dependencies_visible(db, first_request.context_snapshot)):
            continue
        card = db.scalar(select(Card).where(Card.entry_id == entry.id))
        rows.append({'key': f'A{entry.id}', 'entry_id': entry.id, 'turn_id': None,
                     'revision': entry.revision, 'card_revision': entry.revision,
                     'model_name': entry.model_name, 'model': entry.model,
                     'sequence': card.first_sequence if card else 0, 'body': entry.body,
                     'citations': entry.citations or []})
        turns = db.scalars(select(Turn).where(Turn.entry_id == entry.id).order_by(Turn.id))
        for turn in turns:
            request = db.get(Request, turn.request_id)
            if not sources_current(db, turn.citations) or not dependencies_visible(db, request.context_snapshot):
                continue
            rows.append({'key': f'A{entry.id}T{turn.id}', 'entry_id': entry.id, 'turn_id': turn.id,
                         'revision': turn.revision, 'card_revision': entry.revision,
                         'model_name': entry.model_name, 'model': entry.model,
                         'sequence': request.sequence, 'body': turn.body, 'citations': turn.citations or []})
    return sorted(rows, key=lambda row: (row['sequence'], row['entry_id'], row['turn_id'] or 0))


def manifest(rows):
    return [{**{k: row[k] for k in ('key', 'entry_id', 'turn_id', 'revision', 'card_revision', 'model_name', 'sequence')},
             'body_hash': hashlib.sha256(row['body'].encode()).hexdigest()} for row in rows]


def combine_sources(fresh, history):
    sources, seen = [], set()
    for source in [*fresh, *(s for row in history for s in row['citations'])]:
        signature = (source['paper_id'], source['paper_revision'], source.get('chunk_id'), source.get('content'))
        if signature not in seen:
            seen.add(signature)
            sources.append({**source, 'id': f'S{len(sources)+1}'})
    return sources


def finish_failure(identifier, code, only_queued=False):
    with Session(engine) as db, db.begin():
        initial = db.get(Request, identifier)
        if not initial:
            return None
        locked(db, Entry, initial.question_id)
        request = locked(db, Request, identifier)
        if request.state in ACTIVE and (not only_queued or request.state == 'queued'):
            request.state, request.error, request.finished_at = 'failed', code, now()
        return request.question_id


def run(identifier):
    from .jobs import capacity
    engine.dispose(close=False)
    connection = redis_connection()
    question_id = None
    job_id = None
    claimed = False
    try:
        with capacity(connection) as lease:
            with Session(engine) as db, db.begin():
                initial = db.get(Request, identifier)
                if not initial: return
                question_id, job_id = initial.question_id, initial.job_id
                actor_allowed(db, initial.actor_id)
                question = question_locked(db, question_id)
                head = db.scalar(select(Request).where(Request.question_id == question_id, Request.state.in_(ACTIVE)).order_by(Request.sequence).limit(1).with_for_update())
                if not head or head.id != identifier or head.state != 'queued':
                    return
                head.state, head.started_at = 'running', now(); claimed = True
                config = load_config(connection, job_id, head.model_id, head.config_hash)
                question_revision = question.revision
                question_text = question.title + '\n' + question.body
                history = context_rows(db, question_id)
                snapshot = manifest(history)
                head.context_snapshot = snapshot
                model_hash, actor_id = head.config_hash, head.actor_id
            token = set_llm_config(config)
            try:
                raw_sources = retrieve_sources(question_text)
                with Session(engine) as db:
                    sources = combine_sources(approved_sources(db, raw_sources), history)
                    if not sources_current(db, sources): raise GenerationError('sources_changed')
                body, citations = create_answer(question_text, sources, history)
            finally:
                reset_llm_config(token)
            with Session(engine) as db, db.begin():
                actor_allowed(db, actor_id)
                question = question_locked(db, question_id)
                # 所有被读取的卡片加锁，和 Go 编辑采用同样的祖先顺序。
                for entry_id in sorted({row['entry_id'] for row in history}):
                    locked(db, Entry, entry_id)
                request = locked(db, Request, identifier)
                if request.state != 'running' or question.revision != question_revision or not lease.owned():
                    raise GenerationError('generation_conflict')
                if manifest(context_rows(db, question_id)) != snapshot:
                    raise GenerationError('generation_conflict')
                if not sources_current(db, sources, lock=True): raise GenerationError('sources_changed')
                card = db.scalar(select(Card).where(Card.question_id == question_id, Card.config_hash == model_hash))
                replies = [{'key': row['key'], 'entry_id': row['entry_id'], 'turn_id': row['turn_id'],
                            'model_name': row['model_name'], 'sequence': row['sequence']} for row in history if f"[{row['key']}]" in body]
                if card:
                    entry = locked(db, Entry, card.entry_id)
                    if entry.status != 'visible': raise GenerationError('content_unavailable')
                    turn = Turn(entry_id=entry.id, request_id=request.id, body=body, citations=citations,
                                replies=replies, revision=1, human_edited=False, created_at=now(), updated_at=now())
                    db.add(turn); db.flush(); request.turn_id = turn.id
                    entry.revision += 1; entry.updated_at = now()
                else:
                    entry = Entry(kind='answer', title='', body=body, origin='ai', author_id=None,
                                  question_id=question_id, model_id=request.model_id, model_name=request.model_name,
                                  model=request.model, model_order=request.sequence, citations=citations, status='visible', activity_at=now(), created_at=now(), updated_at=now())
                    db.add(entry); db.flush()
                    db.add(Card(question_id=question_id, config_hash=model_hash, entry_id=entry.id, first_sequence=request.sequence))
                request.answer_id = entry.id; request.sources = sources
                request.state, request.error, request.finished_at = 'succeeded', '', now()
                question.activity_at = now()
    except Exception as exc:
        code = str(exc) if isinstance(exc, GenerationError) else 'generation_failed'
        if getattr(exc, 'code', '') in {'context_length_exceeded', 'context_window_exceeded'} or (getattr(exc, 'status_code', 0) == 400 and any(term in str(exc).lower() for term in ('context length', 'context window', 'maximum context'))):
            code = 'context_too_long'
        question_id = finish_failure(identifier, code, only_queued=not claimed)
        claimed = True
    finally:
        # 重放已运行或已完成任务不删除另一个执行者的凭据。
        if claimed and job_id: connection.delete(key(job_id))
        connection.close()
        if question_id:
            try: dispatch(question_id)
            except Exception: pass  # 监督周期补齐投递。


def on_failure(job, connection, exc_type, exc_value, traceback):
    question_id = finish_failure(job.args[0], 'worker_interrupted')
    connection.delete(key(job.id))
    if question_id: dispatch(question_id)


def reconcile_answers():
    connection = redis_connection()
    try:
        with Session(engine) as db:
            requests = list(db.scalars(select(Request).where(Request.state.in_(ACTIVE))))
            candidates = [(r.id, r.question_id, r.state, r.job_id, r.started_at, r.created_at) for r in requests]
        for identifier, question_id, state, job_id, started, created in candidates:
            try: status = Job.fetch(job_id, connection=connection).get_status(refresh=True)
            except NoSuchJobError: status = 'missing'
            overdue = started and started < now()-timedelta(seconds=TIMEOUT+90)
            expired = created < now()-timedelta(seconds=TTL)
            if status in {'failed', 'stopped', 'canceled', 'finished'} or overdue or expired:
                finish_failure(identifier, 'credentials_expired' if expired else 'worker_interrupted')
                connection.delete(key(job_id))
        for question_id in {row[1] for row in candidates}:
            dispatch(question_id)
    finally:
        connection.close()


def edit_turn(actor_id, turn_id, body, revision):
    with Session(engine) as db, db.begin():
        actor_allowed(db, actor_id)
        initial = db.get(Turn, turn_id)
        if not initial: raise GenerationError('content_unavailable')
        initial_entry = db.get(Entry, initial.entry_id)
        question_locked(db, initial_entry.question_id)
        entry = locked(db, Entry, initial.entry_id)
        turn = locked(db, Turn, turn_id)
        if entry.status != 'visible': raise GenerationError('content_unavailable')
        if turn.revision != revision: raise GenerationError('community_revision_conflict')
        db.add(Revision(turn_id=turn.id, revision=turn.revision, body=turn.body, citations=turn.citations,
                        replies=turn.replies, human_edited=turn.human_edited, actor_id=actor_id))
        turn.body, turn.human_edited, turn.updated_at = body, True, now()
        turn.revision += 1; entry.revision += 1; entry.updated_at = now()
        return {'id': turn.id, 'revision': turn.revision}
