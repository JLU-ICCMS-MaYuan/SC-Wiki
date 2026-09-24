"""仅从授权来源文件按需渲染证据页面；不保存截图。"""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from backend import models
from backend.rag.config import settings
from .document_ir import DocumentIR
from .document_parsers import DocumentSource


def region_document(session, target, target_id, file_id, user):
    if target == "upload":
        from backend.ingest.upload_tasks import get_state, data_path
        state = get_state(target_id)
        if not state or state.get("is_shadow"):
            raise HTTPException(404, detail="上传任务不存在")
        if state.get("user_id") != user.id and not (user.role in {"admin","superadmin"} and user.is_approved):
            raise HTTPException(403, detail="无权查看此文档")
        files = state.get("files") or [{"file_id":"main","stored_path":state.get("file_path"),"sha256":state.get("file_sha256")}]
        source = next((f for f in files if f["file_id"] == file_id), None)
        if source is None:
            raise HTTPException(404, detail="来源文件不存在")
        # file_id 来自已认证的服务端 manifest，不能把客户端路径交给文件系统。
        ir_path = data_path("review_artifacts") / target_id / "document_ir" / f"{source['file_id']}.json"
        if not ir_path.is_file():
            return None, None, None
        ir = DocumentIR.model_validate_json(ir_path.read_text(encoding="utf-8"))
        if ir.source_file_id != source["file_id"]:
            raise HTTPException(409, detail="文档来源已变化")
        return ir, Path(source["stored_path"]), source.get("sha256")
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
    if run is None:
        return None, None, None
    path = Path(file.stored_path)
    if not path.is_absolute():
        path = settings.sc_wiki_data_dir / path
    return DocumentIR.model_validate(run.document_json), path, file.sha256


def render_region(ir: DocumentIR | None, path: Path | None, expected_hash, *, quote: str, pdf_page: int | None, block_id: str | None = None):
    if ir is None:
        return {"status":"legacy_text","image":None,"message":"此来源没有区域定位，可继续核对页码与原文。"}
    matches = [block for block in ir.blocks if (block_id is None or block.block_id == block_id)
               and (pdf_page is None or block.pdf_page == pdf_page)
               and " ".join(quote.split()) in " ".join(block.text.split())]
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
            scale = min(1.5,1600/max(page.rect.width,page.rect.height))
            pixels = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            page_info = next(p for p in ir.pages if p.pdf_page==block.pdf_page)
            if abs(page_info.width-page.rect.width)>1 or abs(page_info.height-page.rect.height)>1:
                raise ValueError("page geometry mismatch")
            x0,y0,x1,y1=block.bbox
            result.update(status="located",image="data:image/png;base64,"+base64.b64encode(pixels.tobytes("png")).decode(),
                region=[x0/page.rect.width,y0/page.rect.height,(x1-x0)/page.rect.width,(y1-y0)/page.rect.height])
    except Exception:
        result.update(status="render_unavailable",message="原 PDF 暂不可渲染或来源已变化，文本证据仍可查看。")
    return result
