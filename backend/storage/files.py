"""本地与 S3 文件存储使用同一私有契约。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol


class FileConflict(Exception):
    """对象键已被其他内容占用。"""


class FileIntegrityError(Exception):
    """持久文件与已保存的摘要不一致。"""


class FileNotFound(FileIntegrityError):
    """文件键尚不存在。"""


class FileStorageUnavailable(Exception):
    """存储服务不可用。异常正文不得包含连接参数。"""


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 500:
        raise ValueError("文件键无效")
    if "\\" in key or any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError("文件键无效")
    if any(ord(char) < 32 or ord(char) == 127 for char in key):
        raise ValueError("文件键无效")
    return key


@dataclass(frozen=True)
class FileRef:
    key: str
    size: int
    sha256: str
    media_type: str

    def __post_init__(self) -> None:
        validate_key(self.key)
        if self.size < 0 or len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("文件完整性信息无效")


class FileStorage(Protocol):
    def put(self, key: str, source: BinaryIO, media_type: str) -> FileRef: ...
    def open(self, ref: FileRef) -> BinaryIO: ...
    def head(self, ref: FileRef) -> None: ...
    def describe(self, key: str) -> FileRef: ...
    def list_prefix(self, prefix: str) -> list[str]: ...
    def delete(self, ref: FileRef) -> None: ...

    @contextmanager
    def materialize(self, ref: FileRef) -> Iterator[Path]: ...


def _verify(ref: FileRef, source: BinaryIO) -> None:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    if size != ref.size or digest.hexdigest() != ref.sha256:
        raise FileIntegrityError("文件内容与记录不一致")


class _MaterializeMixin:
    @contextmanager
    def materialize(self, ref: FileRef) -> Iterator[Path]:
        with tempfile.TemporaryDirectory(prefix="scwiki-file-") as directory:
            destination = Path(directory) / "content"
            digest = hashlib.sha256()
            size = 0
            with self.open(ref) as source, destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if size != ref.size or digest.hexdigest() != ref.sha256:
                raise FileIntegrityError("文件内容与记录不一致")
            yield destination


class LocalFileStorage(_MaterializeMixin):
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        validate_key(key)
        path = self.root.joinpath(*key.split("/"))
        current = self.root
        for part in key.split("/"):
            current /= part
            if current.is_symlink():
                raise ValueError("文件键指向符号链接")
        # 不允许已存在的目录项通过符号链接逃逸出数据根。
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("文件键越界")
        return path

    def put(self, key: str, source: BinaryIO, media_type: str) -> FileRef:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".upload-", delete=False) as output:
            temporary = Path(output.name)
            try:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        ref = FileRef(key, size, digest.hexdigest(), media_type)
        try:
            os.link(temporary, path)  # 原子 no-replace；重试只接受相同内容。
        except FileExistsError:
            try:
                with path.open("rb") as existing:
                    _verify(ref, existing)
            except (FileIntegrityError, OSError) as exc:
                raise FileConflict("文件键已被不同内容占用") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return ref

    def open(self, ref: FileRef) -> BinaryIO:
        try:
            return self._path(ref.key).open("rb")
        except FileNotFoundError as exc:
            raise FileNotFound("文件不存在") from exc

    def head(self, ref: FileRef) -> None:
        with self.open(ref) as source:
            _verify(ref, source)

    def describe(self, key: str) -> FileRef:
        import mimetypes

        path = self._path(key)
        try:
            with path.open("rb") as source:
                digest = hashlib.sha256()
                size = 0
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
        except FileNotFoundError as exc:
            raise FileNotFound("文件不存在") from exc
        return FileRef(key, size, digest.hexdigest(), mimetypes.guess_type(key)[0] or "application/octet-stream")

    def delete(self, ref: FileRef) -> None:
        self._path(ref.key).unlink(missing_ok=True)

    def list_prefix(self, prefix: str) -> list[str]:
        directory = self._path(prefix.rstrip("/"))
        if not directory.is_dir():
            return []
        return sorted(path.relative_to(self.root).as_posix() for path in directory.rglob("*")
                      if path.is_file() and not path.is_symlink())


class S3FileStorage(_MaterializeMixin):
    def __init__(self, *, endpoint: str, region: str, bucket: str, access_key: str, secret_key: str,
                 addressing_style: str = "path"):
        if not all((endpoint, region, bucket, access_key, secret_key)):
            raise ValueError("S3 存储配置不完整")
        if addressing_style not in {"path", "virtual"}:
            raise ValueError("S3 寻址方式无效")
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("S3 模式需要 boto3") from exc
        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint, region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            config=Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 3},
                          s3={"addressing_style": addressing_style}),
        )

    def put(self, key: str, source: BinaryIO, media_type: str) -> FileRef:
        validate_key(key)
        digest = hashlib.sha256()
        size = 0
        with tempfile.TemporaryFile() as staged:
            while chunk := source.read(1024 * 1024):
                staged.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            ref = FileRef(key, size, digest.hexdigest(), media_type)
            staged.seek(0)
            # 部分 S3 兼容服务忽略 If-None-Match；先核验已有键，业务键另由 UUID 隔离并发。
            try:
                existing = self.describe(key)
            except FileNotFound:
                pass
            else:
                if existing.size == ref.size and existing.sha256 == ref.sha256:
                    try:
                        with self.materialize(ref):
                            pass
                    except FileIntegrityError as exc:
                        raise FileConflict("已有对象内容损坏") from exc
                    return ref
                raise FileConflict("文件键已被不同内容占用")
            try:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=staged,
                                       ContentLength=size, ContentType=media_type,
                                       Metadata={"sha256": ref.sha256}, IfNoneMatch="*")
            except Exception as exc:
                if self._is_conflict(exc):
                    self.head(ref)
                    return ref
                raise FileStorageUnavailable("文件存储暂时不可用") from exc
        try:
            with self.materialize(ref):
                pass
        except FileIntegrityError as exc:
            self.delete(ref)
            raise FileStorageUnavailable("对象写入后校验失败") from exc
        return ref

    @staticmethod
    def _is_conflict(exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        return code in {"PreconditionFailed", "ConditionalRequestConflict"}

    def open(self, ref: FileRef) -> BinaryIO:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=ref.key)["Body"]
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise FileNotFound("文件不存在") from exc
            raise FileStorageUnavailable("文件存储暂时不可用") from exc

    def head(self, ref: FileRef) -> None:
        try:
            result = self.client.head_object(Bucket=self.bucket, Key=ref.key)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise FileNotFound("文件不存在") from exc
            raise FileStorageUnavailable("文件存储暂时不可用") from exc
        if result["ContentLength"] != ref.size or result.get("Metadata", {}).get("sha256") != ref.sha256:
            raise FileConflict("文件键已被不同内容占用")

    def describe(self, key: str) -> FileRef:
        validate_key(key)
        try:
            result = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404"}:
                raise FileNotFound("文件不存在") from exc
            raise FileStorageUnavailable("文件存储暂时不可用") from exc
        digest = result.get("Metadata", {}).get("sha256")
        if not digest:
            raise FileIntegrityError("文件缺少内容摘要")
        return FileRef(key, result["ContentLength"], digest,
                       result.get("ContentType") or "application/octet-stream")

    def delete(self, ref: FileRef) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=ref.key)
        except Exception as exc:
            raise FileStorageUnavailable("文件存储暂时不可用") from exc

    def list_prefix(self, prefix: str) -> list[str]:
        validate_key(prefix.rstrip("/"))
        keys = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                keys.extend(item["Key"] for item in page.get("Contents", []))
        except Exception as exc:
            raise FileStorageUnavailable("文件存储暂时不可用") from exc
        return sorted(keys)


def create_storage(*, local_root: Path | None = None) -> FileStorage:
    mode = os.environ.get("FILE_STORAGE_BACKEND", "local")
    if mode == "local":
        from backend.rag.config import settings

        root = Path(os.environ.get("FILE_STORAGE_LOCAL_ROOT") or str(local_root or settings.sc_wiki_data_dir))
        return LocalFileStorage(root)
    if mode == "s3":
        return S3FileStorage(
            endpoint=os.environ.get("S3_ENDPOINT_URL", ""),
            region=os.environ.get("S3_REGION", "us-east-1"),
            bucket=os.environ.get("S3_BUCKET", ""),
            access_key=os.environ.get("S3_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("S3_SECRET_ACCESS_KEY", ""),
            addressing_style=os.environ.get("S3_ADDRESSING_STYLE", "path"),
        )
    raise ValueError("文件存储模式无效")
