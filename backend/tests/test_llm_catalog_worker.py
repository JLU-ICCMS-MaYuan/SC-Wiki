"""#116：隔离 Redis 与真实 RQ Worker 的编号模型快照验证。"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue, Worker

from backend.ingest import upload_jobs, upload_tasks
from backend.rag import llm_context
from backend.rag.llm_client import get_llm_client


def test_real_rq_worker_uses_snapshot_without_default_fallback(monkeypatch, tmp_path):
    url = os.environ.get("SCWIKI_TEST_REDIS_URL")
    if not url:
        pytest.skip("仅在显式指定的隔离 Redis 上执行")
    connection = Redis.from_url(url)
    observed = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            observed.append((self.headers["Authorization"], value["model"]))
            data = json.dumps({"id":"probe", "object":"chat.completion", "created":0, "model":value["model"],
                "choices":[{"index":0,"message":{"role":"assistant","content":"OK"},"finish_reason":"stop"}]}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self, *args):
            pass
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True); thread.start()
    queue = Queue("catalog-test-"+uuid4().hex, connection=connection)
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: connection)
    monkeypatch.setattr(llm_context.settings, "sc_wiki_data_dir", tmp_path)
    def process(task_id):
        config = llm_context.get_llm_config()
        result = get_llm_client().chat.completions.create(model=config.model, messages=[{"role":"user","content":"probe"}])
        return {"answer":result.choices[0].message.content}
    monkeypatch.setattr(upload_jobs, "_process_upload_task", process)
    monkeypatch.setattr(llm_context, "resolve_llm_config", lambda *a,**kw: (_ for _ in ()).throw(AssertionError("不允许回退默认")))
    tasks = []
    try:
        for n in (1, 3):
            task_id=uuid4().hex;tasks.append(task_id)
            config=llm_context.LlmConfig(f"server:LLM{n}",f"http://127.0.0.1:{upstream.server_port}/v1",f"model-{n}",f"test-key-{n}",False,f"LLM{n}",f"Model {n}")
            connection.set(upload_tasks.task_key(task_id),json.dumps({"task_id":task_id,"status":"queued","llm_provider":config.provider}))
            upload_tasks.save_llm_config(task_id,config)
            assert connection.ttl(upload_tasks.llm_config_key(task_id)) > 0
            queue.enqueue(upload_jobs.process_upload_task,task_id,job_timeout=30)
        Worker([queue],connection=connection).work(burst=True,with_scheduler=False)
        assert observed==[("Bearer test-key-1","model-1"),("Bearer test-key-3","model-3")]
        assert all(connection.get(upload_tasks.llm_config_key(task)) is None for task in tasks)
    finally:
        for task in tasks:connection.delete(upload_tasks.task_key(task),upload_tasks.llm_config_key(task))
        queue.delete(delete_jobs=True)
        upstream.shutdown();upstream.server_close();thread.join();connection.close()
