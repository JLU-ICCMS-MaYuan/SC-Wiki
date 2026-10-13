"""按原 PDF 文本层核对当前证据页码，旧解析页码只作为提示。"""

from __future__ import annotations

import copy
from backend.storage.paths import resolve_file
from .document_parsers import DocumentSource


def _files(session, snapshot):
    for item in snapshot.get("pdf_manifest") or []:
        if str(item.get("kind") or "").lower() != "pdf" or not item.get("stored_path"):
            continue
        yield (str(item["file_id"]), resolve_file(str(item["stored_path"]),
               size=int(item.get("size") or 0), sha256=str(item.get("sha256") or ""),
               media_type=str(item.get("media_type") or "application/pdf"),
               namespace=str(snapshot.get("target_id") or "")), item.get("sha256"))


def correct_pdf_source_pages(session, snapshot, results: dict) -> dict:
    """只修正当前结果；原文不唯一时保留引句并撤回无依据的支持状态。"""
    if snapshot["target"] == "paper" and snapshot.get("review_state", [None])[0] == "approved":
        return results
    import pymupdf
    pages = {}
    pdf_ids = set()
    for file_id, path, digest in _files(session, snapshot):
        pdf_ids.add(file_id)
        if not digest or not path.is_file() or DocumentSource(path, file_id).resolved_sha256() != digest:
            continue
        try:
            with pymupdf.open(path) as pdf:
                pages[file_id] = [" ".join(page.get_text("text").split()).casefold() for page in pdf]
        except Exception:
            continue
    corrected = dict(results)
    for record in snapshot["records"]:
        original = results.get(record["key"])
        if not original or not original.get("evidences"):
            continue
        result = copy.deepcopy(original)
        verified = 0
        for source in result["evidences"]:
            source_id = str(source.get("file_id"))
            document = pages.get(source_id)
            if source_id in pdf_ids and document is None:
                source["locator_status"] = "source_unavailable"
                continue
            if document is None or not source.get("quote"):
                continue
            if (record.get("field") in {"paper.title", "paper.authors"}
                    and source.get("origin_kind") == "verified_front_matter" and source.get("page_start") == 1):
                source["locator_status"] = "verified_front_matter"
                verified += 1
                continue
            needle = " ".join(str(source["quote"]).split()).casefold()
            hits = [number for number, page in enumerate(document, 1) for _ in range(page.count(needle))]
            if len(hits) == 1:
                source.update(page_start=hits[0], page_end=hits[0], locator_status="verified_text_layer")
                verified += 1
            elif source.get("block_id"):
                # 图表、OCR 块保留原有几何来源资格；不以文本层检索结果覆盖。
                verified += 1
            else:
                source["locator_status"] = "ambiguous" if hits else "not_in_pdf_text_layer"
        if result.get("status") == "supported" and not verified and all(
            str(source.get("file_id")) in pdf_ids for source in result["evidences"]):
            result.update(status="missing", reason="当前引句未在原 PDF 文本层唯一定位，请人工核对或重新解析。")
        corrected[record["key"]] = result
    return corrected


def current_pdf_results(session, snapshot, results: dict) -> dict:
    if not snapshot.get("pdf_manifest") or not snapshot.get("rule_version") or not all(
            "field" in record for record in snapshot.get("records") or []):
        return results
    from .pdf_front_matter import correct_front_matter_results
    return correct_pdf_source_pages(session, snapshot, correct_front_matter_results(session, snapshot, results))
