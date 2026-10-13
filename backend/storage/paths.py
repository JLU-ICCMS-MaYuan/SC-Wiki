"""将稳定文件键按需转换为当前进程可清理的临时路径。"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import tempfile
import threading
import uuid
import atexit
from pathlib import Path

from .files import FileIntegrityError, FileRef, create_storage


_CACHE_ROOTS: dict[str, Path] = {}
_CACHE_LOCK = threading.Lock()


def _remove_caches() -> None:
    for root in _CACHE_ROOTS.values():
        shutil.rmtree(root, ignore_errors=True)


atexit.register(_remove_caches)


def object_mode() -> bool:
    return os.environ.get("FILE_STORAGE_BACKEND", "local") == "s3"


def _cache_root(namespace: str | None = None) -> Path:
    base = Path(os.environ.get("FILE_STORAGE_TMP_DIR") or tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache_id = str(base.resolve())
    with _CACHE_LOCK:
        root = _CACHE_ROOTS.get(cache_id)
        if root is None:
            root = Path(tempfile.mkdtemp(prefix="scwiki-files-", dir=base))
            _CACHE_ROOTS[cache_id] = root
    if namespace:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", namespace):
            raise ValueError("临时目录身份无效")
        root /= namespace
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def resolve_file(key: str, *, size: int, sha256: str, media_type: str = "application/octet-stream",
                 namespace: str | None = None) -> Path:
    """返回当前节点已校验的文件路径；对象模式绝不读取旧业务目录。"""
    if not object_mode():
        path = Path(key)
        if path.is_absolute():
            return path
        from backend.rag.config import settings
        return settings.sc_wiki_data_dir / path

    ref = FileRef(key, size, sha256, media_type)
    cache = _cache_root(namespace) / ref.sha256 / Path(ref.key).name
    if cache.is_file():
        digest = hashlib.sha256(cache.read_bytes()).hexdigest()
        if cache.stat().st_size == ref.size and digest == ref.sha256:
            return cache
        cache.unlink()
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with create_storage().materialize(ref) as source:
        with tempfile.NamedTemporaryFile(dir=cache.parent, prefix=".download-", delete=False) as output:
            temporary = Path(output.name)
            try:
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, output)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(cache)
    if cache.stat().st_size != ref.size:
        cache.unlink(missing_ok=True)
        raise FileIntegrityError("临时文件大小与引用不一致")
    return cache


def clear_namespace(namespace: str) -> None:
    if not object_mode():
        return
    root = _cache_root(namespace)
    shutil.rmtree(root, ignore_errors=True)


def resolve_known_key(key: str, *, namespace: str | None = None) -> Path:
    """仅供服务端按已知规则生成的持久键使用；不接受客户端任意键。"""
    if not object_mode():
        return resolve_file(key, size=0, sha256="0" * 64)
    ref = create_storage().describe(key)
    return resolve_file(ref.key, size=ref.size, sha256=ref.sha256,
                        media_type=ref.media_type, namespace=namespace)


def publish_tree(directory: Path, *, data_root: Path, task_id: str, run_id: str) -> list[dict[str, object]]:
    """上传必需产物后返回可核验清单，不在此改变业务完成状态。"""
    if not object_mode():
        return []
    storage = create_storage()
    records: list[dict[str, object]] = []
    if not directory.exists():
        return records
    paths = [directory] if directory.is_file() else sorted(directory.rglob("*"))
    for path in paths:
        if path.is_symlink():
            raise ValueError("解析产物包含符号链接")
        if not path.is_file():
            continue
        logical_path = path.relative_to(data_root).as_posix()
        key = f"runs/{task_id}/{run_id}/{logical_path}"
        with path.open("rb") as stream:
            ref = storage.put(key, stream, mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        records.append({"logical_path": logical_path, "key": ref.key, "size": ref.size, "sha256": ref.sha256,
                        "media_type": ref.media_type})
    return records


def publish_replacement(path: Path, *, data_root: Path, task_id: str,
                        current: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    """改写审核产物时生成新版本，并返回新的当前引用清单。"""
    if not object_mode():
        return current or []
    logical = path.relative_to(data_root).as_posix()
    new = publish_tree(path, data_root=data_root, task_id=task_id, run_id=uuid.uuid4().hex)
    return [item for item in current or [] if item.get("logical_path") != logical] + new
