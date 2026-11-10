"""#224：真实客户端验证每轮5次、自动暂停及人工续跑边界。"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace as NS

import httpx
from openai import APIStatusError, OpenAI
import pytest

from backend.ingest import model_runtime, upload_tasks
from backend.ingest.upload_contracts import apply_state_changes
from backend.rag import llm
from backend.tests.test_model_runtime import setup_runtime


@pytest.fixture
def task_runtime(tmp_path, monkeypatch):
    runtime, context, state = setup_runtime(tmp_path, monkeypatch)
    draft = {'paper': {'title': '保留的人工草稿'}}
    persisted, enqueued = [], []

    def update(_task_id, **changes):
        state.update(apply_state_changes(state, now=100, **changes))
        return dict(state)

    monkeypatch.setattr(upload_tasks, 'get_state', lambda _: dict(state))
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda _: draft)
    monkeypatch.setattr(upload_tasks, 'update_state', update)
    monkeypatch.setattr(upload_tasks, 'upload_task_lock', lambda _: runtime.lock())
    monkeypatch.setattr(upload_tasks, 'enqueue_processing', lambda _: enqueued.append(1))
    monkeypatch.setattr(upload_tasks, 'redis_client', lambda: NS(
        persist=lambda key: persisted.append(key), get=lambda _: json.dumps(draft)))
    return runtime, context, state, draft, persisted, enqueued


@contextmanager
def model_server(monkeypatch, failure_kind, *, failures=9):
    seen, failed = [], []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append(request)
            checkpoint = request['messages'][1]['content'] == 'completed checkpoint'
            if not checkpoint:
                failed.append(request)
            if not checkpoint and len(failed) <= failures:
                if failure_kind == 'empty_sse':
                    body = b'data: [DONE]\n\n'
                    status, content_type = 200, 'text/event-stream'
                else:
                    body = json.dumps({'error': {'code': 'service_unavailable',
                        'message': '上游暂时不可用', 'request_id': 'fixture-request-id',
                        'output_started': False, 'retryable': True}}).encode()
                    status, content_type = int(failure_kind), 'application/json'
            else:
                body = ('data: ' + json.dumps({'id': 'fixture',
                    'object': 'chat.completion.chunk', 'choices': [{'index': 0,
                        'delta': {'content': '{"value":42}'}, 'finish_reason': 'stop'}]})
                    + '\n\ndata: [DONE]\n\n').encode()
                status, content_type = 200, 'text/event-stream'
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(llm, '_client', lambda _timeout: OpenAI(api_key='isolated-fixture',
        base_url=f'http://127.0.0.1:{server.server_port}/v1', max_retries=0,
        http_client=httpx.Client(trust_env=False)))
    monkeypatch.setattr(llm, 'get_llm_config', lambda: NS(model='fixture'))
    try:
        yield seen, failed
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('failure_kind', ['503', '429', 'empty_sse'])
def test_five_failures_pause_and_manual_resume_gets_five_fresh_attempts(
        task_runtime, tmp_path, monkeypatch, failure_kind):
    runtime, context, state, draft, persisted, enqueued = task_runtime
    schema = {'type': 'object', 'properties': {'value': {'type': 'integer'}},
              'required': ['value'], 'additionalProperties': False}
    with model_server(monkeypatch, failure_kind) as (seen, failed):
        with context(runtime):
            assert llm.complete_json('contract', 'completed checkpoint', response_schema=schema) == {'value': 42}
            with pytest.raises(model_runtime.ExecutionStopped, match='5'):
                llm.complete_json('contract', 'unfinished source', response_schema=schema)
        assert len(failed) == 5 and len(seen) == 6
        assert state['status'] in {'pausing', 'paused'}
        assert state['execution_draft_hash'] == model_runtime.digest(draft)
        assert state['cleanup_at'] is None
        assert persisted == [upload_tasks.draft_key(runtime.task_id)]
        activity = state['model_activity']
        assert activity['retry_at'] is None and '5' in activity['error']['message']
        if failure_kind != 'empty_sse':
            assert activity['error']['request_id'] == 'fixture-request-id'
        # 作业退出后沿既有暂停状态继续，完成响应不再发送到HTTP服务。
        upload_tasks.update_state(runtime.task_id, status='paused', processing_status='paused')
        from backend.rag import llm_context
        monkeypatch.setattr(llm_context, 'get_llm_config', lambda: NS(
            provider='fixture', model='fixture', catalog_id=None))
        assert model_runtime.resume_task(runtime.task_id)['status'] == 'queued'
        assert enqueued == [1]
        upload_tasks.update_state(runtime.task_id, status='reading', execution_generation=3)
        resumed = model_runtime.ModelRuntime(runtime.task_id, 3, tmp_path,
            runtime.read_state, runtime.write_state, runtime.lock, identity=runtime.identity)
        monkeypatch.setattr(resumed, 'wait', lambda _: resumed.check())
        with context(resumed):
            assert llm.complete_json('contract', 'completed checkpoint', response_schema=schema) == {'value': 42}
            assert llm.complete_json('contract', 'unfinished source', response_schema=schema) == {'value': 42}
        assert len(failed) == 10 and len(seen) == 11
        assert len(list(tmp_path.rglob('failure-*.json'))) == 9
        assert draft == {'paper': {'title': '保留的人工草稿'}}
        events = model_runtime.read_events(tmp_path)['events']
        requests = [event['attempt'] for event in events
                    if event['status'] == 'requesting' and event.get('attempt')
                    and event.get('started_at')]
        # 预备输入后会再次发布requesting；仅计算每轮第一次出现的尝试。
        attempts = [value for index, value in enumerate(requests)
                    if index == 0 or value != requests[index - 1]]
        assert attempts[-10:] == [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]


def test_worker_wrapper_settles_retry_limit_as_paused(task_runtime, tmp_path, monkeypatch):
    runtime, _, state, _, _, _ = task_runtime
    from backend.ingest import upload_jobs, document_run_metadata, document_shadow
    from backend.rag.llm_context import LlmConfig
    # Worker可能已被其他测试导入；显式绑定同一隔离存储，不依赖模块导入先后。
    monkeypatch.setattr(upload_jobs, 'get_state', upload_tasks.get_state)
    monkeypatch.setattr(upload_jobs, 'update_state', upload_tasks.update_state)
    monkeypatch.setattr(upload_jobs, 'load_llm_config', lambda _: LlmConfig(
        'fixture', 'https://model.invalid/v1', 'fixture', 'isolated'))
    monkeypatch.setattr(model_runtime, 'start_runtime', lambda _: runtime)
    monkeypatch.setattr(upload_jobs, 'artifact_directory', lambda _: tmp_path)
    monkeypatch.setattr(document_run_metadata, 'save_run_metadata', lambda *args, **kwargs: None)
    monkeypatch.setattr(document_shadow, 'refresh_comparison', lambda _: None)
    monkeypatch.setattr(upload_jobs, '_process_upload_task',
        lambda _: llm.complete_json('contract', 'unfinished source'))
    from backend.ingest import upload_resume
    monkeypatch.setattr(upload_resume, 'resume_spectra', lambda _: None)
    with model_server(monkeypatch, '503', failures=5) as (_, failed):
        result = upload_jobs.process_upload_task(runtime.task_id)
    assert len(failed) == 5
    assert result['status'] == state['status'] == 'paused'
    assert result['processing_status'] == 'paused'
    assert result['model_activity']['error']['request_id'] == 'fixture-request-id'
    assert result['model_activity']['retry_at'] is None


def test_parallel_activity_cannot_replace_last_failed_request(task_runtime, monkeypatch):
    runtime, context, state, _, _, _ = task_runtime
    event = runtime.event

    def interleaved(status, **fields):
        event(status, **fields)
        if status == 'paused':
            event('receiving', phase='other_parallel_request', filename='other.pdf',
                  attempt=1, pages=[9], error=None)

    monkeypatch.setattr(runtime, 'event', interleaved)
    with model_server(monkeypatch, '503', failures=5) as (_, failed):
        with context(runtime), llm.call_phase('structure_reading', filename='source.pdf', pages=[1]):
            with pytest.raises(model_runtime.ExecutionStopped):
                llm.complete_json('contract', 'unfinished source')
    assert len(failed) == 5
    activity = state['model_activity']
    assert activity['phase'] == 'structure_reading' and activity['filename'] == 'source.pdf'
    assert activity['pages'] == [1] and activity['attempt'] == 5
    assert activity['error']['request_id'] == 'fixture-request-id'


@pytest.mark.parametrize(('status', 'code'), [
    (429, 'insufficient_quota'), (503, 'credit_balance_too_low'),
    (429, 'billing_hard_limit_reached'), (401, 'invalid_api_key'),
    (403, 'permission_denied'), (400, 'invalid_request_error'),
])
def test_fixed_errors_stop_after_one_attempt(task_runtime, monkeypatch, status, code):
    runtime, context, state, _, persisted, _ = task_runtime
    calls = []

    def complete(*args, **kwargs):
        calls.append(1)
        raise APIStatusError('fixed failure', response=httpx.Response(status,
            request=httpx.Request('POST', 'https://model.invalid')), body={
                'error': {'code': code, 'message': '固定错误', 'retryable': True}})

    monkeypatch.setattr(llm, '_complete_json', complete)
    with context(runtime), pytest.raises(model_runtime.ModelRequestError):
        llm.complete_json('contract', 'source')
    assert calls == [1] and persisted == []
    assert state['model_activity']['status'] == 'blocked'
    assert state['model_activity']['error']['code'] == code
