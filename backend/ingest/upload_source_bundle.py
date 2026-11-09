"""上传任务各生成器共用当前论文的有效文本来源。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .property_evidence import source_chunks


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
        # 保留兼容参数，但不能凭References标题切掉后续SI图、表或附录。
        # 本文/引用工作的科学范围由既有模型判断，程序不把未读内容当作不存在。
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


def paper_source_chunks(task_id: str, state: dict[str, Any], root: Path) -> list[dict]:
    """论文先行只读原解析文本；后加的图像派生事实不能改变已完成论文阶段的输入。"""
    from .upload_tasks import artifact_directory
    from .chart_cache import load_document_ir
    from .upload_jobs import _ir_to_markdown
    chunks = []
    manifest = {str(item['file_id']): item for item in state.get('files') or []}
    for source in text_sources(task_id, state, root):
        item = manifest.get(source['file_id'], {})
        path = artifact_directory(task_id)/'document_ir'/f"{source['file_id']}.json"
        if str(item.get('kind') or 'pdf').lower() == 'pdf' and path.is_file():
            ir = load_document_ir(path)
            if item.get('sha256') and ir.source_sha256 != item['sha256']:
                raise ValueError('论文阶段IR与当前原文件摘要不一致')
            ir.blocks = [b for b in ir.blocks if 'chart_reading' not in b.metadata and 'chart_unresolved' not in b.metadata]
            content = _ir_to_markdown(ir)
        else:
            content = source['content']
        chunks.extend({**chunk, 'source_name': source['source_name'], 'file_role': source['role']}
                      for chunk in source_chunks(content, source['file_id']))
    return chunks
