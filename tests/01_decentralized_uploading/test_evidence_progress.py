"""准备进度使用隔离真实Redis，验证原子取消和HTTP请求边界。"""
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis import Redis
from redis.retry import Retry
from redis.backoff import NoBackoff

from backend.ingest import evidence_progress as progress


@pytest.fixture
def progress_redis(tmp_path, monkeypatch):
    # Unix socket、禁用TCP和持久化，不连接或清理业务Redis。
    directory = tempfile.TemporaryDirectory(prefix='ev168-', dir='/tmp')
    socket = directory.name + '/redis.sock'
    process = subprocess.Popen([str(Path(sys.executable).parent / 'redis-server'),
        '--port', '0', '--unixsocket', socket, '--save', '', '--appendonly', 'no'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = Redis(unix_socket_path=socket, decode_responses=True, retry=Retry(NoBackoff(), 0))
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(.02)
        assert client.ping()
        monkeypatch.setattr(progress, 'redis_client', lambda: client)
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        directory.cleanup()


def test_progress_is_monotonic_scoped_and_expires(progress_redis):
    identity = uuid4().hex
    for percent in [0, 5, 10, 5, 20]:
        progress.advance(identity, 7, 'submit:upload:test', percent)
    assert progress.read(identity, 7) == {'percent': 20, 'cancelled': False}
    assert 0 < progress_redis.ttl(progress.key(identity, 7)) <= 3600
    with pytest.raises(HTTPException) as error:
        progress.read(identity, 8)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        progress.advance(identity, 7, 'submit:upload:other', 20)


@pytest.mark.parametrize('before_start', [True, False])
def test_cancel_tombstone_cannot_be_overwritten(progress_redis, before_start):
    identity = uuid4().hex
    if not before_start:
        progress.advance(identity, 7, 'submit:upload:test', 5)
    progress.cancel(identity, 7)
    with pytest.raises(HTTPException) as error:
        progress.advance(identity, 7, 'submit:upload:test', 10)
    assert error.value.detail['code'] == 'evidence_preparation_cancelled'
    assert progress.read(identity, 7)['cancelled']


def test_invalid_id_and_legacy_requests(progress_redis):
    progress.advance(None, 7, 'submit:upload:test', 5)
    assert progress_redis.dbsize() == 0
    with pytest.raises(HTTPException) as error:
        progress.read('../other', 7)
    assert error.value.status_code == 422


@pytest.fixture
def http_client(progress_redis, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.api import evidence
    from backend.security import get_current_user
    from backend.rag.llm_context import request_llm_config
    from backend.ingest import field_drafts, field_review_migration

    engine = create_engine('sqlite:///' + str(tmp_path / 'progress.sqlite'))
    monkeypatch.setattr(evidence, 'SessionLocal', sessionmaker(engine))
    monkeypatch.setattr(field_drafts, 'authorized_draft', lambda *args: ({'paper': {}, 'material_states': []}, None))
    monkeypatch.setattr(field_review_migration, 'migrated', lambda *args: True)
    app = FastAPI()
    app.include_router(evidence.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role='admin')
    app.dependency_overrides[request_llm_config] = lambda: None
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_http_observes_real_preparation_before_post_returns(http_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from backend.api import evidence, rag
    from backend.ingest import field_review
    identity = uuid4().hex
    at_fields, fields_done, at_sources, sources_done = (Event() for _ in range(4))
    snapshot = evidence.ev.complete_snapshot('upload', 'test', [], [], {})
    def validate(_):
        at_fields.set()
        assert fields_done.wait(5)
    def sources(*_):
        at_sources.set()
        assert sources_done.wait(5)
        return snapshot, {}
    monkeypatch.setattr(rag, '_validate_draft', validate)
    monkeypatch.setattr(evidence, 'snapshot_for', sources)
    monkeypatch.setattr(field_review, 'prepare_submission', lambda s, c: (s, c))
    with ThreadPoolExecutor() as pool:
        result = pool.submit(http_client.post, '/api/rag/evidence/submit-check',
            json={'target': 'upload', 'target_id': 'test', 'progress_id': identity})
        try:
            assert at_fields.wait(5)
            path = '/api/rag/evidence/preparations/' + identity
            assert http_client.get(path).json()['percent'] == 0
            fields_done.set()
            assert at_sources.wait(5)
            assert http_client.get(path).json()['percent'] == 5
            assert not result.done()
        finally:
            fields_done.set()
            sources_done.set()
        response = result.result(timeout=5)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'completed'  # 空待核对集合复用路径，没有模型请求。
    assert http_client.get(path).json()['percent'] == 20


def test_http_cancel_during_sources_prevents_enqueue(http_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from backend.api import evidence
    identity = uuid4().hex
    entered, release = Event(), Event()
    def sources(*_):
        entered.set()
        assert release.wait(5)
        return {'version': 'v'}, {}
    monkeypatch.setattr(evidence, 'snapshot_for', sources)
    monkeypatch.setattr(evidence, 'enqueue_review', lambda *_: pytest.fail('取消后不得排队'))
    with ThreadPoolExecutor() as pool:
        result = pool.submit(http_client.post, '/api/rag/evidence/jobs',
            json={'target': 'upload', 'target_id': 'test', 'progress_id': identity})
        try:
            assert entered.wait(5)
            assert http_client.delete('/api/rag/evidence/preparations/' + identity).status_code == 200
        finally:
            release.set()
        response = result.result(timeout=5)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'evidence_preparation_cancelled'


def test_http_late_queue_result_is_cancelled(http_client, monkeypatch):
    from backend.api import evidence
    identity = uuid4().hex
    cancelled = []
    monkeypatch.setattr(evidence, 'snapshot_for', lambda *_: ({'version': 'v'}, {}))
    def enqueue(*_):
        progress.cancel(identity, 7)
        return {'id': 'late', 'status': 'queued'}
    monkeypatch.setattr(evidence, 'enqueue_review', enqueue)
    monkeypatch.setattr(evidence, 'cancel_job', lambda job, user: cancelled.append((job, user.id)))
    response = http_client.post('/api/rag/evidence/jobs',
        json={'target': 'upload', 'target_id': 'test', 'progress_id': identity})
    assert response.status_code == 409
    assert cancelled == [('late', 7)]


def test_http_progress_identity_validation_and_isolation(http_client):
    identity = uuid4().hex
    progress.advance(identity, 8, 'test', 10)
    assert http_client.get('/api/rag/evidence/preparations/' + identity).status_code == 404
    assert http_client.get('/api/rag/evidence/preparations/invalid').status_code == 422
    response = http_client.post('/api/rag/evidence/submit-check',
        json={'target': 'upload', 'target_id': 'test', 'progress_id': 'invalid'})
    assert response.status_code == 422
