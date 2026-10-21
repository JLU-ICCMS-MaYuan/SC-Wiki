"""待确认文件角色必须按任务版本和原来源继续解析。"""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import upload_tasks as api
from backend.ingest import upload_tasks as storage
from backend.ingest.document_roles import assess_roles


def _waiting_task(tmp_path):
    task_id = "a" * 32
    root = tmp_path / "parsed_markdown" / task_id
    root.mkdir(parents=True)
    texts = {"a": "## First paper title with enough words\nAbstract\nResults and Discussion\n",
             "b": "## Second paper title with enough words\nAbstract\nResults and Discussion\n"}
    files = [{"file_id": file_id, "role": "attachment", "kind": "pdf",
              "original_filename": f"{file_id}.pdf", "sha256": file_id} for file_id in texts]
    for file_id, text in texts.items():
        (root / f"{file_id}.md").write_text(text, encoding="utf-8")
    state = {"task_id": task_id, "user_id": 7, "status": "needs_role_review",
             "revision": 4, "files": files, "role_assessment": assess_roles(files, texts)}
    return state


def test_confirmation_requires_current_revision_and_resumes_cached_text(tmp_path, monkeypatch):
    state = _waiting_task(tmp_path)
    submitted = []

    monkeypatch.setattr(api, "_owned_state", lambda *_: state)
    monkeypatch.setattr(storage, "get_state", lambda *_: state)
    monkeypatch.setattr(storage, "data_path", lambda *_: tmp_path / "parsed_markdown")
    monkeypatch.setattr(storage, "upload_task_lock", lambda *_: nullcontext())
    monkeypatch.setattr(storage, "load_llm_config", lambda *_: object())
    monkeypatch.setattr(storage, "enqueue_processing", lambda task_id, **kwargs: submitted.append((task_id, kwargs)))

    def update(_, **changes):
        state.update(changes)
        state["revision"] += 1
        return state

    monkeypatch.setattr(storage, "update_state", update)
    user = SimpleNamespace(id=7, role="user", is_approved=True)
    roles = [api.RoleDecision(file_id="a", role="main"), api.RoleDecision(file_id="b", role="attachment")]
    with pytest.raises(HTTPException) as stale:
        api.resolve_upload_roles(state["task_id"], api.ResolveRoles(expected_revision=3, roles=roles), user)
    assert stale.value.status_code == 409

    response = api.resolve_upload_roles(state["task_id"], api.ResolveRoles(expected_revision=4, roles=roles), user)
    assert json.loads(response.body)["data"]["status"] == "queued"
    assert state["role_assessment"]["status"] == "user_confirmed"
    assert submitted == [(state["task_id"], {"preserve_llm_config": True})]
