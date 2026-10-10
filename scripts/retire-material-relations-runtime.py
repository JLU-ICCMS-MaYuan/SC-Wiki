"""#127：清理当前运行实例中的材料关系缓存、索引与旧图谱边。

先运行 --dry-run；停写后运行 --apply --database <数据库名>，随后执行 Alembic 迁移。
既有整库备份和冻结包不在本脚本范围内。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from sqlalchemy import inspect, text  # noqa: E402

from backend.database import engine  # noqa: E402
from backend.ingest.upload_tasks import data_path, redis_client  # noqa: E402
from backend.rag.config import settings  # noqa: E402


FIELD = "paper.material_relations"


def retired_item(value):
    if not isinstance(value, dict):
        return False
    for key in ("field", "field_path", "path"):
        path = value.get(key)
        if isinstance(path, str) and (path == FIELD or path.startswith(FIELD + "[")):
            return True
    fields = value.get("fields")
    return isinstance(fields, list) and any(
        isinstance(path, str) and (path == FIELD or path.startswith(FIELD + "[")) for path in fields
    )


def strip(value):
    if isinstance(value, dict):
        return {key: strip(item) for key, item in value.items()
                if key not in {"material_relations", FIELD} and not key.startswith(FIELD + "[")
                and not retired_item(item)}
    if isinstance(value, list):
        return [strip(item) for item in value if not retired_item(item)]
    return value


def database_ids():
    with engine.connect() as connection:
        inspector = inspect(connection)
        sources = []
        manual = []
        if inspector.has_table("scientific_evidence_sources"):
            sources = [int(row[0]) for row in connection.execute(text(
                "SELECT id FROM scientific_evidence_sources WHERE field_path = :path OR field_path LIKE :indexed"
            ), {"path": FIELD, "indexed": FIELD + "[%"})]
        if inspector.has_table("scientific_manual_evidence"):
            import hashlib
            item_key = hashlib.sha256(json.dumps(["paper", "material_relations"], ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            manual = [str(row[0]) for row in connection.execute(text(
                "SELECT id FROM scientific_manual_evidence WHERE item_key = :item_key"
            ), {"item_key": item_key})]
    return sources, manual


def redis_changes(apply):
    client = redis_client()
    changed = 0
    for key in client.scan_iter(match="upload:*:draft"):
        raw = client.get(key)
        if not raw:
            continue
        value = json.loads(raw)
        cleaned = strip(value)
        if cleaned != value:
            changed += 1
            if apply:
                client.set(key, json.dumps(cleaned, ensure_ascii=False), keepttl=True)
    return changed


def artifact_changes(apply):
    changed = 0
    for path in data_path("review_artifacts").rglob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        cleaned = strip(value)
        if cleaned != value:
            changed += 1
            if apply:
                temporary = path.with_suffix(path.suffix + ".retiring")
                temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temporary, path)
    return changed


def neo4j_changes(apply):
    from backend.rag.tools.neo4j import _driver

    with _driver().session() as session:
        relationship_types = set(session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").value())
        property_keys = set(session.run("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey").value())
        edges = (session.run("MATCH ()-[r:STUDIES]->() RETURN count(r) AS n").single()["n"]
                 if "STUDIES" in relationship_types else 0)
        properties = (session.run("MATCH (p:Paper) WHERE p.material_relations IS NOT NULL RETURN count(p) AS n").single()["n"]
                      if "material_relations" in property_keys else 0)
        if apply:
            if edges:
                session.run("MATCH ()-[r:STUDIES]->() DELETE r").consume()
            if properties:
                session.run("MATCH (p:Paper) REMOVE p.material_relations").consume()
    return edges, properties


def qdrant_changes(source_ids, apply):
    if not source_ids:
        return 0
    from qdrant_client.models import PointIdsList
    from backend.rag.vectordb import COLLECTION_NAME, _get_client

    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return 0
    if apply:
        client.delete(collection_name=COLLECTION_NAME,
                      points_selector=PointIdsList(points=[(1 << 62) + source_id for source_id in source_ids]),
                      wait=True)
    return len(source_ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--database", help="--apply 时必须与当前 DATABASE_URL 的数据库名完全一致")
    args = parser.parse_args()
    database = engine.url.database
    if args.apply and (not database or args.database != database):
        parser.error("--apply 必须指定当前 DATABASE_URL 的准确数据库名")
    print(f"目标数据库：{database}")
    source_ids, manual_ids = database_ids()
    print(f"正式材料关系来源：{len(source_ids)}；人工证据目录：{len(manual_ids)}")
    print(f"Redis 草稿：{redis_changes(args.apply)}")
    print(f"解析 JSON：{artifact_changes(args.apply)}")
    print(f"Qdrant 来源点：{qdrant_changes(source_ids, args.apply)}")
    edges, properties = neo4j_changes(args.apply)
    print(f"Neo4j STUDIES 边：{edges}；论文旧属性：{properties}")
    if args.apply:
        for evidence_id in manual_ids:
            directory = settings.sc_wiki_data_dir / "manual_evidence" / evidence_id
            if directory.exists():
                shutil.rmtree(directory)
        print("运行缓存、索引与图谱清理完成；请执行 Alembic 升级并复核残留。")


if __name__ == "__main__":
    main()
