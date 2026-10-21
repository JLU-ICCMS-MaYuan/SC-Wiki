"""上传任务各生成器共用当前论文的有效文本来源。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .property_evidence import source_chunks


_REFERENCES = re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:references|bibliography|参考文献)\s*$")
_VALID_ID = re.compile(r"[\w-]+")


def text_sources(task_id: str, state: dict[str, Any], root: Path, *,
                 trim_references: bool = False) -> list[dict[str, str]]:
    """只把有效正文和补充材料交给本文字段；普通附件不混入。"""
    from .upload_tasks import available_published_path
    files = state.get("files") or [{"file_id": "main", "role": "main", "kind": state.get("file_kind") or "pdf",
                                    "original_filename": state.get("filename")}]
    result = []
    for item in files:
        if item.get("role") not in {"main", "supplementary"}:
            continue
        if str(item.get("kind") or "pdf").lower() not in {"pdf", "txt", "md"}:
            continue
        file_id = str(item.get("file_id") or "")
        if not _VALID_ID.fullmatch(file_id):
            continue
        path = available_published_path(task_id, root / task_id / f"{file_id}.md")
        if not path.is_file() and not state.get("files"):
            path = available_published_path(task_id, root / f"{task_id}.md")
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if trim_references and (match := _REFERENCES.search(content)):
            content = content[:match.start()]
        if content.strip():
            result.append({"file_id": file_id, "role": str(item["role"]),
                           "source_name": str(item.get("original_filename") or file_id), "content": content})
    return result


def task_source_chunks(task_id: str, state: dict[str, Any], root: Path, *,
                       trim_references: bool = False) -> list[dict]:
    chunks = []
    for source in text_sources(task_id, state, root, trim_references=trim_references):
        chunks.extend({**chunk, "source_name": source["source_name"], "file_role": source["role"]}
                      for chunk in source_chunks(source["content"], source["file_id"]))
    return chunks
