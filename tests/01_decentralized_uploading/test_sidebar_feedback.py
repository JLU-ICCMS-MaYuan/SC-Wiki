"""#221：真实工具阶段、公开进度投影与候选措辞。"""
import json
import pytest
from test_evidence_progress import progress_redis
from backend.ingest import property_evidence as ev


def snapshot():
    row = {"key": "graph", "item_key": "graph", "field": "paper.knowledge_graph_title",
           "label": "图谱科学标题", "kind": "field", "current_value": "High temperature superconductivity in calcium hydride",
           "claim": {"value": "High temperature superconductivity in calcium hydride"}, "required": True, "evidences": []}
    chunks = [{"file_id": "paper-file", "chunk_index": 0, "page_start": 1,
               "content": "Calcium hydride CaH6 is predicted to superconduct at high temperatures."}]
    return ev.complete_snapshot("upload", "isolated221", [row], chunks, {})


def test_actual_tool_actions_and_public_summary_are_reported():
    from backend.ingest.model_review import review_fields
    snap = snapshot()
    events = []
    calls = []
    def model(_, payload, **kwargs):
        data = json.loads(payload)
        calls.append(data)
        if len(calls) == 1:
            return {"action": {"name": "read_page", "arguments": {"file_id": "paper-file", "page": 1}},
                    "progress_summary": "核实该标题是否忠实概括本文的CaH6预测。"}
        return {"results": [{"key": "graph", "status": "supported", "reason": "原文支持CaH6高温超导预测这一概括。",
                              "source_ids": [data["sources"][0]["source_id"]], "basis_kind": "paper_synthesis"}]}
    result = review_fields(snap["records"], snap["chunks"], model=model, on_activity=events.append)
    assert result["graph"]["status"] == "supported"
    assert len(calls) == 2
    assert any(e["stage"] == "tool" and e.get("tool") == "read_page" for e in events)
    assert any(e.get("summary") == "核实该标题是否忠实概括本文的CaH6预测。" for e in events)
    assert events[-1]["stage"] == "result"
    assert all("prompt" not in e and "reasoning_content" not in e for e in events)


def test_small_progress_projection_filters_private_fields_and_bounds_history():
    job = {"id": "job", "owner": 7, "status": "running",
           "activity": {"stage": "model", "message": "核对当前字段", "summary": "公开摘要",
                        "reasoning_content": "不能作为公开进度", "api_key": "private"},
           "activity_log": [{"stage": "tool", "message": str(i)} for i in range(30)],
           "snapshot": {"target": "revision", "target_id": "field", "records": [{"huge": "payload"}]}}
    result = ev.job_control(job)
    assert result["activity"]["summary"] == "公开摘要"
    assert "api_key" not in result["activity"] and "reasoning_content" not in result["activity"]
    assert len(result["activity_log"]) <= 12
    assert "records" not in result["snapshot"]


def test_captured_false_mutation_claim_is_a_proposal_and_does_not_change_value():
    from backend.ingest.model_review import review_fields
    snap = snapshot()
    original = snap["records"][0]["current_value"]
    def model(_, payload, **kwargs):
        data = json.loads(payload)
        return {"results": [{"key": "graph", "status": "supported", "unique": True,
             "reason": "已据原文将图谱科学标题更正为论文实际题名。",
             "final_value": "Superconductive sodalite-like clathrate calcium hydride at high pressures",
             "source_ids": [data["sources"][0]["source_id"]], "basis_kind": "paper_quote"}]}
    result = review_fields(snap["records"], snap["chunks"], model=model)["graph"]
    assert snap["records"][0]["current_value"] == original
    assert result["proposal"]
    assert "已据原文将" not in result["reason"]
    assert "建议" in result["reason"]


