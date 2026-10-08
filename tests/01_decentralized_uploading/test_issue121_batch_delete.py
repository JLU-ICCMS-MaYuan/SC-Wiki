"""Issue #121：上传解析记录批量删除接口与公共删除函数。"""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from backend.api import upload_tasks as api
from backend.ingest import upload_tasks
from backend.main import app


def _state(task_id: str, status: str, user_id: int = 7, job_id: str | None = None) -> dict:
    return {
        "task_id": task_id,
        "user_id": user_id,
        "status": status,
        "updated_at": 100,
        "existing_paper_id": None,
        "state_schema_version": 1,
        **({"job_id": job_id} if job_id else {}),
    }


def _patch_cleanup_primitives(monkeypatch, events: list) -> None:
    monkeypatch.setattr(
        upload_tasks,
        "cleanup_transient_data",
        lambda task_id, **kwargs: events.append(("transient", task_id, kwargs)),
    )
    monkeypatch.setattr(
        upload_tasks,
        "cleanup_unsubmitted_files",
        lambda task_id: events.append(("files", task_id)),
    )
    monkeypatch.setattr(
        upload_tasks,
        "cleanup_duplicate_candidate",
        lambda task_id, paper_id: events.append(("candidate", task_id, paper_id)),
    )
    import backend.ingest.scientific_evidence as evidence
    monkeypatch.setattr(
        evidence,
        "delete_target",
        lambda session, target, target_id: events.append(("evidence", target_id)),
    )
    monkeypatch.setattr(upload_tasks, "upload_task_lock", lambda _task_id: nullcontext())
    import backend.database as database
    monkeypatch.setattr(
        database, "SessionLocal",
        SimpleNamespace(begin=lambda: nullcontext(SimpleNamespace())),
    )


def test_batch_delete_route_is_registered():
    schema = app.openapi()
    operations = schema["paths"].get("/api/upload-tasks/batch-delete", {})
    assert "post" in operations


def test_delete_task_record_full_cleanup_for_terminal_task(monkeypatch):
    task_id = "a" * 32
    state = _state(task_id, "failed")
    monkeypatch.setattr(upload_tasks, "get_state", lambda _task_id: state)
    monkeypatch.setattr(upload_tasks, "submitted_paper_id", lambda _task_id: None)
    monkeypatch.setattr(
        upload_tasks, "update_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("终态任务无需更新状态")),
    )
    monkeypatch.setattr(
        upload_tasks, "_delete_processing_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("终态任务无作业可终止")),
    )
    events: list = []
    _patch_cleanup_primitives(monkeypatch, events)

    upload_tasks.delete_task_record(task_id)

    assert events[0] == (
        "transient", task_id,
        {"context": upload_tasks.CleanupContext.from_state(task_id, state), "preserve_review_snapshot": False},
    )
    assert ("files", task_id) in events
    assert ("candidate", task_id, None) in events
    assert ("evidence", task_id) in events


def test_delete_task_record_cancels_running_job_before_cleanup(monkeypatch):
    task_id = "b" * 32
    state = _state(task_id, "extracting", job_id="rq-job")
    deleted_jobs: list[str] = []
    state_changes: list[dict] = []
    monkeypatch.setattr(upload_tasks, "get_state", lambda _task_id: state)
    monkeypatch.setattr(upload_tasks, "_delete_processing_job", deleted_jobs.append)

    def fake_update_state(_task_id, **changes):
        state_changes.append(changes)
        state.update(changes, status="cancelled")
        return state

    monkeypatch.setattr(upload_tasks, "update_state", fake_update_state)
    monkeypatch.setattr(upload_tasks, "submitted_paper_id", lambda _task_id: None)
    events: list = []
    _patch_cleanup_primitives(monkeypatch, events)

    upload_tasks.delete_task_record(task_id)

    assert deleted_jobs == ["rq-job"]
    assert state_changes and state_changes[0]["status"] == "cancelled"
    assert ("files", task_id) in events
    assert ("evidence", task_id) in events


