"""只读发现历史文件及其数据库、Redis 和派生路径引用。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, and_, inspect, select, update

from backend.database import Base
from backend.storage.reference_inventory import FileInventoryError, scan_registered_files
from scripts.local_deploy.paths import PATH_FIELDS


TASK_ID = re.compile(r"^[0-9a-f]{32}$")
PATH_KEYS = PATH_FIELDS | {"storage_key"}


def relative_file(value: str, source_root: Path) -> str:
    """只接受源数据根内的已知业务目录，不猜测缺失路径。"""
    from backend.storage.reference_inventory import BUSINESS_ROOTS

    if not isinstance(value, str) or not value or "\\" in value:
        raise FileInventoryError("文件引用无效")
    path = Path(value)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(source_root.resolve())
        except ValueError as exc:
            raise FileInventoryError("文件引用位于源数据根之外") from exc
    if not path.parts or ".." in path.parts or path.parts[0] not in BUSINESS_ROOTS:
        raise FileInventoryError("文件引用未登记为业务文件")
    return path.as_posix()


def pointer_values(value: Any, prefix: tuple[str | int, ...] = ()):
    """只枚举登记字段名；自由文本、引句和科学数据不做字符串替换。"""
    if isinstance(value, dict):
        for key, item in value.items():
            pointer = (*prefix, key)
            if key in PATH_KEYS and isinstance(item, str) and item:
                yield pointer, item
            else:
                yield from pointer_values(item, pointer)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from pointer_values(item, (*prefix, index))


def set_pointer(document: Any, pointer: list[str | int], old: str, new: str) -> Any:
    """条件替换一处已登记引用，重复执行相同迁移为幂等。"""
    import copy

    result = copy.deepcopy(document)
    target = result
    for part in pointer[:-1]:
        target = target[part]
    current = target[pointer[-1]]
    if current == new:
        return result
    if current != old:
        raise FileInventoryError("引用内容已变化，拒绝覆盖")
    target[pointer[-1]] = new
    return result


def apply_database_references(manifest: dict[str, Any], session, *, rollback: bool = False) -> int:
    """在调用方的一个数据库事务内条件更新全部已登记引用。"""
    from backend import models  # noqa: F401  独立切换进程须注册业务表
    from backend import manual_evidence_models  # noqa: F401

    changed = 0
    for item in manifest["files"]:
        for reference in item["references"]:
            if reference["kind"] != "db":
                continue
            table = Base.metadata.tables[reference["table"]]
            column = table.c[reference["column"]]
            identity = reference["pk"]
            condition = and_(*(table.c[name] == value for name, value in identity.items()))
            current = session.execute(select(column).where(condition).with_for_update()).scalar_one_or_none()
            if current is None:
                raise FileInventoryError("被引用的数据库记录已消失")
            old, new = reference["old"], reference["new"]
            if rollback:
                old, new = new, old
            pointer = reference.get("pointer") or []
            if pointer:
                updated = set_pointer(current, pointer, old, new)
                if updated == current:
                    continue
            else:
                if current == new:
                    continue
                if current != old:
                    raise FileInventoryError("数据库文件引用在扫描后发生变化")
                updated = new
            session.execute(update(table).where(condition).values({column.name: updated}))
            changed += 1
    return changed


def apply_redis_references(manifest: dict[str, Any], client, *, rollback: bool = False) -> int:
    """逐键 WATCH 条件更新，Redis 原 TTL 保持不变。"""
    from redis.exceptions import WatchError

    references: dict[str, list[dict[str, Any]]] = {}
    for item in manifest["files"]:
        for reference in item["references"]:
            if reference["kind"] == "redis":
                references.setdefault(reference["key"], []).append(reference)
    changed = 0
    for key, entries in references.items():
        while True:
            with client.pipeline(transaction=True) as pipeline:
                try:
                    pipeline.watch(key)
                    raw = pipeline.get(key)
                    if raw is None:
                        raise FileInventoryError("Redis 草稿在迁移窗口内消失")
                    original = json.loads(raw)
                    document = original
                    for entry in entries:
                        old, new = entry["old"], entry["new"]
                        if rollback:
                            old, new = new, old
                        document = set_pointer(document, entry["pointer"], old, new)
                    if document == original:
                        break
                    pipeline.multi()
                    pipeline.set(key, json.dumps(document, ensure_ascii=False), keepttl=True)
                    pipeline.execute()
                    changed += 1
                    break
                except WatchError:
                    continue
    return changed


def discover(source_root: Path, session, redis_client) -> dict[str, Any]:
    """只读扫描；任何未解释文件都会阻断清单创建。"""
    from backend import models  # noqa: F401  注册 ORM 表
    from backend import manual_evidence_models  # noqa: F401  注册人工证据表

    root = source_root.resolve()
    if not root.is_dir():
        raise FileInventoryError("源数据目录不存在")
    referenced: dict[str, list[dict[str, Any]]] = {}
    target_keys: dict[str, str] = {}
    task_ids: set[str] = set()

    def add(value: str, reference: dict[str, Any], *, source_path: str | None = None,
            target_key: str | None = None) -> None:
        relative = relative_file(source_path or value, root)
        key = target_key or relative
        if key in target_keys.values() and target_keys.get(relative) != key:
            raise FileInventoryError("多个源文件映射到同一对象键")
        if relative in target_keys and target_keys[relative] != key:
            raise FileInventoryError("同一文件存在冲突的对象键")
        target_keys[relative] = key
        referenced.setdefault(relative, []).append({"old": value, "new": key, **reference})

    # 普通列与包含路径字段的 JSON 列统一按 ORM 元数据遍历；不读取全文字符串作为路径。
    existing = set(inspect(session.bind).get_table_names())
    for table in Base.metadata.tables.values():
        if table.name not in existing:
            continue
        primary = list(table.primary_key.columns)
        json_columns = [column for column in table.columns if isinstance(column.type, JSON)]
        plain_columns = [column for column in table.columns if column.name == "stored_path"]
        if table.name == "users":
            plain_columns.extend(column for column in table.columns if column.name == "avatar_key")
        selected = list(dict.fromkeys([*primary, *json_columns, *plain_columns]))
        if not selected:
            continue
        for row in session.execute(select(*selected)).mappings():
            identity = {column.name: row[column.name] for column in primary}
            if table.name == "scientific_upload_drafts":
                task_ids.add(str(identity["task_id"]))
            for column in plain_columns:
                value = row[column.name]
                if not value:
                    continue
                old = str(value)
                if table.name == "users" and column.name == "avatar_key" and "/" not in old:
                    add(old, {"kind": "db", "table": table.name, "pk": identity,
                              "column": column.name, "pointer": []},
                        source_path=f"avatars/{old}", target_key=f"avatars/{old}")
                elif table.name == "users" and column.name == "avatar_key" and old.startswith("files/avatars/"):
                    add(old, {"kind": "db", "table": table.name, "pk": identity,
                              "column": column.name, "pointer": []},
                        source_path=f"avatars/{old}", target_key=old)
                else:
                    add(old, {"kind": "db", "table": table.name, "pk": identity,
                              "column": column.name, "pointer": []})
            for column in json_columns:
                document = row[column.name]
                for pointer, value in pointer_values(document):
                    add(value, {"kind": "db", "table": table.name, "pk": identity,
                                "column": column.name, "pointer": list(pointer)})
            if table.name == "scientific_manual_evidence":
                for item in row.get("items") or []:
                    if item.get("kind") == "text":
                        continue
                    if not TASK_ID.fullmatch(str(item.get("id") or "")):
                        raise FileInventoryError("人工证据文件身份无效")
                    add(f"manual_evidence/{identity['id']}/{item['id']}",
                        {"kind": "derived", "table": table.name, "pk": identity})

    # 论文审核结果可能在提交后不再保存 Redis 草稿，但 Paper 仍持有上传任务 ID。
    if "papers" in existing and "upload_task_id" in Base.metadata.tables["papers"].columns:
        paper = Base.metadata.tables["papers"]
        task_ids.update(str(value) for value in session.scalars(select(paper.c.upload_task_id)) if value)

    for key in redis_client.scan_iter(match="upload:*"):
        name = key.decode() if isinstance(key, bytes) else str(key)
        match = re.fullmatch(r"upload:([0-9a-f]{32}):(state|draft)", name)
        if match is None:
            continue
        task_ids.add(match.group(1))
        raw = redis_client.get(key)
        if not raw:
            continue
        document = json.loads(raw)
        for pointer, value in pointer_values(document):
            add(value, {"kind": "redis", "key": name, "pointer": list(pointer)})

    def add_tree(directory: Path, description: str) -> None:
        if directory.exists():
            for path in directory.rglob("*"):
                if path.name == ".DS_Store" or path.name.startswith("._"):
                    continue
                if path.is_file() or path.is_symlink():
                    add(path.relative_to(root).as_posix(), {"kind": "derived", "owner": description})

    for task_id in task_ids:
        if not TASK_ID.fullmatch(task_id):
            raise FileInventoryError("任务 ID 格式无效")
        add_tree(root / "review_artifacts" / task_id, f"task:{task_id}")
        add_tree(root / "parsed_markdown" / task_id, f"task:{task_id}")
        markdown = root / "parsed_markdown" / f"{task_id}.md"
        if markdown.exists():
            add(markdown.relative_to(root).as_posix(), {"kind": "derived", "owner": f"task:{task_id}"})
        add_tree(root / "upload_PDFs" / task_id, f"task:{task_id}")

    # 旧 Redis 任务到期后仍可能留下按任务 ID 命名的产物；保留为不可直接访问的历史对象。
    for name in ("upload_PDFs", "review_artifacts", "parsed_markdown"):
        directory = root / name
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_dir() and TASK_ID.fullmatch(child.name) and child.name not in task_ids:
                add_tree(child, f"legacy-orphan:{child.name}")
            elif name == "parsed_markdown" and child.is_file() and child.suffix == ".md" and TASK_ID.fullmatch(child.stem):
                add(child.relative_to(root).as_posix(), {"kind": "derived", "owner": f"legacy-orphan:{child.stem}"})

    # 候选附件的元数据与正文按同一 task_id 配对；缺一项由预检阻断。
    candidates = root / "upload_PDFs" / "candidates"
    if candidates.is_dir():
        for metadata in candidates.glob("*/*.json"):
            if not TASK_ID.fullmatch(metadata.stem):
                raise FileInventoryError("候选附件元数据文件名无效")
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            if str(payload.get("task_id")) != metadata.stem:
                raise FileInventoryError("候选附件任务身份不一致")
            matches = [path for path in metadata.parent.glob(metadata.stem + ".*")
                       if path != metadata and path.is_file()]
            if len(matches) != 1:
                raise FileInventoryError("候选附件缺失或不唯一")
            for path in (metadata, matches[0]):
                add(path.relative_to(root).as_posix(), {"kind": "derived", "owner": f"candidate:{metadata.stem}"})

    # 富化输出与早期上传目录中的非引用文件也属于当前业务数据，按目录保留。
    for name in ("clean_results", "uploads"):
        add_tree(root / name, name)

    files = scan_registered_files(root, set(referenced))
    return {"format_version": 1, "source_root": str(root),
            "files": [{**asdict(item), "key": target_keys[item.relative_path],
                       "references": referenced[item.relative_path], "stage": "discovered"}
                      for item in files],
            "task_count": len(task_ids)}
