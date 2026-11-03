"""重放真实发现的重复文件故障；Redis、哈希判重及存储清理均运行真实代码。"""

import subprocess
import sys
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis


@pytest.fixture
def isolated_redis():
    binary = Path(sys.executable).with_name("redis-server")
    assert binary.is_file(), "需要项目 Python 环境附带的 redis-server"
    socket = Path(tempfile.gettempdir()) / f"scw-{uuid4().hex[:8]}.sock"
    process = subprocess.Popen([str(binary), "--port", "0", "--unixsocket", str(socket),
                                "--save", "", "--appendonly", "no"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = Redis(unix_socket_path=str(socket), decode_responses=True,
                   socket_connect_timeout=0.2, socket_timeout=0.2)
    try:
        for _ in range(100):
            assert process.poll() is None, "隔离 Redis 启动失败"
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(0.02)
        else:
            pytest.fail("隔离 Redis 未就绪")
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        socket.unlink(missing_ok=True)


@pytest.mark.parametrize("mode", ["local", "s3"])
def test_duplicate_upload_returns_conflict_and_removes_only_rejected_copy(monkeypatch, tmp_path, isolated_redis, mode):
    monkeypatch.setenv("JWT_SECRET_KEY", "isolated-upload-conflict-test-key")
    from backend.api import upload_tasks as api
    from backend.ingest import upload_tasks as tasks
    from backend.rag.llm_context import request_llm_config
    from backend.security import get_current_user

    monkeypatch.setattr(tasks, "redis_client", lambda: isolated_redis)
    monkeypatch.setattr(tasks, "authoritative_state", lambda *_: None)
    monkeypatch.setattr(tasks, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    jobs = []
    monkeypatch.setattr(tasks, "enqueue_processing", lambda task_id: jobs.append(task_id))
    monkeypatch.setenv("FILE_STORAGE_BACKEND", mode)
    monkeypatch.setenv("FILE_STORAGE_TMP_DIR", str(tmp_path / "cache"))
    if mode == "s3":
        import boto3
        import moto
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-conflict-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    with (moto.mock_aws() if mode == "s3" else nullcontext()):
        if mode == "s3":
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="scwiki-conflict-test")
        app = FastAPI()
        app.include_router(api.router)
        app.dependency_overrides[request_llm_config] = lambda: None
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, role="user", is_approved=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            source = b"%PDF-1.7 real-upload-conflict-replay"
            created = client.post("/api/upload-tasks", json={"files": [
                {"client_id": "main", "role": "main", "filename": "main.pdf", "size": len(source)},
                {"client_id": "si", "role": "supplementary", "filename": "si.pdf", "size": len(source)},
            ]})
            assert created.status_code == 201, created.text
            task = created.json()["data"]
            task_id = task["task_id"]
            main_id, si_id = [file["file_id"] for file in task["files"]]
            endpoint = f"/api/upload-tasks/{task_id}/files/"
            original = client.put(endpoint + main_id, files={"file": ("main.pdf", source, "application/pdf")})
            assert original.status_code == 200, original.text
            rejected = client.put(endpoint + si_id, files={"file": ("si.pdf", source, "application/pdf")})
            assert rejected.status_code == 409, rejected.text
            assert rejected.json()["detail"] == {
                "code": "UPLOAD_FILE_CONFLICT", "message": "任务内存在内容完全相同的重复文件",
            }
            state = tasks.get_state(task_id)
            assert state["files"][0]["upload_status"] == "completed"
            assert state["files"][1]["upload_status"] != "completed"
            assert not jobs
            assert not (tasks.task_directory(task_id) / f"{si_id}.pdf").exists()
            if mode == "s3":
                stored = s3.list_objects_v2(Bucket="scwiki-conflict-test")["Contents"]
                assert len(stored) == 1
                assert s3.get_object(Bucket="scwiki-conflict-test", Key=state["files"][0]["stored_path"])["Body"].read() == source
            else:
                assert Path(state["files"][0]["stored_path"]).read_bytes() == source
            corrected = client.put(endpoint + si_id, files={"file": ("si.pdf", source + b" distinct supplement", "application/pdf")})
            assert corrected.status_code == 200, corrected.text
            assert jobs == [task_id]
            assert len(tasks.get_state(task_id)["files"]) == 2
