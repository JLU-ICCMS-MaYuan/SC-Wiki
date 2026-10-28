"""解析耗时的状态契约与真实任务存取入口。"""
import json
from copy import deepcopy

import pytest

from backend.ingest import upload_contracts as contracts


def fresh():
    return {"status": "uploading", "extraction_timing": contracts.new_extraction_timing()}


def move(state, now, status, **changes):
    return contracts.apply_state_changes(state, now=now, status=status, **changes)


def test_excludes_upload_queue_and_role_wait_then_freezes_at_ready():
    state = move(fresh(), 100, "queued")
    assert state["extraction_timing"]["started_at"] is None
    state = move(state, 200, "extracting")
    original = deepcopy(state)
    state = move(state, 230, "needs_role_review")
    assert original["extraction_timing"]["elapsed_seconds"] == 0
    assert state["extraction_timing"]["elapsed_seconds"] == 30
    state = move(state, 1000, "queued")
    state = move(state, 1100, "extracting")
    state = move(state, 1150, "reading")
    state = move(state, 1200, "summarizing")
    state = move(state, 1275, "ready")
    assert state["extraction_timing"] == {
        "started_at": 200, "running_since": None,
        "finished_at": 1275, "elapsed_seconds": 205,
    }
    fixed = deepcopy(state["extraction_timing"])
    state = contracts.apply_user_activity(state, now=3000)
    state = contracts.apply_state_changes(state, now=4000, progress={"done": 6})
    state = move(state, 5000, "submitted")
    assert state["extraction_timing"] == fixed


@pytest.mark.parametrize("terminal", ["failed", "cancelled", "duplicate", "ready"])
def test_terminal_updates_are_idempotent(terminal):
    state = move(fresh(), 100, "extracting")
    if terminal == "cancelled":
        state = move(state, 105, "cancelling")
    state = move(state, 110, terminal)
    assert state["extraction_timing"]["elapsed_seconds"] == 10
    assert move(state, 200, terminal)["extraction_timing"] == state["extraction_timing"]


def test_retry_resets_but_does_not_count_queue_time():
    state = move(move(fresh(), 100, "extracting"), 150, "failed")
    state = move(state, 300, "queued", retry=True)
    assert state["extraction_timing"] == contracts.new_extraction_timing()
    state = move(state, 500, "extracting")
    state = move(state, 507, "ready")
    assert state["extraction_timing"]["elapsed_seconds"] == 7
    assert state["extraction_timing"]["started_at"] == 500


def test_legacy_active_task_does_not_fabricate_start_but_retry_can_start_new_run():
    state = move({"status": "extracting", "created_at": 1}, 100, "reading")
    state = move(state, 200, "failed")
    assert "extraction_timing" not in state
    state = move(state, 300, "queued", retry=True)
    assert state["extraction_timing"] == contracts.new_extraction_timing()


def test_role_resume_enqueue_failure_preserves_paused_duration():
    state = move(move(fresh(), 100, "extracting"), 130, "needs_role_review")
    state = move(state, 200, "queued")
    state = move(state, 201, "needs_role_review")
    assert state["extraction_timing"]["elapsed_seconds"] == 30
    assert state["extraction_timing"]["running_since"] is None


def test_failure_before_worker_starts_has_no_fabricated_runtime():
    state = move(fresh(), 100, "failed")
    assert state["extraction_timing"]["started_at"] is None
    assert state["extraction_timing"]["elapsed_seconds"] == 0


def test_repeated_stage_updates_do_not_reset_start_or_count_twice():
    state = move(fresh(), 100, "extracting")
    state = move(state, 110, "extracting")
    state = contracts.apply_state_changes(state, now=120, completed_chunks=1)
    assert move(state, 130, "ready")["extraction_timing"]["elapsed_seconds"] == 30


class MemoryRedis:
    """仅替代外部Redis传输，保留生产create/update/get及序列化。"""
    def __init__(self):
        self.values = {}

    def pipeline(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def watch(self, *args):
        pass

    def multi(self):
        pass

    def execute(self):
        pass

    def zrange(self, *args):
        return []

    def zadd(self, *args):
        pass

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def setex(self, key, ttl, value):
        self.set(key, value)


def test_real_task_storage_and_public_dto_preserve_timing(monkeypatch):
    from backend.ingest import upload_tasks, scientific_evidence

    client = MemoryRedis()
    snapshots = []
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    monkeypatch.setattr(scientific_evidence, "persist_upload_state",
                        lambda task_id, state: snapshots.append(deepcopy(state)))
    monkeypatch.setattr(upload_tasks.time, "time", lambda: 100)
    created = upload_tasks.create_task(7, filename="paper.pdf", file_kind="pdf")
    task_id = created["task_id"]
    assert created["extraction_timing"] == contracts.new_extraction_timing()
    upload_tasks.update_state(task_id, status="extracting")
    monkeypatch.setattr(upload_tasks.time, "time", lambda: 305)
    upload_tasks.update_state(task_id, status="ready")
    restored = upload_tasks.get_state(task_id)
    public = contracts.public_task_state(restored)
    assert public["extraction_timing"]["elapsed_seconds"] == 205
    assert snapshots[-1]["extraction_timing"] == public["extraction_timing"]
    assert json.loads(client.values[upload_tasks.task_key(task_id)])["extraction_timing"] == public["extraction_timing"]
    assert "user_id" not in public


def test_persisted_draft_restores_fixed_timing_after_redis_loss(sqlite_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from backend import database, models
    from backend.ingest import upload_tasks, scientific_evidence

    sessions = sessionmaker(bind=sqlite_engine)
    client = MemoryRedis()
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
    task_id = "b" * 32
    state = {**move(fresh(), 100, "extracting"), "task_id": task_id, "user_id": 7}
    with sessions.begin() as session:
        session.add(models.ScientificUploadDraft(task_id=task_id, owner_id=7, state=state, draft={}))
    state = move(state, 305, "ready")
    scientific_evidence.persist_upload_state(task_id, state)
    restored = upload_tasks.get_state(task_id)
    assert restored["extraction_timing"]["elapsed_seconds"] == 205
    assert upload_tasks.get_state(task_id)["extraction_timing"] == restored["extraction_timing"]
