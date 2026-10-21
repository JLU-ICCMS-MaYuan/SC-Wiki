"""真实长请求和文件热重载验证：旧连接不能永久占住本地服务。"""
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def test_reload_releases_unfinished_request_and_starts_replacement(tmp_path):
    script = (ROOT / 'scripts/dev.sh').read_text()
    match = re.search(r'--timeout-graceful-shutdown\s+(\d+)', script)
    assert match, '本地Python启动须明确设置有限关闭等待'
    timeout = int(match[1])
    assert 0 < timeout <= 15
    backend = tmp_path / 'backend'
    backend.mkdir()
    (backend / '__init__.py').write_text('')
    source = backend / 'main.py'
    source.write_text('''import asyncio, os
from fastapi import FastAPI
app = FastAPI()
@app.get('/health')
async def health(): return {'pid':os.getpid()}
@app.get('/pending')
async def pending():
    print('TEST_PENDING_STARTED', flush=True)
    await asyncio.Event().wait()
''')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    output = tmp_path / 'server.log'
    env = {**os.environ, 'PYTHONPATH': str(tmp_path), 'PYTHONUNBUFFERED': '1'}
    with output.open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1',
            '--port', str(port), '--reload', '--reload-dir', str(backend),
            '--timeout-graceful-shutdown', str(timeout)], cwd=tmp_path, env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    pending = None
    def health():
        import json
        try:
            with urlopen(f'http://127.0.0.1:{port}/health', timeout=0.4) as response:
                return json.loads(response.read())['pid']
        except (OSError, ValueError):
            return None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            original = health()
            if original: break
            assert server.poll() is None, output.read_text()
            time.sleep(0.1)
        else: raise AssertionError('隔离测试服务未启动：' + output.read_text())
        pending = subprocess.Popen(['curl', '--noproxy', '*', '--max-time', str(timeout + 20),
            '-s', f'http://127.0.0.1:{port}/pending'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 5
        while 'TEST_PENDING_STARTED' not in output.read_text():
            assert time.monotonic() < deadline
            time.sleep(0.05)
        time.sleep(0.3)
        source.write_text(source.read_text() + '\n# reload regression\n')
        deadline = time.monotonic() + timeout + 12
        while time.monotonic() < deadline:
            replacement = health()
            if replacement and replacement != original: break
            time.sleep(0.1)
        else: raise AssertionError('热重载未在关闭期限后恢复：' + output.read_text())
        assert 'timeout graceful shutdown exceeded' in output.read_text()
        pending.wait(timeout=3)
    finally:
        if pending and pending.poll() is None:
            pending.terminate()
            pending.wait(timeout=3)
        os.killpg(server.pid, signal.SIGTERM)
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, signal.SIGKILL)
            server.wait(timeout=3)
