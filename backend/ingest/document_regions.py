"""仅从授权来源文件按需渲染证据页面；不保存截图。"""
from __future__ import annotations

from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import select
from backend import models
from backend.storage.paths import resolve_file
from backend.storage.files import FileNotFound as StorageFileNotFound
from .document_ir import DocumentIR
from .document_parsers import DocumentSource
from .pdf_evidence_crops import DPI, render_evidence_crops


def region_document(session, target, target_id, file_id, user):
    if target == "upload":
        from backend.ingest.upload_tasks import available_published_path, get_state, data_path
        state = get_state(target_id)
        if not state or state.get("is_shadow"):
            raise HTTPException(404, detail="上传任务不存在")
        if state.get("user_id") != user.id and not (user.role in {"admin","superadmin"} and user.is_approved):
            raise HTTPException(403, detail="无权查看此文档")
        files = state.get("files") or [{"file_id":"main","stored_path":state.get("file_path"),
                                         "sha256":state.get("file_sha256"), "size":state.get("file_size")}]
        source = next((f for f in files if f["file_id"] == file_id), None)
        if source is None:
            raise HTTPException(404, detail="来源文件不存在")
        # file_id 来自已认证的服务端 manifest，不能把客户端路径交给文件系统。
        ir_path = data_path("review_artifacts") / target_id / "document_ir" / f"{source['file_id']}.json"
        try:
            ir_path = available_published_path(target_id, ir_path)
        except (StorageFileNotFound, FileNotFoundError):
            # 区域IR是可选产物；旧任务仍可从同一授权原PDF的文字层可靠定位。
            ir_path = None
        if ir_path is None or not ir_path.is_file():
            if not source.get("stored_path"):
                return None, None, None
            path = resolve_file(str(source["stored_path"]), size=int(source.get("size") or 0),
                                sha256=str(source.get("sha256") or ""), namespace=target_id)
            return None, path if path.suffix.lower() == ".pdf" else None, source.get("sha256")
        ir = DocumentIR.model_validate_json(ir_path.read_text(encoding="utf-8"))
        if ir.source_file_id != source["file_id"]:
            raise HTTPException(409, detail="文档来源已变化")
        return ir, resolve_file(str(source["stored_path"]), size=int(source.get("size") or 0),
                                sha256=str(source.get("sha256") or ""), namespace=target_id), source.get("sha256")
    if target == "revision":
        from backend.services.paper_revisions import revision_snapshot
        revision_snapshot(session, target_id, user.id)  # 复用返修所有权和版本核对。
        draft = session.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == target_id))
        paper_id = draft.paper_id
    elif target == "paper" and target_id.isdigit():
        paper_id = int(target_id)
    else:
        raise HTTPException(400, detail="文档目标无效")
    paper = session.get(models.Paper, paper_id)
    if paper is None:
        raise HTTPException(404, detail="论文不存在")
    if (paper.uploaded_by_user_id != user.id
            and not (user.role in {"admin","superadmin"} and user.is_approved)):
        raise HTTPException(403, detail="无权查看此文档")
    if not file_id.isdigit():
        return None, None, None
    file = session.scalar(select(models.PaperFile).where(models.PaperFile.id == int(file_id),
        models.PaperFile.paper_id == paper.id, models.PaperFile.paper_revision == paper.content_revision))
    if file is None:
        raise HTTPException(404, detail="当前论文版本没有此文件")
    run = session.scalar(select(models.PaperDocumentParserRun).where(
        models.PaperDocumentParserRun.paper_file_id == file.id,
        models.PaperDocumentParserRun.paper_revision == paper.content_revision).order_by(models.PaperDocumentParserRun.id.desc()))
    if not file.stored_path:
        return None, None, None
    path = resolve_file(str(file.stored_path), size=int(file.size), sha256=str(file.sha256),
                        media_type=str(file.media_type or "application/pdf"), namespace=str(paper_id))
    if run is None:
        return None, path if path.suffix.lower() == ".pdf" else None, file.sha256
    return DocumentIR.model_validate(run.document_json), path, file.sha256


