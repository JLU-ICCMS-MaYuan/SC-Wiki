"""私有生产备份组件：S3 对象与业务 Redis 状态，完整回读后才声明成功。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    path.chmod(0o600)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_client():
    from backend.storage.files import create_storage, S3FileStorage
    storage = create_storage()
    if not isinstance(storage, S3FileStorage):
        raise ValueError("需要显式 S3 配置")
    return storage.client, storage.bucket


def list_objects(client, bucket):
    return {item["Key"]: item["Size"]
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket)
            for item in page.get("Contents", [])}


def export_objects(target):
    client, bucket = object_client()
    before = list_objects(client, bucket)
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    objects = []
    for index, (key, size) in enumerate(sorted(before.items())):
        # 本地文件名不使用远端 key，防止对象键变成文件系统路径。
        filename = f"{index:08d}.blob"
        response = client.get_object(Bucket=bucket, Key=key)
        path = target / filename
        with path.open("xb") as stream, response["Body"] as body:
            for chunk in iter(lambda: body.read(1024 * 1024), b""):
                stream.write(chunk)
        path.chmod(0o600)
        digest = sha256(path)
        metadata = response.get("Metadata", {})
        if path.stat().st_size != size or metadata.get("sha256") != digest:
            raise ValueError("对象内容、长度或摘要元数据不一致")
        objects.append({"key": key, "file": filename, "size": size, "sha256": digest,
                        "content_type": response.get("ContentType", "application/octet-stream"),
                        "metadata": metadata})
    if list_objects(client, bucket) != before:
        raise ValueError("导出期间对象集合发生变化")
    write_json(target / "manifest.json", {"format": 1, "objects": objects})
    verify_objects(target, remote=True)
    return {"objects": len(objects), "bytes": sum(before.values())}


def object_manifest(source):
    data = json.loads((source / "manifest.json").read_text())
    if data.get("format") != 1 or not isinstance(data.get("objects"), list):
        raise ValueError("对象备份格式无效")
    keys, filenames = set(), set()
    from backend.storage.files import validate_key
    for item in data["objects"]:
        validate_key(item["key"])
        if (item["key"] in keys or item["file"] in filenames
                or not re.fullmatch(r"[0-9]{8}\.blob", item["file"])):
            raise ValueError("对象清单包含重复或非法路径")
        keys.add(item["key"]); filenames.add(item["file"])
        path = source / item["file"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["size"]:
            raise ValueError("备份文件缺失或长度错误")
        if sha256(path) != item["sha256"] or item["metadata"].get("sha256") != item["sha256"]:
            raise ValueError("备份摘要错误")
    return data["objects"]


def verify_objects(source, *, remote=False):
    items = object_manifest(source)
    if remote:
        client, bucket = object_client()
        if list_objects(client, bucket) != {i["key"]: i["size"] for i in items}:
            raise ValueError("目标对象键集合或大小不一致")
        for item in items:
            response = client.get_object(Bucket=bucket, Key=item["key"])
            digest = hashlib.sha256()
            with response["Body"] as body:
                for chunk in iter(lambda: body.read(1024 * 1024), b""):
                    digest.update(chunk)
            if (digest.hexdigest() != item["sha256"]
                    or response.get("Metadata", {}) != item["metadata"]
                    or response.get("ContentType") != item["content_type"]):
                raise ValueError("对象完整回读或元数据核验失败")
    return {"verified_objects": len(items), "remote": remote}


def restore_objects(source):
    items = object_manifest(source)
    client, bucket = object_client()
    if list_objects(client, bucket):
        raise ValueError("对象恢复目标必须为空；不覆盖已有内容")
    for item in items:
        with (source / item["file"]).open("rb") as stream:
            client.put_object(Bucket=bucket, Key=item["key"], Body=stream,
                              ContentLength=item["size"], ContentType=item["content_type"],
                              Metadata=item["metadata"])
    return verify_objects(source, remote=True)


def redis_client():
    from redis import Redis
    return Redis.from_url(os.environ["REDIS_URL"], decode_responses=True,
                          socket_timeout=10, socket_connect_timeout=5)


def mysql_inventory():
    """在既有结构清单上增加与行顺序无关的内容摘要。"""
    from scripts.local_deploy.storage import mysql_inventory as structure, mysql_connection, identifier
    url = os.environ["DATABASE_URL"]
    result = structure(url)
    with mysql_connection(url) as connection, connection.cursor() as cursor:
        for name, table in result["tables"].items():
            cursor.execute("SELECT * FROM " + identifier(name))
            hashes = []
            for row in cursor:
                value = json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":"))
                hashes.append(hashlib.sha256(value.encode()).hexdigest())
            table["content_sha256"] = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()
    return result


def export_mysql_json(target):
    """补充 JSON 原文，避免 MySQL JSON 文本解析的浮点末位变化。"""
    from scripts.local_deploy.storage import mysql_connection, identifier
    tables = []
    with mysql_connection(os.environ["DATABASE_URL"]) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS "
                       "WHERE TABLE_SCHEMA=DATABASE() AND DATA_TYPE='json' ORDER BY TABLE_NAME,ORDINAL_POSITION")
        columns = {}
        for table, column in cursor.fetchall():
            columns.setdefault(table, []).append(column)
        for table, names in columns.items():
            cursor.execute("SHOW KEYS FROM " + identifier(table) + " WHERE Key_name='PRIMARY'")
            primary = [row[4] for row in sorted(cursor.fetchall(), key=lambda row: row[3])]
            if not primary:
                raise ValueError("JSON 备份表缺少主键")
            selected = ",".join(identifier(name) for name in [*primary, *names])
            cursor.execute("SELECT " + selected + " FROM " + identifier(table))
            rows = [{"key": list(row[:len(primary)]), "values": list(row[len(primary):])}
                    for row in cursor.fetchall()]
            tables.append({"table": table, "primary": primary, "columns": names, "rows": rows})
    write_json(target, {"format": 1, "tables": tables})
    return {"json_tables": len(tables)}


def numeric_json_changes(expected, actual, path="$"):
    """仅接受 JSON 文本导入中的浮点差异；结构、字符串或整数变化拒绝。"""
    import math
    if type(expected) is not type(actual):
        raise ValueError("JSON 类型不一致")
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            raise ValueError("JSON 字段集合不一致")
        return [item for key in expected for item in numeric_json_changes(
            expected[key], actual[key], path + "." + json.dumps(key, ensure_ascii=False))]
    if isinstance(expected, list):
        if len(expected) != len(actual):
            raise ValueError("JSON 列表长度不一致")
        return [item for index, (left, right) in enumerate(zip(expected, actual))
                for item in numeric_json_changes(left, right, f"{path}[{index}]")]
    if expected == actual:
        return []
    if isinstance(expected, float) and math.isfinite(expected) and math.isfinite(actual):
        # 仅允许相邻 double 的解析舍入误差，不把业务数据修改当作恢复修正。
        if abs(expected - actual) <= max(math.ulp(expected), math.ulp(actual)):
            return [(path, repr(expected))]
    raise ValueError("JSON 内容差异不属于可恢复的浮点解析舍入")


def restore_mysql_json(source):
    from scripts.local_deploy.storage import mysql_connection, identifier
    data = json.loads(source.read_text())
    if data.get("format") != 1:
        raise ValueError("JSON 补充备份格式无效")
    changed = 0
    with mysql_connection(os.environ["DATABASE_URL"]) as connection, connection.cursor() as cursor:
        connection.begin()
        try:
            for table in data["tables"]:
                primary, columns = table["primary"], table["columns"]
                selection = ",".join(identifier(name) for name in [*primary, *columns])
                cursor.execute("SELECT " + selection + " FROM " + identifier(table["table"]) + " FOR UPDATE")
                actual = {tuple(row[:len(primary)]): list(row[len(primary):]) for row in cursor.fetchall()}
                if set(actual) != {tuple(row["key"]) for row in table["rows"]}:
                    raise ValueError("恢复目标主键集合与备份不一致")
                for row in table["rows"]:
                    for column, expected, current in zip(columns, row["values"], actual[tuple(row["key"])]):
                        if expected == current:
                            continue
                        if expected is None or current is None:
                            raise ValueError("JSON 空值不一致")
                        changes = numeric_json_changes(json.loads(expected), json.loads(current))
                        where = " AND ".join(identifier(name) + "=%s" for name in primary)
                        if changes:
                            expression = "JSON_SET(" + identifier(column) + "," + ",".join(
                                "%s,CAST(%s AS DOUBLE)" for _ in changes) + ")"
                            parameters = [value for item in changes for value in item] + row["key"]
                            cursor.execute("UPDATE " + identifier(table["table"]) + " SET " +
                                           identifier(column) + "=" + expression + " WHERE " + where, parameters)
                            changed += len(changes)
                        cursor.execute("SELECT " + identifier(column) + " FROM " +
                                       identifier(table["table"]) + " WHERE " + where, row["key"])
                        if cursor.fetchone()[0] != expected:
                            raise ValueError("JSON 修复后原文仍不一致")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {"restored_float_values": changed}


def assert_no_jobs(client):
    from scripts.local_deploy.storage import assert_no_jobs as check
    check(client)


def export_redis(target):
    from scripts.local_deploy.storage import export_redis as export_tasks
    with redis_client() as client:
        payload = export_tasks(client)
        payload["format"] = 1
        payload["prop_name_map"] = client.hgetall("scwiki:prop-name-map")
        # 只保存明确业务状态；不携带 RQ pickle、模型临时凭据、验证码或锁。
        for task in payload["tasks"]:
            for suffix in ("state", "draft"):
                if isinstance(task.get(suffix), dict):
                    for key in ("job_id", "processing_job_id", "llm_config", "api_key"):
                        task[suffix].pop(key, None)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_json(target, payload)
        return {"tasks": len(payload["tasks"]), "prop_names": len(payload["prop_name_map"])}


def restore_redis(source):
    from scripts.local_deploy.storage import mysql_connection
    data = json.loads(source.read_text())
    if data.get("format") != 1:
        raise ValueError("Redis 备份格式无效")
    with mysql_connection(os.environ["DATABASE_URL"]) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users")
        users = {row[0] for row in cursor.fetchall()}
    with redis_client() as client:
        if client.dbsize():
            raise ValueError("Redis 恢复目标必须为空")
        for task in data["tasks"]:
            if not re.fullmatch(r"[a-f0-9]{32}", task["task_id"]) or task["state"]["user_id"] not in users:
                raise ValueError("任务身份或用户无效")
        restored = expired = 0
        for task in data["tasks"]:
            if not re.fullmatch(r"[a-f0-9]{32}", task["task_id"]) or task["state"]["user_id"] not in users:
                raise ValueError("任务身份或用户无效")
            deadline = task.get("state_expires_at")
            # PERSIST 后 JSON 中可能仍留有旧 cleanup_at；真实 Redis TTL 才是备份事实。
            deadlines = [float(deadline)] if deadline is not None else []
            if deadlines and min(deadlines) <= time.time():
                expired += 1
                continue
            with client.pipeline() as pipe:
                for suffix in ("state", "draft"):
                    value = task.get(suffix)
                    expiry = task.get(suffix + "_expires_at")
                    if suffix == "state" and deadlines:
                        expiry = min(deadlines)
                    if value is None or (expiry is not None and expiry <= time.time()):
                        continue
                    key = f"upload:{task['task_id']}:{suffix}"
                    pipe.set(key, json.dumps(value, ensure_ascii=False))
                    if expiry is not None:
                        pipe.pexpireat(key, int(expiry * 1000))
                pipe.zadd(f"upload:user:{task['state']['user_id']}:tasks",
                          {task["task_id"]: task["state"]["updated_at"]})
                pipe.execute()
            restored += 1
        if data.get("prop_name_map"):
            client.hset("scwiki:prop-name-map", mapping=data["prop_name_map"])
        client.save()
        return {"restored_tasks": restored, "expired_tasks": expired}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("action", choices=["objects-export", "objects-restore", "objects-verify",
                                           "redis-export", "redis-restore", "mysql-inventory",
                                           "mysql-json-export", "mysql-json-restore"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--remote", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if args.env_file:
        from scripts.local_deploy.config import parse_env
        os.environ.update(parse_env(args.env_file.read_text()))
    if args.action == "objects-export":
        result = export_objects(args.path)
    elif args.action == "objects-restore":
        result = restore_objects(args.path)
    elif args.action == "objects-verify":
        result = verify_objects(args.path, remote=args.remote)
    elif args.action == "redis-export":
        result = export_redis(args.path)
    elif args.action == "redis-restore":
        result = restore_redis(args.path)
    elif args.action == "mysql-json-export":
        result = export_mysql_json(args.path)
    elif args.action == "mysql-json-restore":
        result = restore_mysql_json(args.path)
    else:
        data = mysql_inventory()
        write_json(args.path, data)
        result = {"tables": len(data["tables"])}
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 外部 SDK 异常可能带地址/凭据；默认只显示异常类别。
        raise SystemExit("备份/恢复失败：" + (str(exc) if isinstance(exc, ValueError)
                                            else type(exc).__name__))
