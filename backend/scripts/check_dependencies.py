"""只读依赖检查；不初始化数据库、集合、桶或 schema。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def check(role: str = "python", *, schema: bool = False) -> dict[str, bool]:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from redis import Redis

    result = {}
    def probe(name, operation):
        try:
            operation()
            result[name] = True
        except Exception:
            result[name] = False

    def mysql():
        sync = make_url(os.environ["DATABASE_URL"])
        async_url = make_url(os.environ["RAG_DATABASE_URL"])
        if (sync.host, sync.port, sync.database) != (async_url.host, async_url.port, async_url.database):
            raise ValueError("数据库目标不一致")
        engine = create_engine(sync, connect_args={"connect_timeout": 4})
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                actual = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            root = Path(__file__).resolve().parents[2]
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "alembic"))
            if actual != set(ScriptDirectory.from_config(config).get_heads()):
                raise ValueError("迁移版本不兼容")
            if schema:
                from scripts.local_deploy.schema import verify_schema
                verify_schema(root, str(sync.render_as_string(hide_password=False)))
        finally:
            engine.dispose()

    def redis():
        with Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=4, socket_timeout=4) as client:
            client.ping()

    def storage():
        from backend.storage.files import create_storage, S3FileStorage
        client = create_storage()
        if not isinstance(client, S3FileStorage):
            raise ValueError("生产必须配置对象存储")
        client.client.list_objects_v2(Bucket=client.bucket, MaxKeys=1)

    def qdrant():
        from backend.rag.qdrant_connection import create_qdrant_client
        with create_qdrant_client() as client:
            client.get_collections()

    def neo4j():
        from neo4j import GraphDatabase
        with GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
                                  connection_timeout=4, connection_acquisition_timeout=5) as driver:
            driver.verify_connectivity()

    def grobid():
        import requests
        response = requests.get(os.environ["GROBID_URL"].rstrip("/") + "/api/isalive", timeout=5)
        response.raise_for_status()

    for name, operation in (("mysql", mysql), ("redis", redis), ("storage", storage),
                            ("qdrant", qdrant), ("neo4j", neo4j)):
        probe(name, operation)
    if role == "compute":
        probe("grobid", grobid)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["python", "compute"], default="python")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    result = check(args.role, schema=args.schema)
    print(json.dumps(result))
    raise SystemExit(0 if all(result.values()) else 1)


if __name__ == "__main__":
    main()
