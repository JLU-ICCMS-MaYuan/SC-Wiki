"""本地冻结包不能遗漏 S3 文件；本地存储保持原生路径。"""

from pathlib import Path

import pytest

from backend.storage import create_storage
from backend.storage.files import LocalFileStorage
from scripts.local_deploy import cli


def test_local_file_backend_needs_no_s3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FILE_STORAGE_BACKEND", "local")
    for name in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    storage = create_storage(local_root=tmp_path)
    assert isinstance(storage, LocalFileStorage)
    assert storage.root == tmp_path.resolve()


def test_frozen_rejects_object_storage_before_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli.environment, "run", lambda *args, **kwargs: "" if args[0][1] == "status" else "commit")
    monkeypatch.setattr(cli.config, "read_config", lambda root: {"FILE_STORAGE_BACKEND": "s3"})
    monkeypatch.delenv("FILE_STORAGE_BACKEND", raising=False)
    with pytest.raises(ValueError, match="仅支持本地文件存储"):
        cli.pack(tmp_path, None)