def test_activity_uses_only_live_owned_small_projection(tmp_path, monkeypatch):
    import subprocess
    import sys
    import tempfile
    import time
    from pathlib import Path
    from redis import Redis
    from backend.ingest import upload_tasks, review_progress
    with tempfile.TemporaryDirectory(prefix="ev221-", dir="/tmp") as directory:
        socket = directory + "/redis.sock"
        server = subprocess.Popen([str(Path(sys.executable).parent / "redis-server"),
            "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client = Redis(unix_socket_path=socket, decode_responses=True)
        try:
            for _ in range(100):
                try:
                    if client.ping(): break
                except Exception: time.sleep(.02)
            assert client.ping()
            monkeypatch.setattr(upload_tasks, "redis_client", lambda: client)
            key = ev.job_control_key("isolated221")
            # 故意没有完整任务快照；进度的读写完全不依赖它。
            client.set(key, json.dumps({"owner": 7, "status": "running"}))
            for i in range(20):
                review_progress.update_activity("isolated221", 7, {"stage": "tool", "message": str(i),
                    "summary": "可公开", "reasoning_content": "不能公开", "api_key": "不能公开"})
            value = json.loads(client.get(key))
            assert len(value["activity_log"]) == 12
            assert value["activity_log"][0]["message"] == "8"
            assert "reasoning_content" not in value["activity"] and "api_key" not in value["activity"]
            assert client.dbsize() == 1
            before = client.get(key)
            review_progress.update_activity("isolated221", 8, {"message": "另一个用户"})
            assert client.get(key) == before
            for status in ("completed", "cancelled", "failed"):
                client.set(key, json.dumps({**value, "status": status}))
                before = client.get(key)
                review_progress.update_activity("isolated221", 7, {"message": "迟到事件"})
                assert client.get(key) == before
        finally:
            client.close(); server.terminate(); server.wait(timeout=5)


def test_streamed_public_summary_is_visible_before_model_finishes_without_extra_call():
    from backend.ingest.model_review import review_fields
    snap = snapshot()
    events, calls = [], []
    def model(_, payload, **kwargs):
        calls.append(payload)
        # 公开摘要只有完整JSON字符串后才可展示；隐藏推理不会转发。
        kwargs["on_partial"]('{"progress_summary":"核实')
        assert not any(e.get("summary") for e in events)
        kwargs["on_partial"]('{"progress_summary":"核实材料与压力范围", "results":[')
        assert events[-1]["summary"] == "核实材料与压力范围"
        assert not any(e["stage"] == "result" for e in events)
        source = json.loads(payload)["sources"][0]["source_id"]
        return {"results": [{"key": "graph", "status": "supported", "reason": "正文支持当前概括",
                             "source_ids": [source], "basis_kind": "paper_synthesis"}]}
    result = review_fields(snap["records"], snap["chunks"], model=model, on_activity=events.append)
    assert result["graph"]["status"] == "supported"
    assert len(calls) == 1


@pytest.mark.parametrize("outcome", ["supported", "unsupported", "cancelled"])
def test_field_worker_reports_real_progress_and_preserves_persisted_result(sqlite_engine, progress_redis, monkeypatch, outcome):
    from copy import deepcopy
    from contextlib import contextmanager
    from types import SimpleNamespace
    from sqlalchemy.orm import sessionmaker
    from backend import database, manual_evidence_models, workdraft_models
    from backend.rag import llm
    from backend.ingest import upload_tasks, scientific_evidence as science
    snap = snapshot()
    database.Base.metadata.create_all(sqlite_engine)
    factory = sessionmaker(sqlite_engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: progress_redis)
    monkeypatch.setattr(upload_tasks, "load_llm_config", lambda _: SimpleNamespace(model="isolated221"))
    monkeypatch.setattr(upload_tasks, "delete_llm_config", lambda _: None)
    @contextmanager
    def lock(_): yield
    monkeypatch.setattr(upload_tasks, "upload_task_lock", lock)
    monkeypatch.setattr(ev, "upload_snapshot", lambda *args, **kwargs: deepcopy(snap))
    observed = []
    def model(_, payload, **kwargs):
        kwargs["on_partial"]('{"progress_summary":"正在核实CaH6原文"}')
        small = ev.read_job_status("22100000000000000000000000000000", 7)
        observed.append(small)
        assert small["activity"]["summary"] == "正在核实CaH6原文"
        assert "records" not in small["snapshot"]
        if outcome == "cancelled": ev.update_job("22100000000000000000000000000000", status="cancelled")
        request = json.loads(payload)
        return {"results": [{"key": "graph", "status": "supported" if outcome=="cancelled" else outcome,
            "reason": "正文支持当前概括" if outcome=="supported" else "当前概括超出正文范围",
            "source_ids": [request["sources"][0]["source_id"]], "basis_kind": "paper_synthesis"}]}
    monkeypatch.setattr(llm, "complete_json", model)
    job = {"id": "22100000000000000000000000000000", "owner": 7, "status": "queued", "snapshot": snap,
           "cached": {}, "purpose": "field", "review_started_at": "2026-11-05T00:00:00+00:00"}
    progress_redis.set(ev.task_key("22100000000000000000000000000000"), json.dumps(job))
    ev.write_job_control(job)
    ev.run_evidence_job("22100000000000000000000000000000")
    finished = ev.read_job("22100000000000000000000000000000", 7)
    assert observed
    with factory() as session: loaded = science.load_results(session, snap, 7)
    if outcome == "cancelled":
        assert finished["status"] == "cancelled"
        assert not loaded
    else:
        assert finished["status"] == "completed"
        assert loaded["graph"]["status"] == outcome
        assert not loaded["graph"].get("human_confirmed")
