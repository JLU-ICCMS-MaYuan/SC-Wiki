"""人工证据从对象存储读取，不依赖 API 与 Worker 共享目录。"""

from __future__ import annotations

import io
import json
import asyncio
from contextlib import nullcontext
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ingest import manual_evidence as manual
from backend.manual_evidence_models import ScientificManualEvidence
from backend.storage import FileRef, create_storage


def _snapshot(value: str) -> dict:
    return {"target": "upload", "target_id": "task", "records": [{
        "key": "field", "item_key": "stable-field", "field": "paper.authors",
        "content_hash": value, "source_hash": "source", "current_value": value,
    }]}


def test_manual_evidence_roundtrip_without_shared_directory(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path))
        monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path / "unmounted"))
        engine = create_engine("sqlite:///:memory:")
        ScientificManualEvidence.__table__.create(engine)
        try:
            with Session(engine) as session:
                old, current = _snapshot("old"), _snapshot("new")
                manual.save_explanation(session, current, old, "stable-field", 7,
                                        reason="按来源修正", no_evidence_reason="", text_items=[])
                image = io.BytesIO()
                Image.new("RGB", (4, 4), "white").save(image, format="PNG")
                saved = manual.add_file(session, current, old, "stable-field", 7,
                                        filename="source.png", raw=image.getvalue(), source_description="图示")
                row = session.get(ScientificManualEvidence, saved["id"])
                item = row.items[0]
                assert item["storage_key"].startswith("manual_evidence/")
                assert not (tmp_path / "unmounted").exists()
                _, _, temporary = manual.file_entry(session, current, "stable-field", item["id"])
                assert temporary.read_bytes() == image.getvalue()
                temporary.unlink()
                removed = manual.remove_file(session, current, "stable-field", item["id"], 7)
                assert isinstance(removed, FileRef)
                create_storage().delete(removed)
                assert boto3.client("s3", region_name="us-east-1").list_objects_v2(
                    Bucket="scwiki-storage-test").get("KeyCount", 0) == 0
        finally:
            engine.dispose()


