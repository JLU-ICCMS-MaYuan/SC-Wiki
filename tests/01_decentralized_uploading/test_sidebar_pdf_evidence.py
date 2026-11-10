"""#221：长补充PDF必须进入真实统一核对与worker读取状态链。"""
from copy import deepcopy
from contextlib import contextmanager
from types import SimpleNamespace
import json
import pymupdf
import pytest
from sqlalchemy.orm import sessionmaker
from backend import database, models, manual_evidence_models, workdraft_models
from backend.ingest import manual_evidence as manual, property_evidence as ev
from test_sidebar_feedback import snapshot
from test_evidence_progress import progress_redis


def pdf_bytes(lines):
    with pymupdf.open() as pdf:
        for offset in range(0, lines, 100):
            page = pdf.new_page()
            page.insert_text((20, 20), "\n".join(["Evidence for CaH6. " + "x" * 62] * min(100, lines-offset)), fontsize=5)
        raw = pdf.tobytes()
        content = "\n".join(p.get_text("text").strip() for p in pdf)
    return raw, content


@pytest.fixture
def context(sqlite_engine, tmp_path, monkeypatch):
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    database.Base.metadata.create_all(sqlite_engine)
    factory = sessionmaker(sqlite_engine)
    current = snapshot()
    before = deepcopy(current)
    before["records"][0].update(current_value="Old", content_hash="old")
    with factory.begin() as session:
        manual.save_explanation(session, current, before, "graph", 7,
            reason="综述支持当前科学概括", no_evidence_reason="", text_items=[])
    return factory, current, before


@pytest.mark.parametrize("lines,expected", [(400, True), (1200, True), (1300, False)])
def test_pdf_character_limit_and_full_content(context, lines, expected):
    factory, current, before = context
    raw, content = pdf_bytes(lines)
    assert len(content) > 20_000
    assert (len(content) <= 100_000) == expected
    with factory.begin() as session:
        saved = manual.add_file(session, current, before, "graph", 7, filename="long.pdf", raw=raw, source_description="")
        entry = manual.review_context(session, current)["graph"]
        if expected:
            assert entry["items"][0]["content"] == content
            assert len(entry["pdf_refs"]) == 1
        else:
            assert entry["items"][0]["read_status"] == "not_read"
            assert "content" not in entry["items"][0]
            assert len(entry["pdf_refs"])==1 and entry["pdf_refs"][0]["readable"] is False  # 明确未读回执，不能冒充已读。
        assert saved["items"][0]["ai_read_status"] == "not_read"
    assert manual.MAX_TEXT_CHARS == 100_000  # #226：直接长文字与PDF采用相同正文边界。
    assert manual.MAX_REVIEW_PDF_TEXT_CHARS == 100_000


@pytest.mark.parametrize("lines", [20, 400])
@pytest.mark.parametrize("outcome", ["supported", "unsupported", "failure", "cancelled"])
def test_real_worker_pdf_and_text_input_read_receipt(context, progress_redis, monkeypatch, outcome, lines):
    factory, snap, before = context
    raw, content = pdf_bytes(lines)
    with factory.begin() as session:
        saved = manual.add_file(session, snap, before, "graph", 7, filename="review.pdf", raw=raw, source_description="")
        pdf_id = saved["items"][0]["id"]
        manual.add_file(session, snap, before, "graph", 7, filename="note.txt", raw=b"Independent text evidence", source_description="")
    with factory() as session:
        from backend.ingest.field_review import bind_support_versions
        bind_support_versions(snap, session)
    monkeypatch.setattr(database, "SessionLocal", factory)
    from backend.ingest import upload_tasks
    from backend.rag import llm
    monkeypatch.setattr(upload_tasks, "redis_client", lambda: progress_redis)
    monkeypatch.setattr(upload_tasks, "load_llm_config", lambda _: SimpleNamespace(model="isolated-pdf221"))
    monkeypatch.setattr(upload_tasks, "delete_llm_config", lambda _: None)
    @contextmanager
    def lock(_): yield
    monkeypatch.setattr(upload_tasks, "upload_task_lock", lock)
    monkeypatch.setattr(ev, "upload_snapshot", lambda *a, **k: deepcopy(snap))
    job_id = "22100000000000000000000000000099"
    calls = []
    def model(_, payload, **kwargs):
        request = json.loads(payload); calls.append(request)
        materials = request["human_provided_evidence"]["graph"]["items"]
        assert materials[0]["content"] == content
        assert materials[1]["content"] == "Independent text evidence"
        if outcome == "failure": raise TimeoutError("固定模型失败")
        if outcome == "cancelled": ev.update_job(job_id, status="cancelled")
        return {"results": [{"key": "graph", "status": "unsupported" if outcome=="unsupported" else "supported",
            "reason": "已结合原文及补充综述核实", "source_ids": [request["sources"][0]["source_id"]],
            "supplemental_evidences": [{"sha256": materials[0]["sha256"], "quote": "Evidence for CaH6."}],
            "basis_kind": "paper_synthesis"}]}
    monkeypatch.setattr(llm, "complete_json", model)
    job = {"id": job_id, "owner": 7, "status": "queued", "snapshot": snap, "cached": {},
           "purpose": "field", "review_started_at": "2026-11-05T08:00:00+00:00"}
    progress_redis.set(ev.task_key(job_id), json.dumps(job)); ev.write_job_control(job)
    ev.run_evidence_job(job_id)
    assert calls
    with factory() as session:
        row = session.get(manual.ScientificManualEvidence, saved["id"])
        item = next(i for i in row.items if i["id"]==pdf_id)
        assert item["ai_read_status"] == ("read" if outcome in {"supported", "unsupported"} else "not_read")
        if outcome in {"supported", "unsupported"}:
            from backend.ingest.scientific_evidence import load_results
            result = load_results(session, snap, 7)["graph"]
            assert result["status"] == outcome
            assert result["supplemental_evidences"][0]["sha256"] == row.items[0]["sha256"]
            assert not result.get("human_confirmed")
        if outcome == "cancelled":
            assert ev.read_job(job_id, 7)["status"] == "cancelled"


def test_read_receipt_is_idempotent_and_keeps_field_input_version(context):
    factory, current, before = context
    raw, _ = pdf_bytes(20)
    with factory.begin() as session:
        saved = manual.add_file(session, current, before, "graph", 7, filename="review.pdf", raw=raw, source_description="")
        from backend.ingest.field_input import bind
        bind(current, session)
        token = current["records"][0]["field_input_token"]
        refs = [{"row_id": saved["id"], "item_id": saved["items"][0]["id"]}]
        manual.mark_ai_read(session, refs, read=True)
        row = session.get(manual.ScientificManualEvidence, saved["id"])
        version = row.evidence_version
        manual.mark_ai_read(session, refs, read=True)
        assert row.evidence_version == version
        bind(current, session)
        assert current["records"][0]["field_input_token"] == token
