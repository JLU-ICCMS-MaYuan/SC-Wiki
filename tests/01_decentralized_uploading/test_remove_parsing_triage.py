"""#180：撤销派生分类，保留正式草稿存取与原始来源。"""
from copy import deepcopy
import json
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from backend import database, models
from backend.ingest import upload_tasks as tasks
from backend.ingest.upload_jobs import _normalize_draft
from test_upload_extraction_timing import MemoryRedis
from test_issue139_workflow import test_worker_finishes_direct_claim_gate_before_common_methods_fill as _run_worker


def test_worker_saves_without_entering_retired_classifier(tmp_path, monkeypatch):
    def retired(*args, **kwargs):
        raise AssertionError("正常 Worker 不应执行撤销的解析分类或专用 PDF 扫描")
    # 捕获运行调用，而不是搜索生产源码；仍执行真实 Worker 组装、审核与保存边界。
    monkeypatch.setitem(sys.modules, "backend.ingest.parsing_diagnostics", SimpleNamespace(
        annotate_differences=retired, read_pdf_regions=retired))
    _run_worker(tmp_path, monkeypatch)


@pytest.mark.parametrize("history", [False, True])
def test_original_ledger_survives_save_and_durable_restore(sqlite_engine, monkeypatch, history):
    sessions = sessionmaker(bind=sqlite_engine)
    client = MemoryRedis()
    # Redis 传输使用内存替身；关系库持久化和恢复实际执行，不接触用户数据。
    client.persist = lambda key: None
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(tasks, "redis_client", lambda: client)
    task_id = "180" + "a" * 29
    region = {"file_id": "main", "pdf_page": 1, "selected": "a",
              "selected_text": "Original source",
              "alternatives": [{"block_id": "b", "text": "Alternative source", "engine": "marker"}]}
    bibliography = {"field": "year", "grobid_value": 2021, "extracted_value": 2012}
    if history:
        region["triage"] = {"category": "symbol", "status": "system_pending", "legacy_extra": [1, 2]}
        bibliography["triage"] = {"status": "user_review"}
    raw = {"paper": {"title": "Historical draft", "year": 2012}, "material_states": [],
           "parsing_conflicts": [region], "bibliography_conflicts": [bibliography]}
    normalized = _normalize_draft(deepcopy(raw))
    assert normalized["parsing_conflicts"] == raw["parsing_conflicts"]
    assert normalized["bibliography_conflicts"] == raw["bibliography_conflicts"]
    state = {"task_id": task_id, "user_id": 7, "status": "ready"}
    client.set(tasks.task_key(task_id), json.dumps(state))
    with sessions.begin() as session:
        session.add(models.ScientificUploadDraft(task_id=task_id, owner_id=7, state=state, draft=raw))
    normalized["paper"]["title"] = "Edited title"
    saved = tasks.save_draft(task_id, normalized)
    assert tasks.get_draft(task_id) == saved
    client.values.clear()
    restored = tasks.get_draft(task_id)
    # 无核对结果的任务按既有规则仅保存 Redis；这里另验历史数据库快照恢复。
    assert restored["paper"]["title"] == "Historical draft"
    assert restored["parsing_conflicts"] == raw["parsing_conflicts"]
    assert restored["bibliography_conflicts"] == raw["bibliography_conflicts"]
