"""真实 HTTP/JWT、Redis/RQ 与关系库的上传/返修流程；仅固定外部模型结果。"""
import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from rq import SimpleWorker
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend import database, models
from backend.api import evidence, paper_revisions, rag, upload_tasks as task_api
from backend.ingest import upload_jobs, upload_tasks, property_evidence as ev, scientific_evidence as science
from backend.ingest.domain_extraction import DOMAIN_SYSTEM_PROMPT
from backend.ingest.form_definitions import definition_checksum
from backend.rag import database as async_db
from backend.rag.llm_context import LlmConfig
from backend.security import create_access_token
from backend.services.paper_revisions import revision_snapshot


ROOT = Path(__file__).resolve().parents[2]


def apply_method_migration(connection):
    spec = importlib.util.spec_from_file_location("methods114", ROOT / "alembic/versions/20260924_0114_tc_method_definitions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()
        module.upgrade()  # 不覆盖已有版本，并能重复校验。


@pytest.fixture(params=["mysql"])
def workflow(request, tmp_path, monkeypatch):
    if request.param == "mysql":
        url = os.environ.get("ISSUE114_WORKFLOW_MYSQL_URL")
        if not url:
            pytest.skip("需要隔离 #114 MySQL 工作流数据库")
        parsed = make_url(url)
        assert parsed.host in {"localhost", "127.0.0.1"} and parsed.database.startswith("test_issue114_")
    else:
        url = f"sqlite:///{tmp_path / 'workflow.db'}"
    engine = create_engine(url)
    async_url = url.replace("mysql+pymysql", "mysql+asyncmy").replace("sqlite:", "sqlite+aiosqlite:")
    async_engine = create_async_engine(async_url, poolclass=NullPool)
    if request.param == "sqlite":
        for current in (engine, async_engine.sync_engine):
            @event.listens_for(current, "connect")
            def enable_foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
    if request.param == "sqlite":
        database.Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)
    with factory.begin() as session:
        for seed in json.loads((ROOT / "backend/data/form_definitions.v1.json").read_text()):
            if not session.scalar(select(models.FormDefinition.id).where(models.FormDefinition.definition_key == seed["definition_key"], models.FormDefinition.version == 1)):
                session.add(models.FormDefinition(**seed, checksum=definition_checksum(seed)))
    with engine.begin() as connection:
        apply_method_migration(connection)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(upload_jobs, "SessionLocal", factory)
    monkeypatch.setattr(evidence, "SessionLocal", factory)
    monkeypatch.setattr(async_db, "async_session_factory", sessions)
    monkeypatch.setattr(upload_tasks.settings, "sc_wiki_data_dir", tmp_path)
    monkeypatch.setattr(upload_tasks, "get_llm_config", lambda: LlmConfig("openai", "https://api.openai.com/v1", "test-model", "test-only-key", True))
    monkeypatch.setattr(upload_jobs, "extract_references_from_pdf", lambda _: {"status":"unavailable", "references":[], "error_message":None})
    monkeypatch.setattr(upload_jobs, "extract_structure_candidates", lambda *a, **k: [])
    monkeypatch.setattr(ev, "generate_upload_suggestions", lambda *a, **k: None)
    with factory.begin() as session:
        import uuid
        suffix = uuid.uuid4().hex[:10]
        users = [models.User(email=f"{role}-{suffix}@example.test", username=f"{role}-{suffix}",
            real_name="验收", password_hash="unused", role=role, account_status="active", is_approved=True,
            is_email_verified=True, session_version=0) for role in ("user", "admin")]
        session.add_all(users); session.flush()
        owner, reviewer = users

    def complete(system, prompt, **kwargs):
        legacy_state = {"scope":"current_paper", "material":"LaH10", "state_kind":"experimental",
            "pressure_value_gpa":150, "evidence":{"page":1,"quote":"LaH10 Tc = 200 K at 150 GPa."},
            "tc_results":[{"tc_value_k":200,"result_kind":"experimental","tc_method":"unknown",
                           "evidence":{"page":1,"quote":"200 K"}}]}
        if system == upload_jobs.CHUNK_SYSTEM_PROMPT:
            return {"metadata":{"title":"Test hydride measurements"}, "material_states":[legacy_state]}
        if system == DOMAIN_SYSTEM_PROMPT:
            context = json.loads(prompt[prompt.index("{"):])
            states = []
            for page in context["pages"]:
                for block in page["blocks"]:
                    if "Tc =" not in block["text"]:
                        continue
                    pressure, tc = (150, 200) if "150 GPa" in block["text"] else (160, 220)
                    quote = {"file_id":context["file_id"], "pdf_page":block["pdf_page"],
                             "block_id":block["block_id"], "quote":block["text"].strip()}
                    states.append({"scope":"current_paper", "material":"LaH10", "state_kind":"experimental",
                        "pressure_value_gpa":pressure, "evidences":[quote], "property_modules":[{
                            "module_code":"superconductive_properties", "records":[{
                                "module_code":"superconductive_properties", "record_type":"measured_tc", "property_code":"tc",
                                "name_raw":"critical temperature", "value_kind":"number", "value_number":tc,
                                "value_raw":f"{tc} K", "unit_raw":"K", "canonical_unit":"K", "method_code":"unknown",
                                "payload":{"experimental_conditions":{}}, "evidences":[quote],
                            }]}]})
            return {"extraction_version":"1", "material_states":states}
        if system.startswith(upload_jobs.SUMMARY_SYSTEM_PROMPT):
            # 试图用错误汇总值覆盖科学记录；新链路必须保留分段的两个真实记录。
            return {"paper":{"title":"Test hydride measurements", "year":2026, "paper_type":"experimental",
                "material_families":[{"name":"Hydrides", "status":"pending"}]},
                "material_states":([{"material":"H", "tc_results":[{"tc_value_k":999}]}]
                    if "DOCUMENT IR PIPELINE" in system else [legacy_state])}
        return {"done":True}
    monkeypatch.setattr(upload_jobs, "complete_json", complete)
    app = FastAPI()
    @app.post("/api/rag/papers/{paper_id}/publish")
    def indexing_stub(paper_id: int):
        # 外部向量索引不属于此验收；批准事务和证据门禁执行真实生产代码。
        return {"ok":True}
    for router in (task_api.router, rag.router, evidence.router, paper_revisions.router):
        app.include_router(router)
    def db():
        with factory() as session: yield session
    app.dependency_overrides[database.get_db] = db
    tokens = {u.role:create_access_token({"sub":u.email, "sv":0}) for u in users}
    with tempfile.TemporaryDirectory(prefix="sc114-redis-") as directory:
        socket = Path(directory) / "redis.sock"
        binary = shutil.which("redis-server") or str(Path(os.sys.executable).parent / "redis-server")
        process = subprocess.Popen([binary, "--port", "0", "--unixsocket", str(socket), "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL)
        try:
            redis_url = f"unix://{socket}"
            connection = Redis.from_url(redis_url)
            for _ in range(100):
                try:
                    if connection.ping(): break
                except Exception: time.sleep(.05)
            assert connection.ping()
            monkeypatch.setattr(upload_tasks.settings, "redis_url", redis_url)
            with TestClient(app) as client:
                client.headers["Authorization"] = "Bearer " + tokens["user"]
                yield SimpleNamespace(client=client, factory=factory, sessions=sessions, owner=owner, reviewer=reviewer,
                    tokens=tokens, connection=connection, dialect=request.param, tmp_path=tmp_path, app=app)
        finally:
            process.terminate(); process.wait(timeout=10)
            engine.dispose()
            asyncio.run(async_engine.dispose())


def checked(w, snapshot, actor):
    """模型替身只提供真实来源；共享校验、缓存和提交门均执行正式代码。"""
    results = {}
    for record in snapshot["records"]:
        own = record.get("evidences") or []
        results[record["key"]] = {"status":"supported", "reason":"固定模型测试响应",
            "evidences": own or [{**snapshot["chunks"][0], "quote":"LaH10"}]}
    with w.factory.begin() as session:
        science.save_results(session, snapshot, results, actor)
    return snapshot["version"]


def review_in_go(w, paper_id, status, **extra):
    import socket
    import threading
    import uvicorn
    go = os.environ.get("SCWIKI_TEST_GO") or str(ROOT / ".local/go/bin/go")
    assert Path(go).is_file(), "跨语言验收需要 SCWIKI_TEST_GO"
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(w.app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets":[listener]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.05)
        assert server.started
        parsed = make_url(os.environ["ISSUE114_WORKFLOW_MYSQL_URL"])
        env = dict(os.environ, ISSUE114_REVIEW_PAPER=str(paper_id), ISSUE114_REVIEW_ADMIN=str(w.reviewer.id),
            ISSUE114_REVIEW_OWNER=str(w.owner.id), ISSUE114_REVIEW_STATUS=status,
            ISSUE114_MYSQL_DSN=f"root@unix({parsed.query['unix_socket']})/{parsed.database}?parseTime=true",
            PYTHON_BACKEND_URL=f"http://127.0.0.1:{port}",
            ISSUE114_REVIEW_BODY=json.dumps({"status":status,"comment":"隔离工作流验收", **extra}))
        handlers = ROOT / "goserver/handlers"
        production = sorted(path.name for path in handlers.glob("*.go") if not path.name.endswith("_test.go"))
        # 仅编译当前生产源码与此验收文件，不把并行开发的其他未完成测试混入。
        result = subprocess.run([go,"test",*production,"issue114_workflow_mysql_test.go",
                                 "-run","^TestIssue114DocumentReview$","-count=1"],
            cwd=handlers, env=env, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()


def upload(w, *, profile="text", run_worker=True):
    import pymupdf
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 80), "LaH10 Tc = 200 K at 150 GPa.")
        pdf.new_page().insert_text((50, 80), "LaH10 Tc = 220 K at 160 GPa.")
        data = pdf.tobytes()
    created = w.client.post("/api/upload-tasks", json={"parser_profile":profile, "files":[{
        "client_id":"main", "role":"main", "filename":"paper.pdf", "size":len(data), "media_type":"application/pdf"}]})
    assert created.status_code == 201, created.text
    task = created.json()["data"]; task_id = task["task_id"]; file_id = task["files"][0]["file_id"]
    response = w.client.put(f"/api/upload-tasks/{task_id}/files/{file_id}", files={"file":("paper.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    if not run_worker:
        return task_id, file_id
    queue = upload_tasks.upload_queue()
    worker = SimpleWorker([queue], connection=w.connection)
    worker.work(burst=True, logging_level="WARNING")
    state = upload_tasks.get_state(task_id)
    assert state["status"] == "ready", state
    if state["parser_profile"] != "legacy":
        assert state["reading_state"] == "coverage_checked"
    draft = w.client.get(f"/api/rag/upload-tasks/{task_id}/draft")
    assert draft.status_code == 200, draft.text
    draft = draft.json()["data"]
    expected_pressures = [150] if state["parser_profile"] == "legacy" else [150, 160]
    expected_values = [200] if state["parser_profile"] == "legacy" else [200, 220]
    assert [s["pressure_value_gpa"] for s in draft["material_states"]] == expected_pressures
    assert [s["property_modules"][0]["records"][0]["value_number"] for s in draft["material_states"]] == expected_values
    assert w.client.put(f"/api/rag/upload-tasks/{task_id}/draft", json=draft).status_code == 200
    return task_id, file_id


def test_http_rq_submit_region_and_current_revision(workflow):
    w = workflow
    task_id, file_id = upload(w)
    region = w.client.post("/api/rag/evidence/region", json={"target":"upload", "target_id":task_id,
        "file_id":file_id, "pdf_page":1, "quote":"200 K"})
    assert region.status_code == 200 and region.json()["status"] == "located", region.text
    endpoint = f"/api/rag/upload-tasks/{task_id}/submit"
    assert w.client.post(endpoint).status_code == 409  # 尚未核对不能提交。
    version = checked(w, ev.upload_snapshot(task_id, w.owner.id), w.owner.id)
    submitted = w.client.post(endpoint, json={"expected_evidence_version":version})
    assert submitted.status_code == 200, submitted.text
    paper_id = submitted.json()["paper_id"]
    assert w.client.post(endpoint).json()["paper_id"] == paper_id  # 重复请求幂等。
    with w.factory() as session:
        records = list(session.scalars(select(models.PropertyRecord).where(models.PropertyRecord.paper_id == paper_id)))
        assert len(records) == 2 and {float(r.value_number) for r in records} == {200, 220}
        assert all(r.method_code == "unknown" for r in records)
        assert session.get(models.Paper, paper_id).review_status == "pending"
        locators = list(session.scalars(select(models.PaperEvidenceLocator).where(models.PaperEvidenceLocator.paper_id == paper_id)))
        assert len(locators) >= 2
        formal_file = str(locators[0].paper_file_id)
    w.client.headers["Authorization"] = "Bearer " + w.tokens["admin"]
    with w.factory() as session:
        snapshot = ev.paper_snapshot(session, paper_id, w.reviewer.id, "admin")
    version = checked(w, snapshot, w.reviewer.id)
    prepared = w.client.post("/api/rag/evidence/prepare-review", json={"paper_id":paper_id, "expected_version":version})
    assert prepared.status_code == 200, prepared.text
    review_in_go(w, paper_id, "rejected")
    w.client.headers["Authorization"] = "Bearer " + w.tokens["user"]
    base = f"/api/rag/papers/{paper_id}/revision-draft"
    opened = w.client.post(base)
    assert opened.status_code == 200, opened.text
    opened = opened.json()
    draft = copy.deepcopy(opened["data"])
    draft["paper"]["title"] = "Revised hydride measurements"
    # 既有返修流程要求重新选择尚未进入正式目录的候选家族。
    draft["paper"]["material_families"] = [{"name":"Hydrides", "status":"pending"}]
    draft["material_states"][0]["property_modules"][0]["records"][0]["evidences"][0]["quote"] = "200 K at 150 GPa."
    saved = w.client.put(base, json={"revision_id":opened["revision_id"], "draft_version":opened["draft_version"], "draft":draft})
    assert saved.status_code == 200, saved.text
    saved = saved.json()
    with w.factory() as session:
        snapshot = revision_snapshot(session, saved["revision_id"], w.owner.id)
    version = checked(w, snapshot, w.owner.id)
    revised = w.client.post(base + "/submit", json={"revision_id":saved["revision_id"],
        "draft_version":saved["draft_version"], "expected_evidence_version":version})
    assert revised.status_code == 200, revised.text
    assert revised.json()["content_revision"] == 2
    with w.factory() as session:
        for model in (models.PaperDocumentParserRun, models.PaperDocumentBlock, models.PaperEvidenceLocator, models.PropertyRecord):
            rows = list(session.scalars(select(model).where(model.paper_id == paper_id)))
            assert rows and all(row.paper_revision == 2 for row in rows)
        assert session.scalar(select(models.PaperEvidenceLocator.id).where(
            models.PaperEvidenceLocator.paper_id == paper_id,
            models.PaperEvidenceLocator.quote == "200 K at 150 GPa."))
    response = w.client.post("/api/rag/evidence/region", json={"target":"paper", "target_id":str(paper_id),
        "file_id":formal_file, "pdf_page":1, "quote":"200 K"})
    assert response.status_code == 200 and response.json()["status"] == "located", response.text
    # 管理员先保存完整分类再核对，批准接口不捎带未经核对的新分类。
    from backend.services.paper_revisions import current_draft
    w.client.headers["Authorization"] = "Bearer " + w.tokens["admin"]
    with w.factory() as session:
        draft = current_draft(session, session.get(models.Paper, paper_id))
    changed = w.client.put(f"/api/rag/papers/{paper_id}/scientific-draft", json={
        "paper_type":"experimental", "superconductor_kind":"unknown",
        "material_families":[{"name":"Hydrides", "status":"pending"}],
        "material_states":draft["material_states"]})
    assert changed.status_code == 200, changed.text
    with w.factory() as session:
        snapshot = ev.paper_snapshot(session, paper_id, w.reviewer.id, "admin")
        families = list(session.scalars(select(models.MaterialFamily).join(models.PaperMaterialFamily,
            models.PaperMaterialFamily.material_family_id == models.MaterialFamily.id).where(models.PaperMaterialFamily.paper_id == paper_id)))
        states = list(session.scalars(select(models.MaterialState).where(models.MaterialState.paper_id == paper_id)))
        classifications = {"superconductor_kind":"unknown", "material_families":[{"id":f.id, "name":f.name_zh} for f in families],
            "material_states":[{"id":s.id,"material_dimensionality":s.material_dimensionality,"structure_families":[]} for s in states]}
    version = checked(w, snapshot, w.reviewer.id)
    review_in_go(w, paper_id, "approved", expected_evidence_version=version, **classifications)
    with w.factory() as session:
        paper = session.get(models.Paper, paper_id)
        assert paper.review_status == "approved" and paper.approved_revision == paper.content_revision == 2


@pytest.mark.parametrize("profile, expected", [("text", "ready"), ("vision", "failed")])
def test_shadow_isolated_queue_never_writes_or_changes_user_draft(workflow, monkeypatch, profile, expected):
    w = workflow
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_stage", "shadow")
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_default_profile", profile)
    writes = []
    engine = w.factory.kw["bind"]
    def record_sql(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].lower() in {"insert", "update", "delete"}:
            writes.append(statement)
    event.listen(engine, "before_cursor_execute", record_sql)
    try:
        task_id, file_id = upload(w, profile=None)
    finally:
        event.remove(engine, "before_cursor_execute", record_sql)
    assert not writes
    parent = upload_tasks.get_state(task_id)
    shadow_id = parent["shadow_task_id"]
    shadow = upload_tasks.get_state(shadow_id)
    assert parent["status"] == "ready" and parent["parser_profile"] == "legacy"
    assert parent["shadow_status"] == shadow["status"] == expected
    assert shadow["is_shadow"] and shadow["parser_profile"] == profile
    assert [t["task_id"] for t in upload_tasks.list_user_tasks(w.owner.id)] == [task_id]
    for endpoint in (f"/api/upload-tasks/{shadow_id}", f"/api/rag/upload-tasks/{shadow_id}/draft"):
        assert w.client.get(endpoint).status_code == 404
    assert w.client.post(f"/api/rag/upload-tasks/{shadow_id}/submit").status_code == 404
    with pytest.raises(Exception) as error:
        ev.upload_snapshot(shadow_id, w.owner.id)
    assert error.value.status_code == 403
    comparison = json.loads((upload_tasks.artifact_directory(task_id) / "shadow-comparison.json").read_text())
    assert comparison["legacy_records"] == 1
    assert comparison["new_records"] == (2 if expected == "ready" else 0)
    if expected == "failed":
        assert comparison["runs"]["new"]["error_code"] == "parser_profile_unavailable"
    parent_file = Path(parent["files"][0]["stored_path"])
    shadow_file = Path(shadow["files"][0]["stored_path"])
    assert parent_file != shadow_file and parent_file.read_bytes() == shadow_file.read_bytes()
    before = parent_file.read_bytes()
    shadow_file.write_bytes(b"independent test snapshot")
    assert parent_file.read_bytes() == before


def test_cancelled_parent_stops_shadow_before_parsing(workflow, monkeypatch):
    w = workflow
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_stage", "shadow")
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_default_profile", "text")
    task_id, _ = upload(w, profile=None, run_worker=False)
    shadow_id = upload_tasks.get_state(task_id)["shadow_task_id"]
    response = w.client.post(f"/api/upload-tasks/{task_id}/cancel")
    assert response.status_code == 202
    SimpleWorker([upload_tasks.upload_queue()], connection=w.connection).work(burst=True, logging_level="WARNING")
    assert upload_tasks.get_state(shadow_id)["status"] == "cancelled"
    assert not upload_tasks.artifact_path(shadow_id).exists()


def test_benchmark_driver_runs_real_upload_and_exports_actual_ir(workflow):
    import hashlib
    import pymupdf
    from backend.ingest.pdf_benchmark import Corpus
    from backend.ingest.pdf_benchmark_runner import run_corpus
    w = workflow
    path = w.tmp_path / "benchmark.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 80), "LaH10 Tc = 200 K at 150 GPa.")
        pdf.new_page().insert_text((50, 80), "LaH10 Tc = 220 K at 160 GPa.")
        pdf.save(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    corpus = Corpus.model_validate({"schema_version":"1", "kind":"synthetic", "papers":[{
        "paper_id":"synthetic-1", "main_sha256":digest, "source_sha256s":[digest],
        "categories":["digital", "multi_pressure", "english"], "annotator":"test-only", "reviewed_on":"2026-09-24",
        "records":[{"record_id":"r1", "fields":{"material":"LaH10","tc_k":200}, "conditions":{"pressure_gpa":150},
            "evidences":[{"file_sha256":digest,"pdf_page":1,"bbox":[.1,.1,.5,.2],"quote":"200 K"}]}]}]})
    progress = []
    def run_worker(_):
        SimpleWorker([upload_tasks.upload_queue()], connection=w.connection).work(burst=True, logging_level="WARNING")
    result = run_corpus(w.client, corpus, {"synthetic-1":[{"path":str(path), "role":"main"}]},
        profile="text", artifact_root=w.tmp_path / "review_artifacts", sleep=run_worker, on_progress=progress.append)
    assert len(progress) == 1 and len(result.papers[0].records) == 2
    assert result.pipeline_revision.startswith("sha256:") and result.model == "test-model"
    assert [r.fields["value_number"] for r in result.papers[0].records] == [200, 220]
    assert [r.conditions["pressure_value_gpa"] for r in result.papers[0].records] == [150, 160]
    assert [r.evidences[0].pdf_page for r in result.papers[0].records] == [1, 2]
    assert all(r.evidences[0].file_sha256 == digest for r in result.papers[0].records)
    assert result.papers[0].resources.latency_seconds > 0
    with w.factory() as session:
        assert not session.scalar(select(models.Paper.id).where(models.Paper.uploaded_by_user_id == w.owner.id))


def test_invalid_domain_json_converges_and_real_queue_retry_succeeds(workflow, monkeypatch):
    w = workflow
    original = upload_jobs.complete_json
    monkeypatch.setattr(upload_jobs, "complete_json", lambda system, prompt, **kwargs:
        {"material_states":[]} if system == DOMAIN_SYSTEM_PROMPT else original(system, prompt, **kwargs))
    task_id, _ = upload(w, run_worker=False)
    worker = SimpleWorker([upload_tasks.upload_queue()], connection=w.connection)
    worker.work(burst=True, logging_level="CRITICAL")
    state = upload_tasks.get_state(task_id)
    assert state["status"] == "failed" and state["error_code"] == "domain_invalid_output"
    assert upload_tasks.get_draft(task_id) is None
    monkeypatch.setattr(upload_jobs, "complete_json", original)
    assert w.client.post(f"/api/upload-tasks/{task_id}/retry").status_code == 202
    worker.work(burst=True, logging_level="WARNING")
    assert upload_tasks.get_state(task_id)["status"] == "ready"


def test_submit_ir_hash_failure_rolls_back_paper_and_task(workflow):
    w = workflow
    task_id, file_id = upload(w)
    version = checked(w, ev.upload_snapshot(task_id, w.owner.id), w.owner.id)
    path = upload_tasks.artifact_directory(task_id) / "document_ir" / f"{file_id}.json"
    tables = (models.Paper, models.PaperFile, models.PaperDocumentParserRun, models.PaperDocumentBlock, models.PaperEvidenceLocator)
    with w.factory() as session:
        counts = [session.scalar(select(func.count()).select_from(table)) for table in tables]
    original = path.read_text()
    changed = json.loads(original); changed["source_sha256"] = "f"*64
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="哈希"):
        w.client.post(f"/api/rag/upload-tasks/{task_id}/submit", json={"expected_evidence_version":version})
    assert upload_tasks.get_state(task_id)["status"] == "ready"
    with w.factory() as session:
        assert not session.scalar(select(models.Paper.id).where(models.Paper.upload_task_id == task_id))
        assert [session.scalar(select(func.count()).select_from(table)) for table in tables] == counts
    path.write_text(original)
    response = w.client.post(f"/api/rag/upload-tasks/{task_id}/submit", json={"expected_evidence_version":version})
    assert response.status_code == 200, response.text


def test_shadow_import_failure_callback_cleans_credentials_and_converges(workflow, monkeypatch):
    from rq import Queue
    from rq.job import Callback
    from backend.ingest.document_shadow import shadow_failure
    w = workflow
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_stage", "shadow")
    monkeypatch.setattr(upload_tasks.settings, "upload_parser_default_profile", "text")
    task_id, _ = upload(w, profile=None, run_worker=False)
    shadow_id = upload_tasks.get_state(task_id)["shadow_task_id"]
    shadow = upload_tasks.get_state(shadow_id)
    upload_tasks.upload_queue().remove(shadow["job_id"])
    queue = Queue("issue114-entry-failure", connection=w.connection)
    job = queue.enqueue("issue114_missing_worker_module.process", shadow_id, on_failure=Callback(shadow_failure))
    SimpleWorker([queue], connection=w.connection).work(burst=True, logging_level="CRITICAL")
    assert str(job.get_status(refresh=True)).endswith("FAILED")
    assert upload_tasks.get_state(shadow_id)["error_code"] == "upload_worker_execution_failed"
    assert upload_tasks.get_state(task_id)["status"] == "queued"
    assert upload_tasks.get_state(task_id)["shadow_status"] == "failed"
    assert not w.connection.exists(upload_tasks.llm_config_key(shadow_id))
