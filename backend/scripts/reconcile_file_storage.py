"""只读核对头像与人工证据的未引用对象；仅维护窗口显式 apply 时清理。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.storage.reference_inventory import FileInventoryError
from backend.storage.files import FileIntegrityError, FileStorageUnavailable


AVATAR_KEY = re.compile(r"files/avatars/([0-9]+)/[0-9a-f]{32}\.jpg$")
LEGACY_AVATAR_KEY = re.compile(r"avatars/[A-Za-z0-9._-]+$")
MANUAL_KEY = re.compile(r"manual_evidence/([0-9a-f]{32})/([0-9a-f]{32})$")


def unused_keys(session: Session, store) -> list[str]:
    """只对明确的两类新对象判定引用；未知键一律阻断。"""
    from backend.models import User
    from backend.manual_evidence_models import ScientificManualEvidence

    users = {int(user.id): user.avatar_key for user in session.scalars(select(User))}
    evidence = {str(row.id): row.items or [] for row in session.scalars(select(ScientificManualEvidence))}
    unused = []
    for key in store.list_prefix("files/avatars/"):
        match = AVATAR_KEY.fullmatch(key)
        if match is None:
            raise FileInventoryError("存在未识别的头像对象键")
        if users.get(int(match.group(1))) != key:
            unused.append(key)
    live_avatars = {key for key in users.values() if key}
    for key in store.list_prefix("avatars/"):
        if LEGACY_AVATAR_KEY.fullmatch(key) is None:
            raise FileInventoryError("存在未识别的旧头像对象键")
        if key not in live_avatars:
            unused.append(key)
    for key in store.list_prefix("manual_evidence/"):
        match = MANUAL_KEY.fullmatch(key)
        if match is None:
            raise FileInventoryError("存在未识别的人工证据对象键")
        row_id, item_id = match.groups()
        if not any(item.get("kind") != "text" and item.get("id") == item_id
                   and (item.get("storage_key") or f"manual_evidence/{row_id}/{item_id}") == key
                   for item in evidence.get(row_id, [])):
            unused.append(key)
    return sorted(unused)


def reconcile(*, apply: bool = False) -> dict[str, int]:
    if apply and os.environ.get("SCWIKI_MAINTENANCE_MODE") != "1":
        raise FileInventoryError("未进入显式维护窗口，拒绝删除文件")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise FileInventoryError("缺少显式 DATABASE_URL")
    from backend.scripts.migrate_file_storage import s3_storage

    store = s3_storage()
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            unused = unused_keys(session, store)
            if apply:
                # 数据库会话保持到删除结束；维护窗口须先停止所有写入进程。
                for key in unused:
                    store.delete(store.describe(key))
    finally:
        engine.dispose()
    return {"unused": len(unused), "deleted": len(unused) if apply else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(reconcile(apply=args.apply), ensure_ascii=False))
        return 0
    except (FileInventoryError, ValueError):
        print("文件清理前置检查未通过", file=sys.stderr)
        return 2
    except (SQLAlchemyError, FileStorageUnavailable):
        print("文件清理依赖服务不可用", file=sys.stderr)
        return 3
    except FileIntegrityError:
        print("文件清理完整性检查失败", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
