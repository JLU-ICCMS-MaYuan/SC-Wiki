"""验证真实本地启动配置透传及真实RQ十任务并发上限。"""
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time
from uuid import uuid4

from rq import Queue, Worker
from redis import Redis
import pytest

from worker_capacity_probe import hold_form_slot

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated_tcp_redis():
    # RQ SpawnWorker 2.12 的子进程重建不支持Unix套接字的path参数；与本机业务一致走TCP。
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen([str(Path(sys.executable).with_name('redis-server')),
        '--bind', '127.0.0.1', '--port', str(port), '--save', '', '--appendonly', 'no'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    connection = Redis(host='127.0.0.1', port=port, decode_responses=True)
    try:
        for _ in range(100):
            assert process.poll() is None
            try:
                if connection.ping():break
            except Exception:time.sleep(0.02)
        else:raise AssertionError('隔离TCP Redis未就绪')
        yield connection, f'redis://127.0.0.1:{port}/0'
    finally:
        connection.close()
        process.terminate()
        process.wait(timeout=5)


def test_native_worker_launcher_preserves_configured_ten(tmp_path):
    script = (ROOT / 'scripts/dev.sh').read_text()
    start = script.index('start_worker() {')
    function = script[start:script.index('\nstart_goserver()', start)]
    binary = tmp_path / 'bin'
    binary.mkdir()
    capture = tmp_path / 'observed.json'
    watcher = binary / 'watchfiles'
    watcher.write_text('#!' + sys.executable + '\nimport json,os\nfrom pathlib import Path\n'
                       'Path(os.environ["CAPACITY_CAPTURE"]).write_text(json.dumps({"count":os.environ.get("UPLOAD_LLM_CONCURRENCY")}))\n')
    watcher.chmod(0o700)
    stubs = '''
pid_alive() { test -f "$CAPACITY_CAPTURE"; }
spawn() { shift; "$@"; }
sleep() { :; }
ok() { :; }
die() { exit 1; }
'''
    subprocess.run(['bash', '-c', stubs + function + '\nstart_worker\n'], check=True,
        env={**os.environ, 'UPLOAD_LLM_CONCURRENCY': '10', 'PY_BIN': str(binary),
             'REPO_ROOT': str(tmp_path), 'CAPACITY_CAPTURE': str(capture)}, timeout=10)
    assert json.loads(capture.read_text())['count'] == '10'


def test_ten_real_workers_run_ten_forms_and_queue_the_eleventh(isolated_tcp_redis, tmp_path):
    isolated_redis, redis_url = isolated_tcp_redis
    prefix = 'test-capacity-' + uuid4().hex
    queue = Queue('scwiki-upload', connection=isolated_redis)
    jobs = [queue.enqueue(hold_form_slot, redis_url, prefix, job_timeout=120) for _ in range(11)]
    environment = {**os.environ, 'REDIS_URL': redis_url, 'UPLOAD_LLM_CONCURRENCY': '10',
        'DATABASE_URL': 'sqlite:///:memory:', 'RAG_DATABASE_URL': 'sqlite:///:memory:',
        'SC_WIKI_DATA_DIR': str(tmp_path), 'JWT_SECRET_KEY': 'isolated-capacity-test-key',
        'PYTHONPATH': str(Path(__file__).parent) + os.pathsep + str(ROOT)}
    command = ('from backend.ingest import grobid_document; grobid_document.service_available=lambda:True; '
               'from backend.scripts.run_upload_workers import main; main()')
    log = (tmp_path / 'workers.txt').open('w')
    process = subprocess.Popen([sys.executable, '-c', command], cwd=ROOT, env=environment,
                               stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert process.poll() is None, (tmp_path / 'workers.txt').read_text()[-1500:]
            if int(isolated_redis.get(prefix + ':active') or 0) == 10:
                break
            time.sleep(0.1)
        else:
            raise AssertionError('未在60秒内同时运行10个隔离表单任务')
        assert len(Worker.all(connection=isolated_redis)) == 10
        assert queue.count == 1
        assert jobs[-1].get_status(refresh=True) == 'queued'
        assert int(isolated_redis.get(prefix + ':peak')) == 10
        isolated_redis.set(prefix + ':release', '1')
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if all(job.get_status(refresh=True) == 'finished' for job in jobs):
                break
            time.sleep(0.1)
        else:
            raise AssertionError('隔离11项任务未全部完成')
        assert int(isolated_redis.get(prefix + ':active')) == 0
        assert int(isolated_redis.get(prefix + ':peak')) == 10
    finally:
        isolated_redis.set(prefix + ':release', '1')
        process.terminate()
        try:
            process.wait(timeout=30)
        finally:
            log.close()
