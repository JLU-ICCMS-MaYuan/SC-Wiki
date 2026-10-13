"""统一业务文件存储边界。权限与引用生命周期由调用方负责。"""

from .files import (
    FileConflict,
    FileIntegrityError,
    FileNotFound,
    FileRef,
    FileStorage,
    FileStorageUnavailable,
    create_storage,
)

__all__ = [
    "FileConflict",
    "FileIntegrityError",
    "FileNotFound",
    "FileRef",
    "FileStorage",
    "FileStorageUnavailable",
    "create_storage",
]
