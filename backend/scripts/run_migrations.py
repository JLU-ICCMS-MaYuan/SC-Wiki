"""Safely run Alembic for both imported and newly created databases."""

from __future__ import annotations

import os
import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


IMPORTED_SCHEMA_BASELINE = "b95420be551f"
ISSUE90_SAFE_HEAD = "issue90_copy_v1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fresh-local', action='store_true', help='仅对全新空本地库执行完整部署迁移')
    modes.add_argument('--verify-local', action='store_true', help='只核验便携部署 schema，不执行迁移')
    modes.add_argument('--production', action='store_true', help='显式升级已知生产 schema；不自动 stamp')
    parser.add_argument('--apply', action='store_true', help='确认执行生产 schema 升级')
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL 环境变量未设置")
    if args.production:
        if not args.apply:
            raise RuntimeError("生产迁移必须显式 --apply")
        from alembic.script import ScriptDirectory
        from sqlalchemy import text
        cfg = Config("alembic.ini")
        scripts = ScriptDirectory.from_config(cfg)
        engine = create_engine(database_url)
        try:
            with engine.connect() as conn:
                revisions = list(conn.execute(text("SELECT version_num FROM alembic_version")).scalars())
            if not revisions or any(scripts.get_revision(value) is None for value in revisions):
                raise RuntimeError("未知 schema；禁止自动 stamp")
            # 生产迁移只接受已经越过 #90 安全切换的库。
            for value in revisions:
                ancestors = {r.revision for r in scripts.walk_revisions(base="base", head=value)}
                if ISSUE90_SAFE_HEAD not in ancestors:
                    raise RuntimeError("缺少已确认的数据切换基线")
            command.upgrade(cfg, "heads")
        finally:
            engine.dispose()
        return
    if args.fresh_local or args.verify_local:
        from scripts.local_deploy.schema import initialize, verify_schema
        root = Path(__file__).resolve().parents[2]
        (initialize if args.fresh_local else verify_schema)(root, database_url)
        return

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        tables = set(inspect(engine).get_table_names())
        has_version = False
        if "alembic_version" in tables:
            with engine.connect() as connection:
                has_version = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version LIMIT 1"
                ).first() is not None
    finally:
        engine.dispose()

    config = Config("alembic.ini")
    if "papers" in tables and not has_version:
        print(f"检测到已导入数据库，标记迁移基线 {IMPORTED_SCHEMA_BASELINE}")
        command.stamp(config, IMPORTED_SCHEMA_BASELINE)
    target = "head" if os.environ.get("ISSUE90_CONTRACT_CONFIRMED") == "1" else ISSUE90_SAFE_HEAD
    command.upgrade(config, target)


if __name__ == "__main__":
    main()
