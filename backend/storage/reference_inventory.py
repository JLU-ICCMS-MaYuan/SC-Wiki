"""历史文件预检：只接受已登记的业务引用，未知文件必须人工分类。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


BUSINESS_ROOTS = frozenset({
    "uploads", "upload_PDFs", "parsed_markdown", "review_artifacts",
    "clean_results", "avatars", "manual_evidence",
})


class FileInventoryError(ValueError):
    """引用缺失、越界或遇到没有归属的持久文件。"""


@dataclass(frozen=True)
class InventoryFile:
    relative_path: str
    size: int
    sha256: str


def scan_registered_files(root: Path, references: set[str]) -> list[InventoryFile]:
    """扫描数据库/Redis 已登记路径，拒绝多余或缺失的业务文件。"""
    root = root.resolve()
    normalized: set[str] = set()
    for value in references:
        path = Path(value)
        if path.is_absolute() or "\\" in value or not path.parts or ".." in path.parts or path.parts[0] not in BUSINESS_ROOTS:
            raise FileInventoryError("文件引用不在允许的数据目录中")
        normalized.add(path.as_posix())

    found: set[str] = set()
    for name in sorted(BUSINESS_ROOTS):
        directory = root / name
        if not directory.exists():
            continue
        if directory.is_symlink():
            raise FileInventoryError(f"业务目录是符号链接：{name}")
        for path in directory.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise FileInventoryError(f"发现越界或符号链接：{relative}")
            if path.is_file():
                if relative not in normalized:
                    raise FileInventoryError(f"未分类的持久文件：{relative}")
                found.add(relative)

    missing = normalized - found
    if missing:
        raise FileInventoryError(f"被引用文件缺失：{sorted(missing)[0]}")

    records = []
    for relative in sorted(found):
        path = root / relative
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        records.append(InventoryFile(relative, size, digest.hexdigest()))
    return records
