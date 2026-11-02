"""固定资讯队列和可恢复的日调度；不导入上传任务。"""
from datetime import datetime, timedelta, timezone
import logging
import os
import time
from zoneinfo import ZoneInfo

from redis import Redis
from redis.exceptions import LockError
from rq import Queue
from rq.job import JobStatus
from sqlalchemy.orm import Session

from .domain import CollectionError, SOURCES, parse_time
from .models import NewsFeedSource

QUEUE_NAME = "scwiki-news"
JOB_TIMEOUT = 900
ACTIVE = {JobStatus.QUEUED, JobStatus.STARTED, JobStatus.DEFERRED, JobStatus.SCHEDULED}


def scheduled_at(now, hour=8, zone="Asia/Shanghai"):
    local = now.astimezone(ZoneInfo(zone))
    result = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if result > local:
        result -= timedelta(days=1)
    return result.astimezone(timezone.utc)


def due(state, cutoff, now):
    if state is None:
        return True
    if state.status == "running" and state.last_started_at:
        return now - parse_time(state.last_started_at) > timedelta(seconds=JOB_TIMEOUT + 100)
    if state.status in {"failed", "partial"} and state.last_finished_at:
        return now - parse_time(state.last_finished_at) >= timedelta(hours=1)
    if state.last_success_at and parse_time(state.last_success_at) >= cutoff:
        return False
    return True


def redis_connection():
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL 未设置，资讯进程拒绝使用隐式默认连接")
    # RQ Worker 通过 PubSub 长时间阻塞读取；短 socket_timeout 会让空闲队列错误退出。
    return Redis.from_url(url, socket_timeout=None, socket_connect_timeout=10)


def enqueue_due(engine, connection, now=None, hour=8, zone="Asia/Shanghai"):
    now = now or datetime.now(timezone.utc)
    cutoff = scheduled_at(now, hour, zone)
    lock = connection.lock("scwiki-news:schedule-lock", timeout=30, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return []
    try:
        queue = Queue(QUEUE_NAME, connection=connection, default_timeout=JOB_TIMEOUT)
        queued = []
        with Session(engine) as db:
            for source in SOURCES:
                if not due(db.get(NewsFeedSource, source), cutoff, now):
                    continue
                job_id = "scwiki-news-" + source
                previous = queue.fetch_job(job_id)
                if previous and previous.get_status(refresh=True) in ACTIVE:
                    # RQ worker 的维护循环负责移除死亡 worker 遗留的 started 作业。
                    continue
                if previous:
                    previous.delete()
                queue.enqueue("backend.news.scheduler.run_job", source, job_id=job_id,
                              job_timeout=JOB_TIMEOUT, result_ttl=86400, failure_ttl=86400)
                queued.append(source)
        return queued
    finally:
        try:
            lock.release()
        except LockError:
            logging.getLogger(__name__).warning("news schedule lock expired")


def run_job(source):
    from backend.database import engine
    from .service import collect_source
    from .sources import Sources

    # RQ 在子进程中运行，不复用父进程已有的数据库连接。
    engine.dispose(close=False)
    connection = redis_connection()
    lock = connection.lock("scwiki-news:collection-lock", timeout=JOB_TIMEOUT + 100, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        # 没有取得锁不发请求，调度将在本作业结束后重试。
        raise CollectionError("collection_busy")
    transport = None
    try:
        started = time.monotonic()
        def guard(reserve=30):
            if time.monotonic() - started > JOB_TIMEOUT - reserve or not lock.owned():
                raise CollectionError("collection_timeout")
        sources = Sources(max_pages=int(os.environ.get("NEWS_MAX_PAGES", "100")),
                          contact=os.environ.get("NEWS_CONTACT_EMAIL", ""))
        transport = sources.transport
        # 网络提前结束，为已经取得的候选留出独立写库时间。
        transport.guard = lambda: guard(60)
        return collect_source(engine, source, sources, initial_days=int(os.environ.get("NEWS_INITIAL_DAYS", "7")),
                              before_commit=guard)
    finally:
        if transport:
            transport.close()
        try:
            lock.release()
        except LockError:
            logging.getLogger(__name__).warning("news collection lock expired")


def schedule_forever(engine, connection, hour=8, zone="Asia/Shanghai"):
    while True:
        try:
            enqueue_due(engine, connection, hour=hour, zone=zone)
            enqueue_relevance(connection)
            enqueue_classification(connection)
        except Exception as exc:
            logging.getLogger(__name__).error("news scheduler failed: %s", type(exc).__name__)
        time.sleep(60)


def enqueue_classification(connection):
    """每轮采集入队之后最多追加一个短分类任务，独立锁避免并发调度重复。"""
    from .classification import JOB_TIMEOUT as classification_timeout

    return _enqueue_short_job(connection, "classification", classification_timeout)


def enqueue_relevance(connection):
    from .relevance import JOB_TIMEOUT as relevance_timeout

    return _enqueue_short_job(connection, "relevance", relevance_timeout)


def _enqueue_short_job(connection, kind, timeout):
    lock = connection.lock("scwiki-news:" + kind + "-schedule", timeout=30, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return False
    try:
        queue = Queue(QUEUE_NAME, connection=connection)
        job_id = "scwiki-news-" + kind
        previous = queue.fetch_job(job_id)
        if previous and previous.get_status(refresh=True) in ACTIVE:
            return False
        if previous:
            previous.delete()
        queue.enqueue("backend.news.scheduler.run_" + kind + "_job", job_id=job_id,
                      job_timeout=timeout, result_ttl=86400, failure_ttl=86400)
        return True
    finally:
        try:
            lock.release()
        except LockError:
            logging.getLogger(__name__).warning("news %s schedule lock expired", kind)


def run_classification_job():
    from backend.database import engine
    from .classification import classify_batch

    engine.dispose(close=False)
    return classify_batch(engine)


def run_relevance_job():
    from backend.database import engine
    from .relevance import review_batch

    engine.dispose(close=False)
    return review_batch(engine)
