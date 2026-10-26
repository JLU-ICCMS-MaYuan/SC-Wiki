"""固定模型目录与原文件校验，客户端只能使用白名单 ID。"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from .inference import CACHE

CATALOG_PATH = Path(__file__).with_name("catalog.json")


def source_catalog():
    return json.loads(CATALOG_PATH.read_text())


@lru_cache(maxsize=64)
def _digest(path: str, size: int, mtime: int, ctime: int):
    """缓存受 inode 元信息约束的摘要，避免每次打开目录重复扫描大文件。"""
    with Path(path).open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return sha


def file_status(item):
    path = CACHE / "datasets" / item["filename"]
    if not path.is_file():
        return "原始网站的文件暂不可用" if not item.get("sha256") else "数据文件尚未准备，请联系管理员"
    if path.is_symlink() or path.stat().st_size != item["size"]:
        return "数据文件完整性校验失败，已停止下载"
    stat = path.stat()
    sha = _digest(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if item.get("sha256"):
        return None if sha == item["sha256"] else "数据文件摘要校验失败，已停止下载"
    with path.open("rb") as stream:
        md5 = hashlib.file_digest(stream, "md5").hexdigest()
    return None if md5 == item.get("publisher_md5") else "发布方摘要校验失败，已停止下载"


def dataset(identifier):
    return next((item for item in source_catalog()["datasets"] if item["id"] == identifier), None)


def catalog():
    current = source_catalog()
    for item in current["datasets"]:
        error = file_status(item)
        item.update(available=error is None, error=error,
                    download_url=f"/api/tc-models/datasets/{item['id']}" if error is None else None)
    return current


def verify_bete_artifacts():
    """导入作者 Python 模块和权重前，核对固定发布提交及全部执行制品。"""
    from .inference import REVISION
    tree = json.loads((CACHE / "bete-tree.json").read_text())
    if tree.get("sha") != REVISION or tree.get("truncated"):
        raise ValueError("模型版本清单不匹配")
    entries = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    expected = [f"CSO/model_cso_{i}.pt" for i in range(100)]
    expected += [p for p in entries if p.startswith("structures/") and p.endswith(".cif")]
    expected += ["utils/__init__.py", "utils/model.py", "utils/data.py"]
    for name in expected:
        path = CACHE / "bete" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("模型或结构文件缺失")
        size = path.stat().st_size
        if size != entries[name]["size"]:
            raise ValueError("模型文件大小不匹配")
        digest = hashlib.sha1(f"blob {size}\0".encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != entries[name]["sha"]:
            raise ValueError("模型文件摘要不匹配")
