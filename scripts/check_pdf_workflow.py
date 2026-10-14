"""隔离 MySQL/Redis 中执行真实上传入口、RQ、四工具与模型；不连接业务写库。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import dotenv_values
from sqlalchemy import create_engine, text, select
from sqlalchemy.engine import make_url


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--pdf", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--resume", action="store_true", help="复用已归档任务和解析制品，保留重试记录")
    cli.add_argument("--review-theoretical-subtype", choices=("calculation", "method", "theory"),
                     help="隔离案例的显式人工校对；只补缺失类型，记录原摘要和理由，不改科学值")
    args = cli.parse_args()
    values = dotenv_values(".env")
    live = make_url(values["DATABASE_URL"])
    if live.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("验收只允许本机 MySQL")
    saved = json.loads((args.output / "summary.json").read_text()) if args.resume else None
    name = saved["database"] if saved else "test_issue136_" + uuid4().hex[:12]
    assert name.startswith("test_issue136_") and name.replace("_", "").isalnum()
    admin_url = live.set(username="root", password=values.get("MYSQL_ROOT_PASSWORD"), database=None) if values.get("MYSQL_ROOT_PASSWORD") else live.set(database=None)
    admin = create_engine(admin_url)
    if not saved:
        with admin.begin() as connection:
            connection.execute(text(f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    url = admin_url.set(database=name).render_as_string(hide_password=False)
    if not saved:
        args.output.mkdir(parents=True, exist_ok=False)
    root = args.output.resolve()
    from scripts.complementary_pdf_demo.run import snapshot
    execution = root / "executions" / uuid4().hex
    execution.mkdir(parents=True)
    (execution / "baseline.json").write_text(json.dumps(snapshot(execution), indent=2), encoding="utf-8")
    os.environ.update({k:v for k,v in values.items() if v is not None and k not in os.environ})
    os.environ.update(DATABASE_URL=url, RAG_DATABASE_URL=url.replace("mysql+pymysql", "mysql+asyncmy"),
                      SC_WIKI_DATA_DIR=str(root / "data"), FILE_STORAGE_BACKEND="local")
    from backend import database, models
    from backend.ingest import upload_tasks, upload_jobs
    from backend.rag import database as async_database
    from backend.rag.llm_context import get_llm_config
    from backend.api import upload_tasks as task_api, rag, evidence
    from backend.security import create_access_token
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from redis import Redis
    from rq import SimpleWorker
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    async_database.async_session_factory = async_sessionmaker(
        create_async_engine(url.replace("mysql+pymysql", "mysql+asyncmy"), poolclass=NullPool), expire_on_commit=False)

    # 使用实际迁移后的 DDL，避免 ORM 默认值与 MySQL 版本不一致。
    live_engine = create_engine(live)
    with live_engine.connect() as source, database.engine.begin() as target:
        target.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        for table in ([] if saved else source.exec_driver_sql("SHOW TABLES").scalars().all()):
            if table == "alembic_version":
                continue
            quoted = "`" + table.replace("`", "``") + "`"
            ddl = source.exec_driver_sql("SHOW CREATE TABLE " + quoted).first()[1]
            target.exec_driver_sql(ddl)
        target.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    # 仅克隆公开表单/分类目录，业务论文、账号和科学记录不复制。
    from sqlalchemy.orm import Session
    with Session(live_engine) as source, database.SessionLocal.begin() as target:
        for model in (() if saved else (models.FormDefinition, models.MaterialFamily, models.StructureFamily)):
            for row in source.scalars(select(model)):
                fields = {column.name:getattr(row,column.name) for column in model.__table__.columns}
                for column in model.__table__.columns:
                    if column.nullable and any(fk.column.table.name == "users" for fk in column.foreign_keys):
                        fields[column.name] = None
                target.add(model(**fields))
        user = target.scalar(select(models.User).where(models.User.email == f"{name}@example.test")) if saved else models.User(email=f"{name}@example.test", username=name, real_name="四工具验收",
                           password_hash="test-unused", role="user", account_status="active", is_approved=True,
                           is_email_verified=True, session_version=0)
        target.add(user)
        target.flush()
        user_id, user_email = user.id, user.email
    socket_directory = tempfile.TemporaryDirectory(prefix="scwiki136-", dir="/tmp")
    socket = Path(socket_directory.name) / "redis.sock"
    binary = shutil.which("redis-server") or str(Path(os.sys.executable).parent / "redis-server")
    redis_process = subprocess.Popen([binary,"--port","0","--unixsocket",str(socket),"--save","","--appendonly","no"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        connection = Redis.from_url(f"unix://{socket}")
        for _ in range(100):
            try:
                if connection.ping():break
            except Exception:time.sleep(.1)
        assert connection.ping()
        upload_tasks.settings.redis_url = f"unix://{socket}"
        upload_tasks.settings.upload_stale_seconds = 7200
        app = FastAPI()
        for router in (task_api.router, rag.router, evidence.router):app.include_router(router)
        client = TestClient(app)
        client.headers["Authorization"] = "Bearer " + create_access_token({"sub":user_email,"sv":0})
        def save(name, value):
            (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        if saved:
            task = json.loads((root / "state.json").read_text())
            connection.set(upload_tasks.task_key(task["task_id"]), json.dumps(task))
            upload_tasks.save_llm_config(task["task_id"], get_llm_config())
            if (root / "draft.json").exists():
                connection.set(upload_tasks.draft_key(task["task_id"]), (root / "draft.json").read_text())
        else:
            response = client.post("/api/upload-tasks",json={"files":[{"client_id":"main", "filename":args.pdf.name,"size":args.pdf.stat().st_size,"role":"main"}]})
            assert response.status_code==201,response.text
            task = response.json()["data"]
            assert task["parser_profile"]=="complementary"
            with args.pdf.open("rb") as stream:
                response=client.put(f"/api/upload-tasks/{task['task_id']}/files/{task['files'][0]['file_id']}",files={"file":(args.pdf.name,stream,"application/pdf")})
            assert response.status_code in {200,202},response.text
        print("TEST_DATABASE",name,"TASK",task["task_id"],flush=True)
        if saved and task["status"] == "failed":
            history = root / "attempts" / uuid4().hex
            history.mkdir(parents=True)
            for filename in ("state.json", "summary.json", "draft.json"):
                if (root / filename).exists():
                    shutil.copy2(root / filename, history / filename)
            response = client.post(f"/api/upload-tasks/{task['task_id']}/retry")
            assert response.status_code in {200, 202}, response.text
        worker=SimpleWorker([upload_tasks.upload_queue()],connection=connection)
        worker.work(burst=True,logging_level="WARNING")
        state=upload_tasks.get_state(task["task_id"])
        if state["status"] == "needs_role_review":
            save("role-review.json", state)
            response = client.post(f"/api/upload-tasks/{task['task_id']}/resolve-roles", json={
                "expected_revision": state["revision"], "roles": [{"file_id": item["file_id"], "role": item["declared_role"]} for item in state["files"]]})
            assert response.status_code in {200, 202}, response.text
            worker.work(burst=True, logging_level="WARNING")
            state = upload_tasks.get_state(task["task_id"])
        save("state.json",state)
        draft=upload_tasks.get_draft(task["task_id"])
        if draft:save("draft.json",draft)
        save("summary.json",{"database":name,"task_id":task["task_id"],"status":state["status"],
                             "profile":state["parser_profile"],"model":get_llm_config().model})
        assert state["status"]=="ready",state.get("processing_error")
        response=client.get(f"/api/rag/upload-tasks/{task['task_id']}/draft")
        assert response.status_code==200,response.text
        draft = response.json()["data"]
        save("canonical-draft.json", draft)
        response=client.put(f"/api/rag/upload-tasks/{task['task_id']}/draft",json=draft)
        assert response.status_code==200,response.text
        for key in ("bibliography_sources", "bibliography_conflicts", "parsing_conflicts"):
            assert response.json()["data"].get(key) == draft.get(key), key
        print("READY_AND_SAVE_ROUNDTRIP",flush=True)
        if args.review_theoretical_subtype and draft["paper"].get("paper_type") == "theoretical" and not draft["paper"].get("theoretical_subtype"):
            original_abstract = (draft.get("citation_extraction") or {}).get("metadata", {}).get("abstract")
            assert original_abstract, "人工测试分类需要原始摘要依据"
            draft["paper"]["theoretical_subtype"] = args.review_theoretical_subtype
            response = client.put(f"/api/rag/upload-tasks/{task['task_id']}/draft", json=draft)
            assert response.status_code == 200, response.text
            current = client.post("/api/rag/evidence/preflight", json={"target":"upload", "target_id":task["task_id"]}).json()
            record = next(r for r in current["records"] if r["field"] == "paper.theoretical_subtype")
            review = {"expected_version":current["version"], "reason":f"隔离案例的显式人工校对：依据原始正文摘要所描述的本文贡献，确认理论二级类型为 {args.review_theoretical_subtype}；不修改任何科学记录。",
                      "text_items":[{"text":original_abstract, "source_description":"当前上传正文的 GROBID 原始摘要，非模型总结"}]}
            response = client.put(f"/api/rag/evidence/upload/{task['task_id']}/manual/{record['item_key']}", json=review)
            save("manual-classification.json", {"value":args.review_theoretical_subtype, "evidence":review, "response":response.json()})
            assert response.status_code == 200, response.text
        preflight = client.post("/api/rag/evidence/preflight", json={"target":"upload", "target_id":task["task_id"]})
        assert preflight.status_code == 200, preflight.text
        check = preflight.json()
        save("preflight.json", check)
        if check["needs_check"]:
            response = client.post("/api/rag/evidence/jobs", json={"target":"upload", "target_id":task["task_id"], "expected_version":check["version"]})
            assert response.status_code == 200, response.text
            job = response.json()
            worker.work(burst=True, logging_level="WARNING")
            result = client.get(f"/api/rag/evidence/jobs/{job['id']}")
            save("evidence-job.json", result.json())
            assert result.status_code == 200 and result.json()["status"] == "completed", result.text
        response = client.post(f"/api/rag/upload-tasks/{task['task_id']}/submit", json={"expected_evidence_version":check["version"]})
        save("submission.json", response.json())
        assert response.status_code == 200, response.text
        paper_id = response.json()["paper_id"]
        with database.SessionLocal() as session:
            from backend.ingest.document_ir import DocumentIR
            runs = list(session.scalars(select(models.PaperDocumentParserRun).where(models.PaperDocumentParserRun.paper_id == paper_id)))
            assert runs and all(run.parse_profile == "complementary" for run in runs)
            for run in runs:
                document = DocumentIR.model_validate(run.document_json)
                assert document.source_file_id == str(run.paper_file_id)
                assert document.coverage["grobid"]["file_id"] == str(run.paper_file_id)
                assert document.coverage["component_runs"] and document.coverage["routing"]
            locators = list(session.scalars(select(models.PaperEvidenceLocator).where(models.PaperEvidenceLocator.paper_id == paper_id)))
            assert locators and all(row.parser_name == "complementary" for row in locators)
            references = list(session.scalars(select(models.PaperReference).where(models.PaperReference.paper_id == paper_id)))
            records = list(session.scalars(select(models.PropertyRecord).where(models.PropertyRecord.paper_id == paper_id)))
            assert records and references
            assert session.get(models.Paper, paper_id).review_status == "pending"
            save("persistence.json", {"paper_id":paper_id, "parser_runs":len(runs), "locators":len(locators),
                "references":len(references), "records":len(records), "review_status":"pending"})
        print("SUBMITTED_MYSQL_SOURCE_ROUNDTRIP", flush=True)
    finally:
        redis_process.terminate();redis_process.wait(timeout=10)
        socket_directory.cleanup()
        admin.dispose();live_engine.dispose();database.engine.dispose()


if __name__ == "__main__":main()
