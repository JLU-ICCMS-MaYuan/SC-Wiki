"""文件存储边界的真实本地读写与故障测试。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from backend.storage.files import FileConflict, FileIntegrityError, LocalFileStorage, S3FileStorage, validate_key


@pytest.mark.parametrize("key", ["/absolute", "../escape", "a/../b", "a//b", "a/./b", "a\\b", "a\x00b"])
def test_rejects_unsafe_keys(key: str) -> None:
    with pytest.raises(ValueError):
        validate_key(key)


def test_local_roundtrip_and_immutable_key(tmp_path: Path) -> None:
    store = LocalFileStorage(tmp_path)
    payload = b"a" * (1024 * 1024 + 23)
    ref = store.put("files/paper/42/source.pdf", io.BytesIO(payload), "application/pdf")
    assert ref.size == len(payload)
    store.head(ref)
    assert store.put(ref.key, io.BytesIO(payload), ref.media_type) == ref
    with store.materialize(ref) as materialized:
        assert materialized.read_bytes() == payload
        temporary_parent = materialized.parent
    assert not temporary_parent.exists()
    with pytest.raises(FileConflict):
        store.put(ref.key, io.BytesIO(b"different"), ref.media_type)
    with store.open(ref) as stream:
        assert stream.read() == payload
    store.delete(ref)
    store.delete(ref)
    with pytest.raises(FileIntegrityError):
        store.head(ref)


def test_local_detects_corruption_and_symlink_escape(tmp_path: Path) -> None:
    store = LocalFileStorage(tmp_path / "data")
    ref = store.put("files/paper/42/source.pdf", io.BytesIO(b"original"), "application/pdf")
    (store.root / ref.key).write_bytes(b"changed")
    with pytest.raises(FileIntegrityError):
        store.head(ref)
    with pytest.raises(FileIntegrityError):
        with store.materialize(ref):
            pass
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        store.put("linked/secret", io.BytesIO(b"secret"), "text/plain")
    assert not (outside / "secret").exists()


def test_local_only_selected_explicitly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from backend.storage import create_storage

    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT", str(tmp_path))
    assert isinstance(create_storage(), LocalFileStorage)
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "s3")
    for name in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="S3 存储配置不完整"):
        create_storage()


def test_s3_protocol_roundtrip_and_conflict() -> None:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        bucket = "scwiki-storage-test"
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bucket)
        store = S3FileStorage(endpoint="https://s3.amazonaws.com", region="us-east-1", bucket=bucket,
                              access_key="test", secret_key="test")
        ref = store.put("files/paper/42/source.pdf", io.BytesIO(b"PDF content"), "application/pdf")
        store.head(ref)
        with store.materialize(ref) as path:
            assert path.read_bytes() == b"PDF content"
        assert store.put(ref.key, io.BytesIO(b"PDF content"), ref.media_type) == ref
        with pytest.raises(FileConflict):
            store.put(ref.key, io.BytesIO(b"other"), ref.media_type)
        store.delete(ref)
        with pytest.raises(FileIntegrityError):
            store.head(ref)
