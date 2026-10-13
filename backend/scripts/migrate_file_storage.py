"""安全迁移旧本地业务文件；默认操作不会改写业务库。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from redis.exceptions import RedisError

from backend.storage.files import FileConflict, FileIntegrityError, FileStorageUnavailable, S3FileStorage
from backend.storage.reference_inventory import FileInventoryError


def save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".manifest-", delete=False) as stream:
        temporary = Path(stream.name)
        os.chmod(temporary, 0o600)
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary.replace(path)


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1 or not isinstance(data.get("files"), list):
        raise FileInventoryError("迁移清单格式无效")
    return data


def s3_storage() -> S3FileStorage:
    return S3FileStorage(
        endpoint=os.environ.get("S3_ENDPOINT_URL", ""),
        region=os.environ.get("S3_REGION", "us-east-1"),
        bucket=os.environ.get("S3_BUCKET", ""),
        access_key=os.environ.get("S3_ACCESS_KEY_ID", ""),
        secret_key=os.environ.get("S3_SECRET_ACCESS_KEY", ""),
        addressing_style=os.environ.get("S3_ADDRESSING_STYLE", "path"),
    )


def scan(source_root: Path, manifest_path: Path) -> dict:
    if manifest_path.exists():
        raise FileInventoryError("迁移清单已存在，拒绝覆盖")
    database_url, redis_url = os.environ.get("DATABASE_URL"), os.environ.get("REDIS_URL")
    if not database_url or not redis_url:
        raise FileInventoryError("扫描需要显式 DATABASE_URL 和 REDIS_URL")
    from redis import Redis
    from backend.storage.migration import discover

    engine = create_engine(database_url, pool_pre_ping=True)
    redis_client = Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
    try:
        with Session(engine) as session:
            manifest = discover(source_root, session, redis_client)
    finally:
        engine.dispose()
        redis_client.close()
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest["stage"] = "discovered"
    save_manifest(manifest_path, manifest)
    return manifest


def copy_files(manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    if manifest.get("stage") not in {"discovered", "copied", "verified"}:
        raise FileInventoryError("当前迁移阶段不允许重新复制")
    root = Path(manifest["source_root"]).resolve()
    storage = s3_storage()
    from backend.storage.reference_inventory import scan_registered_files

    actual = {item.relative_path: item for item in scan_registered_files(
        root, {item["relative_path"] for item in manifest["files"]})}
    for item in manifest["files"]:
        current = actual[item["relative_path"]]
        if current.size != item["size"] or current.sha256 != item["sha256"]:
            raise FileIntegrityError("源文件在扫描后发生变化")
        if item.get("stage") in {"copied", "verified"}:
            continue
        with (root / item["relative_path"]).open("rb") as source:
            ref = storage.put(item["key"], source, "application/octet-stream")
        if ref.size != item["size"] or ref.sha256 != item["sha256"]:
            raise FileIntegrityError("目标对象与源文件不一致")
        item["stage"] = "copied"
        save_manifest(manifest_path, manifest)
    if manifest["stage"] != "verified":
        manifest["stage"] = "copied"
    save_manifest(manifest_path, manifest)
    return manifest


def verify(manifest_path: Path) -> dict:
    manifest = load_manifest(manifest_path)
    if manifest.get("stage") not in {"copied", "verified"}:
        raise FileInventoryError("当前迁移阶段不允许重新核验")
    storage = s3_storage()
    for item in manifest["files"]:
        if item.get("stage") not in {"copied", "verified"}:
            raise FileInventoryError("目标文件未全部复制")
        ref = storage.describe(item["key"])
        if ref.size != item["size"] or ref.sha256 != item["sha256"]:
            raise FileIntegrityError("目标对象摘要不匹配")
        with storage.materialize(ref):
            pass
        item["stage"] = "verified"
        save_manifest(manifest_path, manifest)
    manifest["stage"] = "verified"
    save_manifest(manifest_path, manifest)
    return manifest


def switch_references(manifest_path: Path, *, apply: bool, rollback: bool = False,
                      before_new_writes: bool = False) -> dict:
    manifest = load_manifest(manifest_path)
    expected = "switched" if rollback else "verified"
    finished = "rolled_back" if rollback else "switched"
    if manifest.get("stage") == finished:
        return manifest
    if manifest.get("stage") != expected:
        raise FileInventoryError("迁移阶段不允许切换引用")
    if not apply:
        return manifest
    if os.environ.get("SCWIKI_MAINTENANCE_MODE") != "1":
        raise FileInventoryError("应用未进入显式维护窗口，拒绝改写引用")
    if rollback and not before_new_writes:
        raise FileInventoryError("仅可在目标开放新写入前执行回退")
    database_url, redis_url = os.environ.get("DATABASE_URL"), os.environ.get("REDIS_URL")
    if not database_url or not redis_url:
        raise FileInventoryError("切换需要显式 DATABASE_URL 和 REDIS_URL")
    from backend.storage.reference_inventory import scan_registered_files

    root = Path(manifest["source_root"]).resolve()
    actual = {item.relative_path: item for item in scan_registered_files(
        root, {item["relative_path"] for item in manifest["files"]})}
    for item in manifest["files"]:
        file = actual[item["relative_path"]]
        if file.size != item["size"] or file.sha256 != item["sha256"]:
            raise FileIntegrityError("源文件在切换前发生变化")
    from redis import Redis
    from backend.storage.migration import apply_database_references, apply_redis_references

    engine = create_engine(database_url, pool_pre_ping=True)
    redis_client = Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
    try:
        # 只查询运行中 registry 的数量，不反序列化旧 RQ 作业载荷。
        for key in redis_client.scan_iter(match="rq:wip:*"):
            if redis_client.zcard(key):
                raise FileInventoryError("仍有运行中的队列任务，拒绝切换文件引用")
        with Session(engine) as session, session.begin():
            apply_database_references(manifest, session, rollback=rollback)
        # 数据库成功、Redis 失败时保持原阶段；重跑时已改数据库引用按新值跳过。
        apply_redis_references(manifest, redis_client, rollback=rollback)
    finally:
        engine.dispose()
        redis_client.close()
    manifest["stage"] = finished
    manifest[f"{finished}_at"] = datetime.now(timezone.utc).isoformat()
    save_manifest(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="只读发现引用并生成私有清单")
    scan_parser.add_argument("--source-root", type=Path, required=True)
    scan_parser.add_argument("--manifest", type=Path, required=True)
    for name in ("copy", "verify", "switch", "rollback"):
        action = sub.add_parser(name)
        action.add_argument("--manifest", type=Path, required=True)
        if name in {"switch", "rollback"}:
            action.add_argument("--apply", action="store_true")
        if name == "rollback":
            action.add_argument("--before-new-writes", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "scan":
            result = scan(args.source_root, args.manifest)
        elif args.command == "copy":
            result = copy_files(args.manifest)
        elif args.command == "verify":
            result = verify(args.manifest)
        else:
            result = switch_references(args.manifest, apply=args.apply,
                                       rollback=args.command == "rollback",
                                       before_new_writes=getattr(args, "before_new_writes", False))
        print(json.dumps({"stage": result["stage"], "files": len(result["files"]),
                          "task_count": result.get("task_count", 0)}, ensure_ascii=False))
        return 0
    except (FileInventoryError, ValueError, KeyError, OSError) as exc:
        print(f"迁移前置检查未通过：{type(exc).__name__}", file=sys.stderr)
        return 2
    except (FileStorageUnavailable, SQLAlchemyError, RedisError):
        print("迁移依赖服务暂时不可用", file=sys.stderr)
        return 3
    except (FileIntegrityError, FileConflict):
        print("文件完整性或引用冲突", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
