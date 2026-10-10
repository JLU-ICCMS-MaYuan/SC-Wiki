"""从主 PDF 首页核验标题与作者，不把末页引用当作书目主来源。"""

from __future__ import annotations

from pathlib import Path

from backend.rag.config import settings
from .document_parsers import DocumentSource


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def _main_file(session, snapshot):
    file = next((item for item in snapshot.get("pdf_manifest") or [] if item.get("role") == "main"
                 and str(item.get("kind") or "").lower() == "pdf"), None)
    if not file or not file.get("stored_path"):
        return None
    path = Path(file["stored_path"])
    return (path if path.is_absolute() else settings.sc_wiki_data_dir / path,
            file.get("sha256"), str(file["file_id"]), file.get("original_filename"))


def verified_title_source(session, snapshot) -> dict | None:
    record = next((item for item in snapshot["records"] if item["field"] == "paper.title"), None)
    title = str((record or {}).get("current_value") or "").strip()
    source = _main_file(session, snapshot) if title else None
    if source is None:
        return None
    path, digest, file_id, name = source
    if not digest or not path.is_file() or DocumentSource(path, file_id).resolved_sha256() != digest:
        return None
    matching = [chunk for chunk in snapshot["chunks"] if str(chunk["file_id"]) == file_id
                and _normalize(str(chunk.get("heading") or chunk.get("section") or "").lstrip("# ")) == _normalize(title)]
    if not matching:
        return None
    try:
        import pymupdf
        with pymupdf.open(path) as pdf:
            page = pdf[0]
            if _normalize(page.get_text("text")).count(_normalize(title)) != 1:
                return None
            boxes = page.search_for(title)
            if not boxes or min(box.y0 for box in boxes) >= page.rect.height * 0.5:
                return None
    except Exception:
        return None
    chunk = min(matching, key=lambda item: item["chunk_index"])
    return {"file_id": file_id, "source_name": name or file_id, "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk["chunk_index"], "page_start": 1, "page_end": 1,
            "quote": title, "origin_kind": "verified_front_matter"}


def verified_author_source(session, snapshot) -> dict | None:
    record = next((item for item in snapshot["records"] if item["field"] == "paper.authors"), None)
    title_record = next((item for item in snapshot["records"] if item["field"] == "paper.title"), None)
    authors = (record or {}).get("current_value")
    source = _main_file(session, snapshot) if isinstance(authors, list) and authors and title_record else None
    if source is None:
        return None
    path, digest, file_id, name = source
    if not digest or not path.is_file() or DocumentSource(path, file_id).resolved_sha256() != digest:
        return None
    try:
        import pymupdf
        with pymupdf.open(path) as pdf:
            title_boxes = pdf[0].search_for(str(title_record["current_value"] or ""))
            if not title_boxes:
                return None
            title_bottom = max(box.y1 for box in title_boxes)
            lines = [(line["bbox"], "".join(span["text"] for span in line["spans"]).strip())
                     for block in pdf[0].get_text("dict")["blocks"] for line in block.get("lines", [])]
            indexes = [i for i, (bbox, text) in enumerate(lines) if title_bottom < bbox[1] < title_bottom + 100
                       and any(_normalize(str(author)) in _normalize(text) for author in authors)]
            if not indexes or max(indexes) - min(indexes) > 4:
                return None
            quote = " ".join(text for _, text in lines[min(indexes):max(indexes) + 1])
            if not all(_normalize(str(author)) in _normalize(quote) for author in authors):
                return None
    except Exception:
        return None
    matching = [chunk for chunk in snapshot["chunks"] if str(chunk["file_id"]) == file_id
                and _normalize(quote) in _normalize(chunk["content"])]
    if len(matching) != 1:
        return None
    chunk = matching[0]
    return {"file_id": file_id, "source_name": name or file_id, "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk["chunk_index"], "page_start": 1, "page_end": 1,
            "quote": quote, "origin_kind": "verified_front_matter"}


def correct_front_matter_results(session, snapshot, results: dict) -> dict:
    """只替换当前待审字段来源；已批准历史保持原样。"""
    if snapshot["target"] == "paper" and snapshot.get("review_state", [None])[0] == "approved":
        return results
    record = next((item for item in snapshot["records"] if item["field"] == "paper.title"), None)
    if record is None or _main_file(session, snapshot) is None:
        return results
    source = verified_title_source(session, snapshot)
    result = dict(results.get(record["key"]) or {"status": "unchecked"})
    if source is not None:
        result.update(evidences=[source], stale=False, content_hash=record["content_hash"],
                      source_hash=record["source_hash"], rule_version=snapshot["rule_version"])
        if result.get("status") in {"supported", "missing", "unchecked"}:
            result.update(status="supported", reason="标题与正文主 PDF 首页逐字一致。")
    elif result.get("status") == "supported":
        result.update(status="missing", evidences=[], reason="正文主 PDF 首页标题未核实；末页引用不能代替首页标题。")
    corrected = {**results, record["key"]: result}
    author_record = next((item for item in snapshot["records"] if item["field"] == "paper.authors"), None)
    author_source = verified_author_source(session, snapshot)
    if author_record and author_source:
        author_result = dict(corrected.get(author_record["key"]) or {"status": "unchecked"})
        author_result.update(evidences=[author_source], stale=False,
                             content_hash=author_record["content_hash"], source_hash=author_record["source_hash"],
                             rule_version=snapshot["rule_version"])
        if author_result.get("status") in {"supported", "missing", "unchecked"}:
            author_result.update(status="supported", reason="作者姓名与正文主 PDF 首页署名一致。")
        corrected[author_record["key"]] = author_result
    return corrected
