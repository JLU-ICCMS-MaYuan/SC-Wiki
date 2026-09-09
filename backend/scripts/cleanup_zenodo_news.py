"""可审计地清理 OpenAlex 历史 Zenodo 资讯。

默认只预览。真正执行必须显式传入 ``--execute`` 和备份文件路径。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.database import engine as default_engine
from backend.news.domain import normalize_doi
from backend.news.models import NewsFeedIdentity, NewsFeedItem


ZENODO_DOI_PREFIX = "10.5281/"
BACKUP_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Target:
    item: NewsFeedItem
    identities: tuple[NewsFeedIdentity, ...]

    def as_dict(self) -> dict[str, Any]:
        item = {column.name: getattr(self.item, column.name) for column in NewsFeedItem.__table__.columns}
        identities = [
            {column.name: getattr(identity, column.name) for column in NewsFeedIdentity.__table__.columns}
            for identity in self.identities
        ]
        return {"item": item, "identities": identities}


def find_targets(db: Session) -> list[Target]:
    """按规范化 DOI 精确识别 OpenAlex Zenodo 历史记录。"""
    items = db.scalars(
        select(NewsFeedItem)
        .where(NewsFeedItem.discovery_source == "openalex")
        .order_by(NewsFeedItem.id)
    ).all()
    targets: list[Target] = []
    for item in items:
        if not normalize_doi(item.doi).startswith(ZENODO_DOI_PREFIX):
            continue
        identities = tuple(
            db.scalars(
                select(NewsFeedIdentity)
                .where(NewsFeedIdentity.item_id == item.id)
                .order_by(NewsFeedIdentity.key)
            ).all()
        )
        targets.append(Target(item=item, identities=identities))
    return targets


def build_backup(targets: list[Target], created_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "criteria": {
            "discovery_source": "openalex",
            "normalized_doi_prefix": ZENODO_DOI_PREFIX,
        },
        "summary": {
            "item_count": len(targets),
            "identity_count": sum(len(target.identities) for target in targets),
        },
        "items": [target.as_dict() for target in targets],
    }


def write_backup(path: Path, payload: dict[str, Any]) -> None:
    if not path.parent.exists():
        raise FileNotFoundError(f"备份目录不存在: {path.parent}")
    if path.exists():
        raise FileExistsError(f"备份文件已存在，拒绝覆盖: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def report(targets: list[Target]) -> dict[str, Any]:
    return {
        "item_count": len(targets),
        "identity_count": sum(len(target.identities) for target in targets),
        "item_ids": [target.item.id for target in targets],
        "normalized_dois": [normalize_doi(target.item.doi) for target in targets],
    }


def clean(
    engine,
    backup_file: Path | None = None,
    execute: bool = False,
    after_identity_delete: Callable[[Session], None] | None = None,
) -> dict[str, Any]:
    """预览或事务性清理目标记录，返回可打印的影响报告。"""
    with Session(engine) as db:
        targets = find_targets(db)
        result = report(targets)
        if not execute:
            result["dry_run"] = True
            return result
        if backup_file is None:
            raise ValueError("执行清理必须提供 backup_file")

        write_backup(backup_file, build_backup(targets))
        # find_targets 已开启只读事务；先结束它，再以单个事务执行删除。
        db.rollback()
        with db.begin():
            item_ids = [target.item.id for target in targets]
            if item_ids:
                db.execute(delete(NewsFeedIdentity).where(NewsFeedIdentity.item_id.in_(item_ids)))
                if after_identity_delete:
                    after_identity_delete(db)
                db.execute(delete(NewsFeedItem).where(NewsFeedItem.id.in_(item_ids)))
        result["dry_run"] = False
        result["backup_file"] = str(backup_file)
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理 OpenAlex 历史 Zenodo 资讯")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只报告目标，不修改数据库（默认）")
    mode.add_argument("--execute", action="store_true", help="执行事务性清理")
    parser.add_argument("--backup-file", type=Path, help="执行前写入的 JSON 备份清单")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = clean(default_engine, backup_file=args.backup_file, execute=args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