def test_canonical_upload_publishes_object_key_before_queue(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    redis_binary = Path(sys.executable).with_name("redis-server")
    if not redis_binary.is_file():
        pytest.skip("隔离 Redis 服务不可用")
    socket = Path("/tmp") / f"scwiki-{uuid4().hex}.sock"
    process = subprocess.Popen([str(redis_binary), "--port", "0", "--unixsocket", str(socket),
                                "--unixsocketperm", "700", "--save", "", "--appendonly", "no"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        redis = Redis(unix_socket_path=str(socket), decode_responses=True,
                      socket_connect_timeout=0.2, socket_timeout=0.2)
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("隔离 Redis 启动失败")
            if not socket.exists():
                time.sleep(0.02)
                continue
            try:
                if redis.ping():
                    break
            except Exception:
                time.sleep(0.02)
        else:
            pytest.fail("隔离 Redis 未启动")
        from backend.api import upload_tasks as api
        from backend.ingest import scientific_evidence, upload_tasks as tasks
        from backend.rag.llm_context import request_llm_config
        from backend.security import get_current_user

        monkeypatch.setattr(tasks, "redis_client", lambda: redis)
        monkeypatch.setattr(tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path,
                                                                  upload_parser_stage="legacy"))
        monkeypatch.setattr(scientific_evidence, "persist_upload_state", lambda *_: None)
        monkeypatch.setattr(tasks, "enqueue_processing", lambda *_: "queued")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
        with moto.mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
            app = FastAPI()
            app.include_router(api.router)
            app.dependency_overrides[request_llm_config] = lambda: None
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="user", is_approved=True)
            client = TestClient(app)
            created = client.post("/api/upload-tasks", json={"files": [{"client_id": "main", "role": "main",
                "filename": "paper.pdf", "size": 3}], "parser_profile": "legacy"})
            assert created.status_code == 201, created.text
            task_id = created.json()["data"]["task_id"]
            file_id = created.json()["data"]["files"][0]["file_id"]
            response = client.put(f"/api/upload-tasks/{task_id}/files/{file_id}",
                                  files={"file": ("paper.pdf", b"PDF", "application/pdf")})
            assert response.status_code == 200, response.text
            state = tasks.get_state(task_id)
            key = state["file_path"]
            assert key.startswith(f"upload_PDFs/{task_id}/{file_id}/") and key.endswith(".pdf")
            assert state["files"][0]["stored_path"] == key
            assert not (tmp_path / key).exists()
            assert boto3.client("s3", region_name="us-east-1").get_object(
                Bucket="scwiki-storage-test", Key=key)["Body"].read() == b"PDF"
            assert "file_path" not in response.json()["data"]
            from backend.ingest.upload_jobs import _original_path
            from backend.storage.paths import clear_namespace

            localized = _original_path(state)
            assert localized.read_bytes() == b"PDF"
            assert localized != tmp_path / key
            clear_namespace(task_id)
            assert not localized.exists()
    finally:
        process.terminate()
        process.wait(timeout=5)
        socket.unlink(missing_ok=True)


def test_duplicate_candidate_survives_without_worker_directory(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from backend.api import rag
    from backend.ingest import upload_jobs, upload_tasks
    from backend.storage import create_storage

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
        monkeypatch.setattr(upload_tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
        monkeypatch.setattr(upload_jobs, "update_state", lambda _task, **changes: changes)
        monkeypatch.setattr(upload_jobs, "_schedule_terminal_cleanup", lambda _task: None)
        monkeypatch.setattr(upload_jobs, "upload_task_lock", lambda _task: nullcontext())
        monkeypatch.setattr(upload_jobs, "get_state", lambda _task: None)
        task_id = "a" * 32
        key = f"upload_PDFs/{task_id}/source.pdf"
        ref = create_storage().put(key, io.BytesIO(b"new PDF"), "application/pdf")
        state = {"task_id": task_id, "user_id": 7, "file_path": key,
                 "file_size": ref.size, "file_sha256": ref.sha256, "filename": "source.pdf"}
        existing = SimpleNamespace(id=42, doi="10.1/example", review_status="approved",
                                   uploaded_by_user_id=7, main_sha256="b" * 64)
        result = upload_jobs._handle_duplicate(task_id, state, existing)
        assert result["duplicate_file_action"] == "candidate_saved"
        candidates = rag._candidate_attachments(42)
        assert candidates[0]["file_sha256"] == ref.sha256
        found = rag._candidate_attachment_path(42, task_id)
        assert found is not None and found[0].read_bytes() == b"new PDF"
        upload_tasks.cleanup_duplicate_candidate(task_id, 42)
        assert rag._candidate_attachments(42) == []


def test_pdf_evidence_reads_remote_source_without_business_mount(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from backend.ingest.pdf_front_matter import _main_file
    from backend.ingest.pdf_source_pages import _files
    from backend.storage import create_storage

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
        ref = create_storage().put("upload_PDFs/task/main.pdf", io.BytesIO(b"PDF source"), "application/pdf")
        snapshot = {"target_id": "task", "pdf_manifest": [{"file_id": "main", "role": "main",
            "kind": "pdf", "stored_path": ref.key, "size": ref.size, "sha256": ref.sha256,
            "media_type": ref.media_type}]}
        resolved = list(_files(None, snapshot))
        assert len(resolved) == 1 and resolved[0][1].read_bytes() == b"PDF source"
        assert _main_file(None, snapshot)[0].read_bytes() == b"PDF source"
        assert not (tmp_path / "upload_PDFs").exists()


def test_submitted_review_snapshot_survives_state_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from backend.api import rag
    from backend.ingest import upload_tasks
    from backend.storage.paths import publish_tree

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
        monkeypatch.setattr(upload_tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
        task_id = "d" * 32
        source = upload_tasks.artifact_path(task_id)
        source.write_text(json.dumps({"task_id": task_id, "paper_id": None,
                                      "ai_values": {"paper": {"summary": "old"}}, "evidence": {}}))
        state = {"status": "ready", "file_contract_version": 1,
                 "artifact_manifest": publish_tree(source, data_root=tmp_path, task_id=task_id, run_id="first")}
        original_key = state["artifact_manifest"][0]["key"]
        source.unlink()
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: state)
        monkeypatch.setattr(upload_tasks, "update_state", lambda _task, **changes: state.update(changes) or state)
        rag._record_submitted_upload(task_id, 42, {"paper": {"summary": "reviewed"}})
        assert state["artifact_manifest"][0]["key"] != original_key
        assert state["artifact_manifest"][0]["key"] == f"review_artifacts/{task_id}/result.json"
        found = rag._artifact_by_paper_id(42, task_id)
        assert found is not None and found[2]["user_values"]["paper"]["summary"] == "reviewed"
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: None)
        source.unlink()
        found_after_expiry = rag._artifact_by_paper_id(42, task_id)
        assert found_after_expiry is not None
        assert found_after_expiry[2]["user_values"]["paper"]["summary"] == "reviewed"
        from backend.storage import create_storage
        from backend.storage.paths import clear_namespace

        create_storage().delete(create_storage().describe(f"review_artifacts/{task_id}/result.json"))
        clear_namespace(task_id)
        assert rag._artifact_by_paper_id(42, task_id) is None
        old = boto3.client("s3", region_name="us-east-1").get_object(
            Bucket="scwiki-storage-test", Key=original_key)["Body"].read()
        assert json.loads(old)["paper_id"] is None


def test_terminal_review_cleanup_works_after_task_state_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from backend.api import rag
    from backend.ingest import upload_tasks
    from backend.storage import FileIntegrityError, create_storage

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        task_id = "e" * 32
        key = f"review_artifacts/{task_id}/result.json"
        store = create_storage()
        store.put(key, io.BytesIO(json.dumps({"task_id": task_id, "paper_id": 42,
                                              "paper_revision": 1}).encode()), "application/json")
        monkeypatch.setattr(rag, "_paper_review_context", lambda _paper: {
            "task_id": task_id, "paper_id": 42, "paper_revision": 1, "review_status": "approved"})
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: None)
        result = asyncio.run(rag.delete_paper_review_artifact(42, _current_user=SimpleNamespace()))
        assert result["cleaned"] is True
        with pytest.raises(FileIntegrityError):
            store.describe(key)
        assert asyncio.run(rag.delete_paper_review_artifact(42, _current_user=SimpleNamespace()))["cleaned"] is False


def test_expired_review_state_still_protects_wrong_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from fastapi import HTTPException
    from backend.api import rag
    from backend.ingest import upload_tasks
    from backend.storage import create_storage

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        task_id = "e" * 32
        key = f"review_artifacts/{task_id}/result.json"
        store = create_storage()
        store.put(key, io.BytesIO(json.dumps({"task_id": task_id, "paper_id": 42,
                                             "paper_revision": 1}).encode()), "application/json")
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: None)
        monkeypatch.setattr(rag, "_paper_review_context", lambda _paper: {
            "task_id": task_id, "paper_id": 42, "paper_revision": 2, "review_status": "approved"})
        with pytest.raises(HTTPException) as exc:
            asyncio.run(rag.delete_paper_review_artifact(42, _current_user=SimpleNamespace()))
        assert exc.value.status_code == 409
        assert store.describe(key).size > 0


def test_terminal_review_cleanup_checks_published_revision(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from fastapi import HTTPException
    from backend.api import rag
    from backend.ingest import upload_tasks
    from backend.storage import create_storage
    from backend.storage.paths import publish_tree

    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
        monkeypatch.setattr(upload_tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
        task_id = "f" * 32
        source = upload_tasks.artifact_path(task_id)
        source.write_text(json.dumps({"task_id": task_id, "paper_id": 42, "paper_revision": 1}))
        manifest = publish_tree(source, data_root=tmp_path, task_id=task_id, run_id="first")
        source.unlink()
        state = {"artifact_manifest": manifest, "file_contract_version": 1}
        monkeypatch.setattr(upload_tasks, "get_state", lambda _: state)
        monkeypatch.setattr(upload_tasks, "update_state", lambda _task, **changes: state.update(changes) or state)
        context = {"task_id": task_id, "paper_id": 42, "paper_revision": 2, "review_status": "approved"}
        monkeypatch.setattr(rag, "_paper_review_context", lambda _paper: context)

        with pytest.raises(HTTPException) as exc:
            asyncio.run(rag.delete_paper_review_artifact(42, _current_user=SimpleNamespace()))
        assert exc.value.status_code == 409
        assert create_storage().describe(manifest[0]["key"]).size > 0

        context["paper_revision"] = 1
        assert asyncio.run(rag.delete_paper_review_artifact(42, _current_user=SimpleNamespace()))["cleaned"] is True
        assert state["artifact_manifest"] == []


def test_review_artifact_storage_failure_is_desensitized(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException
    from backend.api import rag
    from backend.ingest import upload_tasks
    from backend.storage import FileStorageUnavailable

    monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
    def unavailable(_task: str) -> None:
        raise FileStorageUnavailable("secret endpoint")

    monkeypatch.setattr(upload_tasks, "read_artifact_path", unavailable)
    with pytest.raises(HTTPException) as exc:
        rag._artifact_by_paper_id(42, "a" * 32)
    assert exc.value.status_code == 503
    assert "secret endpoint" not in str(exc.value.detail)


def test_transient_cleanup_removes_objects_without_digest_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from backend.ingest import upload_tasks
    from backend.ingest.upload_contracts import CleanupContext

    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="scwiki-storage-test")
        monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setattr(upload_tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
        monkeypatch.setattr(upload_tasks, "redis_client", lambda: SimpleNamespace(delete=lambda *_: None))
        task_id = "b" * 32
        keys = [f"runs/{task_id}/attempt/review_artifacts/{task_id}/result.json",
                f"review_artifacts/{task_id}/result.json"]
        for key in keys:
            client.put_object(Bucket="scwiki-storage-test", Key=key, Body=b"partial")
        context = CleanupContext.from_state(task_id, {})
        upload_tasks.cleanup_transient_data(task_id, context=context, preserve_review_snapshot=False)
        assert client.list_objects_v2(Bucket="scwiki-storage-test").get("KeyCount", 0) == 0
