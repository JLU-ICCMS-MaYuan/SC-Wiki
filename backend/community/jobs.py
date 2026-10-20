"""独立 RQ 生成消费者；所有发布重新检查祖先状态和修订版本。"""
from contextlib import contextmanager
import uuid
from sqlalchemy.orm import Session
from backend.database import engine
from backend.rag.llm_context import set_llm_config, reset_llm_config
from .configuration import TIMEOUT, key, load_config, redis_connection
from .generation import GenerationError, create_question, fingerprint
from .models import CommunityAIBatch as Batch, CommunityEntry as Entry
from .service import actor_allowed, locked, now, batch_tasks, fail_job


@contextmanager
def capacity(connection):
    # 跨 Worker 实例的两槽租约；租约长于硬任务超时，死亡进程不会永久占槽。
    locks = [connection.lock(f"community-ai:slot:{i}", timeout=TIMEOUT+30, blocking_timeout=0) for i in range(2)]
    lock = next((item for item in locks if item.acquire(blocking=False)), None)
    if not lock:
        raise GenerationError("capacity_busy")
    try:
        yield lock
    finally:
        if lock.owned():
            lock.release()


def prepare(batch_id, job_id, connection, lease):
    with Session(engine) as db, db.begin():
        batch = locked(db, Batch, batch_id)
        if batch.job_id != job_id or batch.state != "queued":
            return
        batch.state, batch.started_at = "running", now()
        actor_allowed(db, batch.actor_id)
        tasks = batch_tasks(db, batch.id)
        selected = next(t for t in tasks if t.model_id == batch.question_model_id)
        config = load_config(connection, job_id, selected.model_id, selected.config_hash)
        category, question_id, actor_id = batch.category, batch.question_id, batch.actor_id
        selected_id, selected_name, selected_model = selected.model_id, selected.model_name, selected.model
    token = set_llm_config(config)
    try:
        if not question_id:
            # 全局选题锁串行去重，避免两个请求同时产生相同或近义问题。
            with connection.lock("community-ai:question", timeout=TIMEOUT+30, blocking_timeout=5):
                with Session(engine) as db:
                    title, body = create_question(db, category)
                with Session(engine) as db, db.begin():
                    actor_allowed(db, actor_id)
                    batch = locked(db, Batch, batch_id)
                    if batch.job_id != job_id or batch.state != "running" or not lease.owned():
                        raise GenerationError("generation_conflict")
                    question = Entry(kind="question", title=title, body=body, author_id=None,
                                     origin="ai", category=category, model_id=selected_id,
                                     model_name=selected_name, model=selected_model,
                                     question_hash=fingerprint(title), status="visible", activity_at=now(), created_at=now(), updated_at=now())
                    db.add(question); db.flush(); batch.question_id = question.id
                    question_id = question.id
        with Session(engine) as db, db.begin():
            batch = locked(db, Batch, batch_id)
            if batch.job_id != job_id or batch.state != 'running' or not lease.owned():
                raise GenerationError('generation_conflict')
            batch.state, batch.sources, batch.finished_at = 'succeeded', [], now()
            for task in batch_tasks(db, batch_id):
                task.state, task.error, task.finished_at = 'succeeded', '', now()
    finally:
        reset_llm_config(token)




def run(kind, identifier, job_id):
    engine.dispose(close=False)
    connection = redis_connection()
    try:
        with capacity(connection) as lease:
            if kind != "batch": raise GenerationError("workflow_changed")
            prepare(identifier, job_id, connection, lease)
    except Exception as exc:
        code = str(exc) if isinstance(exc, GenerationError) else "generation_failed"
        fail_job(kind, identifier, job_id, code)
    finally:
        connection.delete(key(job_id))
        connection.close()


def on_failure(job, connection, exc_type, exc_value, traceback):
    kind, identifier, job_id = job.args
    fail_job(kind, identifier, job_id, "worker_interrupted")
    connection.delete(key(job_id))
