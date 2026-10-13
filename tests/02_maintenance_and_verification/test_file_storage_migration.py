"""隔离库与对象服务中的迁移扫描、复制和回读校验。"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.manual_evidence_models import ScientificManualEvidence
from backend.models import ScientificUploadDraft, User
from backend.scripts import migrate_file_storage as migration_cli
from backend.storage.migration import discover
from backend.storage.reference_inventory import FileInventoryError


class EmptyRedis:
    def scan_iter(self, **_kwargs):
        return iter(())


def _fixture(tmp_path: Path):
    root = tmp_path / "old data"
    root.mkdir()
    task_id = "a" * 32
    manual_id = "b" * 32
    item_id = "c" * 32
    paths = {
        f"upload_PDFs/{task_id}/main.pdf": b"old PDF",
        f"review_artifacts/{task_id}/result.json": b"{}",
        f"parsed_markdown/{task_id}.md": b"paper text",
        f"manual_evidence/{manual_id}/{item_id}": b"manual source",
        "avatars/legacy.jpg": b"avatar",
        "avatars/files/avatars/8/new.jpg": b"new avatar",
        "clean_results/42.json": b"{}",
    }
    for name, content in paths.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    engine = create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    for model in (User, ScientificManualEvidence, ScientificUploadDraft):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add(User(id=7, email="owner@example.test", username="owner", password_hash="hash",
                         real_name="",
                         avatar_key="legacy.jpg"))
        session.add(User(id=8, email="new@example.test", username="newuser", password_hash="hash",
                         real_name="", avatar_key="files/avatars/8/new.jpg"))
        session.add(ScientificUploadDraft(task_id=task_id, owner_id=7, draft={},
            state={"task_id": task_id, "file_path": str(root / f"upload_PDFs/{task_id}/main.pdf"),
                   "file_sha256": "0" * 64}))
        session.add(ScientificManualEvidence(
            id=manual_id, target="upload", target_id=task_id, item_key="field",
            baseline_hash="baseline", value_hash="value", source_hash="source",
            actor_user_id=7, reason="原文核验", items=[{"id": item_id, "kind": "image"}]))
        session.commit()
    return root, engine, paths


def test_scan_finds_explicit_and_derived_references(tmp_path: Path) -> None:
    root, engine, paths = _fixture(tmp_path)
    try:
        with Session(engine) as session:
            manifest = discover(root, session, EmptyRedis())
        assert {item["relative_path"] for item in manifest["files"]} == set(paths)
        avatar = next(item for item in manifest["files"] if item["relative_path"] == "avatars/legacy.jpg")
        assert avatar["references"][0]["old"] == "legacy.jpg"
        assert avatar["references"][0]["new"] == "avatars/legacy.jpg"
        newer = next(item for item in manifest["files"] if item["relative_path"] == "avatars/files/avatars/8/new.jpg")
        assert newer["key"] == "files/avatars/8/new.jpg"
        extra = root / "upload_PDFs" / "unowned.pdf"
        extra.write_bytes(b"unknown")
        with Session(engine) as session, pytest.raises(FileInventoryError, match="未分类"):
            discover(root, session, EmptyRedis())
    finally:
        engine.dispose()


def test_copy_and_verify_are_repeatable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    root, engine, paths = _fixture(tmp_path)
    try:
        with Session(engine) as session:
            manifest = discover(root, session, EmptyRedis())
        manifest["stage"] = "discovered"
        manifest_path = tmp_path / "private manifest.json"
        migration_cli.save_manifest(manifest_path, manifest)
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        with moto.mock_aws():
            client = boto3.client("s3", region_name="us-east-1")
            client.create_bucket(Bucket="scwiki-storage-test")
            migration_cli.copy_files(manifest_path)
            migration_cli.copy_files(manifest_path)
            verified = migration_cli.verify(manifest_path)
            assert verified["stage"] == "verified"
            assert all(item["stage"] == "verified" for item in verified["files"])
            for name, content in paths.items():
                key = "files/avatars/8/new.jpg" if name == "avatars/files/avatars/8/new.jpg" else name
                assert client.get_object(Bucket="scwiki-storage-test", Key=key)["Body"].read() == content
            (root / "avatars/legacy.jpg").write_bytes(b"changed")
            with pytest.raises(Exception, match="变化"):
                migration_cli.copy_files(manifest_path)
    finally:
        engine.dispose()


def test_switch_and_rollback_preserve_redis_ttl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from redis import Redis

    redis_binary = Path(sys.executable).with_name("redis-server")
    if not redis_binary.is_file():
        pytest.skip("隔离 Redis 服务不可用")
    root, engine, _ = _fixture(tmp_path)
    task_id = "a" * 32
    socket = Path("/tmp") / f"scwiki-{uuid4().hex}.sock"
    process = subprocess.Popen([str(redis_binary), "--port", "0", "--unixsocket", str(socket),
                                "--unixsocketperm", "700", "--save", "", "--appendonly", "no"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail("隔离 Redis 启动失败")
            if socket.exists():
                break
            time.sleep(0.02)
        client = Redis(unix_socket_path=str(socket), decode_responses=True,
                       socket_connect_timeout=0.2, socket_timeout=0.2)
        old_path = str(root / f"upload_PDFs/{task_id}/main.pdf")
        client.set(f"upload:{task_id}:state", json.dumps({"file_path": old_path}), ex=3600)
        monkeypatch.setenv("DATABASE_URL", str(engine.url))
        monkeypatch.setenv("REDIS_URL", f"unix://{socket}")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
        monkeypatch.setenv("S3_BUCKET", "scwiki-storage-test")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
        monkeypatch.setenv("SCWIKI_MAINTENANCE_MODE", "1")
        manifest_path = tmp_path / "migration.json"
        with moto.mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="scwiki-storage-test")
            migration_cli.scan(root, manifest_path)
            migration_cli.copy_files(manifest_path)
            migration_cli.verify(manifest_path)
            before = client.ttl(f"upload:{task_id}:state")
            assert migration_cli.switch_references(manifest_path, apply=False)["stage"] == "verified"
            assert json.loads(client.get(f"upload:{task_id}:state"))["file_path"] == old_path
            from rq.registry import StartedJobRegistry

            active = StartedJobRegistry("scwiki-upload", connection=client).key
            client.zadd(active, {"still-running": time.time() + 3600})
            with pytest.raises(FileInventoryError, match="运行中的队列任务"):
                migration_cli.switch_references(manifest_path, apply=True)
            client.delete(active)
            with Session(engine) as session:
                session.get(User, 7).avatar_key = "changed-after-scan.jpg"
                session.commit()
            with pytest.raises(FileInventoryError, match="发生变化"):
                migration_cli.switch_references(manifest_path, apply=True)
            assert json.loads(client.get(f"upload:{task_id}:state"))["file_path"] == old_path
            with Session(engine) as session:
                session.get(User, 7).avatar_key = "legacy.jpg"
                session.commit()
            source_avatar = root / "avatars/legacy.jpg"
            source_avatar.write_bytes(b"changed-after-verify")
            with pytest.raises(Exception, match="切换前发生变化"):
                migration_cli.switch_references(manifest_path, apply=True)
            source_avatar.write_bytes(b"avatar")
            assert migration_cli.switch_references(manifest_path, apply=True)["stage"] == "switched"
            with pytest.raises(FileInventoryError, match="不允许重新复制"):
                migration_cli.copy_files(manifest_path)
            with Session(engine) as session:
                assert session.get(User, 7).avatar_key == "avatars/legacy.jpg"
                assert session.get(ScientificUploadDraft, task_id).state["file_path"] == f"upload_PDFs/{task_id}/main.pdf"
            assert json.loads(client.get(f"upload:{task_id}:state"))["file_path"] == f"upload_PDFs/{task_id}/main.pdf"
            assert client.ttl(f"upload:{task_id}:state") <= before
            with pytest.raises(FileInventoryError, match="开放新写入前"):
                migration_cli.switch_references(manifest_path, apply=True, rollback=True)
            assert migration_cli.switch_references(manifest_path, apply=True, rollback=True,
                                                   before_new_writes=True)["stage"] == "rolled_back"
            with Session(engine) as session:
                assert session.get(User, 7).avatar_key == "legacy.jpg"
                assert session.get(ScientificUploadDraft, task_id).state["file_path"] == old_path
            assert json.loads(client.get(f"upload:{task_id}:state"))["file_path"] == old_path
    finally:
        process.terminate()
        process.wait(timeout=5)
        socket.unlink(missing_ok=True)
        engine.dispose()
