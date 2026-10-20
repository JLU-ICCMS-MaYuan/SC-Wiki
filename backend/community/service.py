"""AI 问答请求、任务分发及幂等状态。"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import secrets
import uuid

from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import engine
from backend.models import User
from .models import CommunityAIBatch as Batch, CommunityAITask as Task, CommunityEntry as Entry
from .configuration import QUEUE, TIMEOUT, current_configs, identity, key, models, redis_connection, save_configs
from .generation import CATEGORIES, GenerationError

ACTIVE = {"queued", "running"}

def now():
    return datetime.utcnow()


def actor_allowed(db, actor_id):
    user = db.scalar(select(User).where(User.id == actor_id).with_for_update(read=True).execution_options(populate_existing=True))
    if not user or user.role != "superadmin" or user.account_status != "active" or not user.is_email_verified:
        raise GenerationError("superadmin_required")


def locked(db, cls, identifier):
    row = db.scalar(select(cls).where(cls.id == identifier).with_for_update().execution_options(populate_existing=True))
    if not row:
        raise GenerationError("content_unavailable")
    return row


def batch_tasks(db, batch_id):
    return list(db.scalars(select(Task).where(Task.batch_id == batch_id).order_by(Task.model_order)))


def sync_batch(db, batch):
    tasks = batch_tasks(db, batch.id)
    if tasks and all(t.state not in ACTIVE for t in tasks):
        succeeded = sum(t.state == "succeeded" for t in tasks)
        batch.state = "succeeded" if succeeded == len(tasks) else "partial" if succeeded else "failed"
        batch.finished_at = now()


def refresh_batch(batch_id):
    with Session(engine) as db, db.begin():
        batch = locked(db, Batch, batch_id)
        sync_batch(db, batch)


def fail_job(kind, identifier, job_id, code):
    with Session(engine) as db, db.begin():
        row = locked(db, Batch if kind == "batch" else Task, identifier)
        if row.job_id != job_id or row.state not in ACTIVE:
            return
        row.state, row.error, row.finished_at = "failed", code, now()
        if kind == "batch":
            for task in batch_tasks(db, row.id):
                if not task.job_id:
                    task.state, task.error = "failed", "preparation_failed"
        batch_id = row.batch_id if kind == "task" else None
    if batch_id:
        refresh_batch(batch_id)


def enqueue(kind, identifier, job_id, configs):
    connection = redis_connection()
    try:
        save_configs(connection, job_id, configs)
        Queue(QUEUE, connection=connection).enqueue(
            "backend.community.jobs.run", kind, identifier, job_id,
            job_id=job_id, job_timeout=TIMEOUT, result_ttl=86400, failure_ttl=86400,
            on_failure="backend.community.jobs.on_failure")
    except Exception:
        fail_job(kind, identifier, job_id, "queue_unavailable")
        try:
            connection.delete(key(job_id))
        except Exception:
            pass
    finally:
        connection.close()


def submit(actor_id, request_id, title=None, body=""):
    request_hash = hashlib.sha256(json.dumps([title, body], ensure_ascii=False).encode()).hexdigest()
    with Session(engine) as db:
        existing = db.get(Batch, request_id)
        if existing:
            if existing.actor_id != actor_id or existing.request_hash != request_hash:
                raise GenerationError("request_conflict")
            return existing.id
    available = models() if title is None else []
    connection = redis_connection()
    try:
        if title is None: connection.ping()
    except Exception:
        raise GenerationError("queue_unavailable") from None
    finally:
        connection.close()
    # 所有创建在同一发起人共享锁下完成；数据库 UUID 唯一键负责并发幂等。
    with Session(engine) as db, db.begin():
        actor_allowed(db, actor_id)
        category = secrets.choice(tuple(CATEGORIES)) if title is None else ""
        selected = secrets.choice(available) if available else None
        question_model = selected[0] if selected else ""
        batch = Batch(id=request_id, actor_id=actor_id, request_hash=request_hash,
                      category=category, question_model_id=question_model, state="queued", error="",
                      job_id="community-"+uuid.uuid4().hex, attempt=1, created_at=now())
        if title is not None:
            question = Entry(kind="question", title=title, body=body, author_id=actor_id,
                             origin="human", status="visible", activity_at=now(), created_at=now(), updated_at=now())
            db.add(question); db.flush()
            batch.question_id = question.id
            batch.state, batch.sources, batch.finished_at = "succeeded", [], now()
        db.add(batch); db.flush()
        for order, (identifier, name, config) in enumerate([selected] if selected else []):
            db.add(Task(batch_id=batch.id, model_id=identifier, model_name=name[:200], model=config.model,
                        config_hash=identity(config), model_order=order, state="queued", error="", job_id="",
                        attempt=0, question_revision=1, answer_revision=0))
        job_id = batch.job_id
    if selected:
        enqueue("batch", request_id, job_id, {selected[0]: selected[2]})
    return request_id


def retry_batch(actor_id, batch_id):
    with Session(engine) as db, db.begin():
        actor_allowed(db, actor_id)
        batch = locked(db, Batch, batch_id)
        if batch.state in ACTIVE:
            return batch.id
        if batch.sources is not None:
            raise GenerationError("retry_model_separately")
        tasks = batch_tasks(db, batch.id)
        configs = current_configs(tasks)
        batch.state, batch.error, batch.finished_at = "queued", "", None
        batch.attempt += 1; batch.job_id = "community-"+uuid.uuid4().hex
        for task in tasks:
            task.state, task.error = "queued", ""
        job_id = batch.job_id
    enqueue("batch", batch_id, job_id, configs)
    return batch_id


def retry_task(actor_id, task_id):
    raise GenerationError("workflow_changed")


def reconcile():
    connection = redis_connection()
    try:
        with Session(engine) as db:
            rows = [("batch", b.id, b.job_id, b.started_at, b.created_at, b.sources is not None) for b in db.scalars(select(Batch).where(Batch.state.in_(ACTIVE)))]
            rows += [("task", t.id, t.job_id, t.started_at, None, False) for t in db.scalars(select(Task).where(Task.state.in_(ACTIVE), Task.job_id != ""))]
        for kind, identifier, job_id, started, created, prepared in rows:
            try:
                job = Job.fetch(job_id, connection=connection)
                status = job.get_status(refresh=True)
            except NoSuchJobError:
                status = "missing"
            if kind == "batch" and prepared:
                # 已准备完毕的批次由回答任务推进；不能把准备任务完成误判为批次失败。
                continue
            overdue = started and started < now()-timedelta(seconds=TIMEOUT+90)
            expired = created and created < now()-timedelta(hours=24)
            age = started or created
            missing = status == "missing" and age and age < now()-timedelta(seconds=60)
            if status in {"failed", "stopped", "canceled", "finished"} or missing or overdue or expired:
                fail_job(kind, identifier, job_id, "worker_interrupted")
                connection.delete(key(job_id))
    finally:
        connection.close()
    from .answers import reconcile_answers
    reconcile_answers()


def batch_dto(db, batch):
    return {"id": batch.id, "question_id": batch.question_id, "state": batch.state, "error": batch.error,
            "category": batch.category, "can_retry": batch.sources is None and batch.state == "failed",
            "tasks": []}