def _legacy_pdf_region(path: Path | None, expected_hash: str | None, quote: str, pdf_page: int | None):
    fallback = {"status": "legacy_text", "image": None,
                "message": "旧解析任务没有保存区域坐标；原文引句仍可核对。"}
    if not path or not expected_hash or not quote.strip():
        return fallback
    try:
        if not path.is_file() or DocumentSource(path, "legacy").resolved_sha256() != expected_hash:
            raise ValueError("来源 PDF 已变化或不可用")
        import pymupdf
        with pymupdf.open(path) as pdf:
            needle = " ".join(quote.split())
            matches = []
            occurrences = 0
            page_texts = [" ".join(page.get_text("text").split()).casefold() for page in pdf]
            for page, text in zip(pdf, page_texts):
                # 旧 Markdown 的页码可能由相邻段落继承；原 PDF 中的唯一匹配优先。
                count = text.count(needle.casefold())
                occurrences += count
                if count == 1:
                    matches.append((page.number, page.search_for(quote)))
            if occurrences == 0:
                spanning = []
                for index in range(len(pdf) - 1):
                    combined = page_texts[index] + " " + page_texts[index + 1]
                    start = combined.find(needle.casefold())
                    boundary = len(page_texts[index])
                    if start < 0 or combined.count(needle.casefold()) != 1 or not start < boundary < start + len(needle):
                        continue
                    first_quote = needle[:boundary - start].strip()
                    second_quote = needle[boundary - start + 1:].strip()
                    if min(len(first_quote), len(second_quote)) < 12:
                        continue
                    if page_texts[index].count(first_quote.casefold()) != 1 or page_texts[index + 1].count(second_quote.casefold()) != 1:
                        continue
                    first_boxes = pdf[index].search_for(first_quote)
                    second_boxes = pdf[index + 1].search_for(second_quote)
                    if first_boxes and second_boxes:
                        spanning.append([(index, first_boxes), (index + 1, second_boxes)])
                if len(spanning) == 1:
                    matches = spanning[0]
                    occurrences = 1
            if occurrences > 1 and pdf_page is not None:
                matches = [item for item in matches if item[0] + 1 == pdf_page]
                occurrences = len(matches)
            if occurrences != 1 or not matches or len(matches) > 2 or not all(item[1] for item in matches):
                return {"status": "unlocated", "image": None,
                        "message": "引句未在原 PDF 文本层唯一匹配，不能可靠高亮。"}
            crops = []
            for page_number, boxes in matches:
                page = pdf[page_number]
                if page.rotation:
                    return {"status": "unlocated", "image": None,
                            "message": "原 PDF 页面有旋转，当前无法可靠高亮引句。"}
                crops.extend(render_evidence_crops(page, boxes))
            first = crops[0]
            return {"status": "located", "image": first["image"], "pdf_page": matches[0][0] + 1,
                    "page_end": matches[-1][0] + 1,
                    "region": first["highlights"][0], "regions": first["highlights"],
                    "crops": crops, "dpi": DPI, "parser": {"name": "原 PDF 文本层检索", "mode": "legacy_text"},
                    "message": "引句在原 PDF 文本层唯一匹配。"}
    except Exception:
        return {"status": "render_unavailable", "image": None,
                "message": "原 PDF 暂不可渲染或来源已变化，原文引句仍可查看。"}


def render_region(ir: DocumentIR | None, path: Path | None, expected_hash, *, quote: str, pdf_page: int | None, block_id: str | None = None):
    if ir is None:
        return _legacy_pdf_region(path, expected_hash, quote, pdf_page) if not block_id else {
            "status": "legacy_text", "image": None, "message": "旧解析任务没有该图像区域的可靠定位。"}
    matches = [block for block in ir.blocks if (block_id is None or block.block_id == block_id)
               and (pdf_page is None or block.pdf_page == pdf_page)
               and (" ".join(quote.split()) in " ".join(block.text.split()) if quote.strip()
                    else block_id is not None and block.block_type in {"figure", "table", "table_cell"})]
    if len(matches) != 1:
        return {"status":"unlocated","image":None,"message":"引句无法唯一定位，保留文本证据。"}
    block = matches[0]
    result = {"status":"text_only","image":None,"pdf_page":block.pdf_page,"printed_page":block.printed_page,
              "bbox":block.bbox,"polygon":block.polygon,"table_id":block.table_id,"figure_id":block.figure_id,
              "file_id":ir.source_file_id,"source_version":ir.source_version,
              "source_kind":block.metadata.get("source_kind",ir.parser.get("mode")),
              "quote":quote,"parser":ir.parser,"block_id":block.block_id}
    if block.bbox is None:
        result["message"]="此块没有可靠区域坐标。"
        return result
    try:
        if not path or not path.is_file():
            raise ValueError("missing file")
        digest = DocumentSource(path,ir.source_file_id).resolved_sha256()
        if digest != ir.source_sha256 or expected_hash and digest != expected_hash:
            raise ValueError("stale file")
        import pymupdf
        with pymupdf.open(path) as pdf:
            page = pdf[block.pdf_page-1]
            page_info = next(p for p in ir.pages if p.pdf_page==block.pdf_page)
            if abs(page_info.width-page.rect.width)>1 or abs(page_info.height-page.rect.height)>1:
                raise ValueError("page geometry mismatch")
            x0,y0,x1,y1=block.bbox
            boxes = [pymupdf.Rect(x0, y0, x1, y1)]
            visual = block.block_type in {"figure", "table", "table_cell"}
            if visual:
                captions = []
                for candidate in ir.blocks:
                    if candidate.pdf_page != block.pdf_page or candidate.bbox is None or candidate.block_id == block.block_id:
                        continue
                    if candidate.block_type != "caption" and not re.match(r"^(?:fig\.?|figure|table)\s*\d", candidate.text.strip(), re.IGNORECASE):
                        continue
                    area = pymupdf.Rect(candidate.bbox)
                    overlap = max(0, min(area.x1, boxes[0].x1) - max(area.x0, boxes[0].x0))
                    gap = max(0, area.y0 - boxes[0].y1, boxes[0].y0 - area.y1)
                    if overlap >= 0.3 * min(area.width, boxes[0].width) and gap <= 50:
                        captions.append((gap, area))
                if captions:
                    boxes.append(min(captions, key=lambda item: item[0])[1])
            crops = render_evidence_crops(page, boxes, keep_together=visual,
                                          context_lines=0 if visual else 3)
            first = crops[0]
            result.update(status="located", image=first["image"], region=first["highlights"][0],
                          crops=crops, dpi=DPI)
    except Exception:
        result.update(status="render_unavailable",message="原 PDF 暂不可渲染或来源已变化，文本证据仍可查看。")
    return result
