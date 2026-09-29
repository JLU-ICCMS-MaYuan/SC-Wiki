"""Issue #73: upload-worker LLM credentials are isolated and short lived."""

import pytest

from backend.ingest import upload_jobs, upload_tasks
from backend.rag import llm_context


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.deleted = []

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)
        return len(keys)


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "cancelled"])
def test_upload_llm_config_has_ttl_and_worker_cleans_it(monkeypatch, outcome):
    monkeypatch.setattr(llm_context.socket, "getaddrinfo", lambda *args, **kwargs: [
        (None, None, None, None, ("93.184.216.34", 443))])
    task_id = "a" * 32
    config = llm_context.LlmConfig(
        "kimi", "https://api.moonshot.cn/v1", "moonshot-v1-8k", "user-key", True,
    )
    redis = FakeRedis()
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: redis)
    monkeypatch.setattr(upload_tasks.settings, "upload_task_ttl_seconds", 3600)

    upload_tasks.save_llm_config(task_id, config)
    key = upload_tasks.llm_config_key(task_id)
    assert redis.ttls[key] == 3600
    assert upload_tasks.load_llm_config(task_id) == config

    observed = []
    monkeypatch.setattr(upload_jobs, "load_llm_config", upload_tasks.load_llm_config)
    monkeypatch.setattr(upload_jobs, "delete_llm_config", upload_tasks.delete_llm_config)
    def process(_task_id):
        observed.append(llm_context.get_llm_config())
        if outcome != "succeeded":
            raise RuntimeError(outcome)
        return {"status": outcome}

    monkeypatch.setattr(upload_jobs, "_process_upload_task", process)

    if outcome == "succeeded":
        assert upload_jobs.process_upload_task(task_id) == {"status": outcome}
    else:
        with pytest.raises(RuntimeError, match=outcome):
            upload_jobs.process_upload_task(task_id)
    assert observed == [config]
    assert key in redis.deleted
    assert key not in redis.values


def test_transient_cleanup_deletes_upload_llm_config(monkeypatch):
    task_id = "b" * 32
    redis = FakeRedis()
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: redis)
    monkeypatch.setattr(upload_tasks, "_delete_processing_job", lambda _job_id: None)
    monkeypatch.setattr(upload_tasks, "get_state", lambda _: None)

    upload_tasks.cleanup_transient_data(task_id)

    assert upload_tasks.llm_config_key(task_id) in redis.deleted


def test_server_catalog_snapshot_preserves_source_and_survives_catalog_changes(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: redis)
    monkeypatch.setattr(llm_context.socket, "getaddrinfo", lambda *args, **kwargs: [
        (None, None, None, None, ("93.184.216.34", 443))])
    config = llm_context.LlmConfig("server:LLM3", "https://example.com/v1", "original", "test-key", False, "LLM3", "模型三")
    upload_tasks.save_llm_config("c" * 32, config)
    monkeypatch.setattr(llm_context, "resolve_llm_config", lambda: (_ for _ in ()).throw(AssertionError("不得读取当前默认")))
    assert upload_tasks.load_llm_config("c" * 32) == config


def test_missing_server_snapshot_fails_task_instead_of_changing_model(monkeypatch):
    changes = []
    monkeypatch.setattr(upload_jobs, "load_llm_config", lambda _: None)
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: {"llm_provider": "server:LLM3"})
    monkeypatch.setattr(upload_jobs, "update_state", lambda _, **kw: changes.append(kw))
    monkeypatch.setattr(upload_jobs, "delete_llm_config", lambda _: None)
    monkeypatch.setattr(upload_jobs, "_schedule_terminal_cleanup", lambda _: None)
    with pytest.raises(RuntimeError, match="配置已失效"):
        upload_jobs.process_upload_task("d" * 32)
    assert changes[0]["status"] == "failed"
    assert changes[0]["error_code"] == "llm_task_config_expired"


@pytest.mark.parametrize("status", ["completed", "submitted", "cancelled", "failed", "duplicate"])
def test_replayed_terminal_catalog_task_keeps_its_result(monkeypatch, status):
    state = {"status": status, "llm_provider": "server:LLM3"}
    monkeypatch.setattr(upload_jobs, "load_llm_config", lambda _: None)
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: state)
    monkeypatch.setattr(upload_jobs, "update_state", lambda *a, **kw: pytest.fail("不能覆盖终态"))
    assert upload_jobs.process_upload_task("e" * 32) == state


def test_expired_snapshot_does_not_override_requested_cancellation(monkeypatch):
    state = {"status": "cancelling", "llm_provider": "server:LLM3"}
    monkeypatch.setattr(upload_jobs, "load_llm_config", lambda _: None)
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: state)
    monkeypatch.setattr(upload_jobs, "update_state", lambda _, **kw: {**state, **kw})
    monkeypatch.setattr(upload_jobs, "_schedule_terminal_cleanup", lambda _: None)
    assert upload_jobs.process_upload_task("f" * 32)["status"] == "cancelled"
