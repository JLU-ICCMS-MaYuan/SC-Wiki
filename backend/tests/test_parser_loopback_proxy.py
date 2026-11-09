"""#136：本地解析服务直连，外网代理与既有排除规则保留。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import threading

import pytest

from backend.ingest.document_parsers import ParseOptions
from backend.ingest.structured_pdf import run_parser_worker


@pytest.mark.parametrize('parser', ['docling', 'mineru', 'marker'])
def test_parser_subprocess_reaches_loopback_without_changing_parent(tmp_path, monkeypatch, parser):
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # 一个不监听的代理明确检出“本机请求误走代理”，不依赖测试机器的系统设置。
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', 'existing.example.org')
    monkeypatch.setenv('no_proxy', 'other.example.org')
    monkeypatch.setenv('SC_WIKI_MARKER_PYTHON', sys.executable)
    monkeypatch.setenv('SC_WIKI_LLAMA_SERVER', sys.executable)
    import os
    parent = dict(os.environ)
    popen = subprocess.Popen
    captured = []
    def worker(_command, **kwargs):
        captured.append(kwargs['env'])
        response = _command[-1]
        code = (
            'import httpx,json,pathlib; '
            f'r=httpx.get("http://127.0.0.1:{server.server_port}/health",timeout=2); '
            'r.raise_for_status(); '
            f'pathlib.Path({str(response)!r}).write_text(json.dumps(r.json()))'
        )
        return popen([sys.executable, '-c', code], **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', worker)
    pdf = tmp_path / 'source.pdf'
    pdf.write_bytes(b'%PDF-source-unchanged')
    try:
        result = run_parser_worker(parser, pdf, ParseOptions(profile='layout', parser_options={
            'artifact_directory': str(tmp_path / 'artifacts'), 'timeout_seconds': 10}))
        assert result['status'] == 'ok'
        assert hits == ['/health']
        assert os.environ == parent
        env = captured[0]
        assert 'existing.example.org' in env['NO_PROXY']
        assert 'other.example.org' in env['no_proxy']
        for key in ('NO_PROXY', 'no_proxy'):
            assert {'127.0.0.1', 'localhost', '::1'} <= set(env[key].split(','))
        assert env['HTTP_PROXY'] == parent['HTTP_PROXY']
    finally:
        server.shutdown()
        server.server_close()