def test_delete_task_record_preserves_paper_and_snapshot_for_submitted_task(monkeypatch):
    task_id = "c" * 32
    state = _state(task_id, "submitted")
    monkeypatch.setattr(upload_tasks, "get_state", lambda _task_id: state)
    monkeypatch.setattr(upload_tasks, "submitted_paper_id", lambda _task_id: 88)
    monkeypatch.setattr(
        upload_tasks, "_delete_processing_job",
        lambda *_args: (_ for _ in ()).throw(AssertionError("已提交任务无作业可终止")),
    )
    events: list = []
    _patch_cleanup_primitives(monkeypatch, events)

    upload_tasks.delete_task_record(task_id)

    assert events == [(
        "transient", task_id,
        {"context": upload_tasks.CleanupContext.from_state(task_id, state), "preserve_review_snapshot": True},
    )]


def test_batch_delete_reports_per_task_results(monkeypatch):
    owner = SimpleNamespace(id=7, role="user", is_approved=True)
    good_id, locked_id, foreign_id = "a" * 32, "b" * 32, "c" * 32

    def fake_owned(task_id, _user):
        if task_id == foreign_id:
            raise api._error(404, "UPLOAD_TASK_NOT_FOUND", "上传任务不存在或已过期")

    monkeypatch.setattr(api, "_owned_state", fake_owned)

    def fake_delete(task_id):
        if task_id == locked_id:
            raise TimeoutError("上传任务正由其他请求处理")
        if task_id == "bad":
            raise RuntimeError("boom")

    monkeypatch.setattr(upload_tasks, "delete_task_record", fake_delete)

    result = api.batch_delete_upload_tasks(
        api.BatchDeleteUploadTasks(task_ids=[good_id, locked_id, foreign_id, "bad"]),
        owner,
    )

    assert result["ok"] is True
    assert [item["task_id"] for item in result["deleted"]] == [good_id]
    failed = {item["task_id"]: item["reason"] for item in result["failed"]}
    assert locked_id in failed and "请稍后重试" in failed[locked_id]
    assert foreign_id in failed and "不存在" in failed[foreign_id]
    assert "bad" in failed and "boom" in failed["bad"]


def test_batch_delete_deduplicates_task_ids(monkeypatch):
    owner = SimpleNamespace(id=7, role="user", is_approved=True)
    calls: list[str] = []
    monkeypatch.setattr(api, "_owned_state", lambda _task_id, _user: None)
    monkeypatch.setattr(
        upload_tasks, "delete_task_record", lambda task_id: calls.append(task_id),
    )

    result = api.batch_delete_upload_tasks(
        api.BatchDeleteUploadTasks(task_ids=["a" * 32, "a" * 32]),
        owner,
    )

    assert calls == ["a" * 32]
    assert len(result["deleted"]) == 1


def test_batch_delete_rejects_empty_and_oversized_batches():
    owner = SimpleNamespace(id=7, role="user", is_approved=True)
    with pytest.raises(ValueError):
        api.BatchDeleteUploadTasks(task_ids=[])
    with pytest.raises(ValueError):
        api.BatchDeleteUploadTasks(task_ids=["a" * 32] * 101)


def test_single_delete_still_rejects_running_and_persisted_tasks(monkeypatch):
    owner = SimpleNamespace(id=7, role="user", is_approved=True)
    task_id = "d" * 32
    monkeypatch.setattr(api, "_owned_state", lambda _t, _u: _state(task_id, "ready"))

    with pytest.raises(api.HTTPException) as clearable:
        api.delete_upload_task(task_id, owner)
    assert clearable.value.status_code == 409
    assert clearable.value.detail["code"] == "UPLOAD_TASK_NOT_CLEARABLE"

    monkeypatch.setattr(api, "_owned_state", lambda _t, _u: _state(task_id, "failed"))
    monkeypatch.setattr(upload_tasks, "submitted_paper_id", lambda _task_id: 88)
    with pytest.raises(api.HTTPException) as persisted:
        api.delete_upload_task(task_id, owner)
    assert persisted.value.status_code == 409
    assert persisted.value.detail["code"] == "UPLOAD_TASK_PERSISTED"
