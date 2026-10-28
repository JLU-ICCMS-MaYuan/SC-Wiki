"""浏览器隔离夹具：正式FastAPI进度路由 + 真实Redis，科学来源/模型结果为受控夹具。"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'isolated-progress-browser-only'

import uvicorn
from fastapi import FastAPI, HTTPException
from redis import Redis
from redis.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.api import evidence, rag
from backend.ingest import evidence_progress, upload_tasks, field_drafts, field_review, field_review_migration
from backend.rag.llm_context import request_llm_config
from backend.security import get_current_user


def main():
    with tempfile.TemporaryDirectory(prefix='ev168-browser-', dir='/tmp') as directory:
        socket = directory + '/redis.sock'
        process = subprocess.Popen([str(Path(sys.executable).parent / 'redis-server'), '--port', '0',
            '--unixsocket', socket, '--save', '', '--appendonly', 'no'], stdout=subprocess.DEVNULL)
        client = Redis(unix_socket_path=socket, decode_responses=True, retry=Retry(NoBackoff(), 0))
        try:
            for _ in range(100):
                try:
                    if client.ping(): break
                except Exception:
                    time.sleep(.02)
            assert client.ping()
            engine = create_engine('sqlite:///' + directory + '/fixture.sqlite')
            evidence.SessionLocal = sessionmaker(engine)
            upload_tasks.redis_client = evidence.redis_client = evidence_progress.redis_client = lambda: client
            draft = {'paper': {'title': 'Isolated progress fixture', 'year': 2026}, 'material_states': []}
            field_drafts.authorized_draft = lambda *a: (draft, None)
            field_review_migration.migrated = lambda *a: True
            evidence.science.load_results = lambda *a, **k: {}
            state = {'mode': 'normal', 'job_id': None}
            def validate(_): time.sleep(1.3)
            rag._validate_draft = validate
            def snapshot(body, user):
                time.sleep(1.3)
                snap = evidence.ev.complete_snapshot(body.target, body.target_id, [], [], draft)
                snap['draft_version_token'] = field_drafts.draft_version(draft)
                return snap, {}
            evidence.snapshot_for = snapshot
            def prepare(snapshot, cached):
                time.sleep(1.3)
                return snapshot, cached
            field_review.prepare_submission = prepare
            def check_version(*_):
                if state['mode'] == 'stale': raise HTTPException(409, detail='核对期间内容发生变化，未提交')
            field_review.validate_support_versions = check_version
            def enqueue(body, user, snapshot, cached):
                if state['mode'] == 'reused':
                    return {'status': 'completed', **evidence.review_response(snapshot, {})}
                identity = uuid4().hex
                job = {'id': identity, 'owner': user.id, 'snapshot': snapshot, 'cached': {}, 'results': {},
                       'status': 'queued', 'completed_batches': 0, 'total_batches': 5, 'current_batch': 0}
                client.setex(evidence.ev.task_key(identity), 3600, json.dumps(job))
                evidence.ev.write_job_control(job, client)
                state['job_id'] = identity
                return {'id': identity, 'status': 'queued', 'version': snapshot['version']}
            evidence.enqueue_review = enqueue
            app = FastAPI()
            app.include_router(evidence.router)
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role='admin')
            app.dependency_overrides[request_llm_config] = lambda: None
            @app.get('/fixture/state')
            def get_state():
                return {**state, 'job': evidence.ev.read_job_status(state['job_id'], 7) if state['job_id'] else None}
            @app.post('/fixture/mode')
            def mode(body: dict):
                state['mode'] = body['mode']
                return {'ok': True}
            @app.post('/fixture/job')
            def advance(body: dict):
                evidence.ev.update_job(state['job_id'], **body)
                return {'ok': True}
            uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('PROGRESS_TEST_PORT', '8198')), log_level='warning')
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__': main()
