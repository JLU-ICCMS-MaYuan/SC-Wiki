"""Document IR 随既有论文事务保存；区域关联始终在服务端重新定位。"""
from __future__ import annotations

from sqlalchemy import select
from backend import models
from .document_ir import DocumentIR, content_hash
from .claim_evidence import EvidenceLocator, locate_evidence


async def persist_document(session, paper, paper_file, ir: DocumentIR):
    if paper_file.paper_id != paper.id or paper_file.paper_revision != paper.content_revision:
        raise ValueError("文档文件不属于当前论文版本")
    if paper_file.sha256 != ir.source_sha256:
        raise ValueError("文档内容哈希与原文件不一致")
    document = ir.model_dump(mode="json")
    document["source_file_id"] = str(paper_file.id)
    run = models.PaperDocumentParserRun(paper_id=paper.id, paper_revision=paper.content_revision,
        paper_file_id=paper_file.id, parse_profile=ir.parse_profile, parser_name=ir.parser["name"],
        parser_version=ir.parser["version"], mode=ir.parser["mode"], status="succeeded",
        reading_state="ir_ready", model_version=ir.parser.get("model"), document_json=document)
    session.add(run)
    await session.flush()
    blocks = {}
    for block in ir.blocks:
        row = models.PaperDocumentBlock(paper_id=paper.id, paper_revision=paper.content_revision,
            paper_file_id=paper_file.id, parser_run_id=run.id, block_id=block.block_id,
            block_type=block.block_type.value, pdf_page=block.pdf_page, printed_page=block.printed_page,
            reading_order=block.reading_order, text=block.text, bbox_json=block.bbox,
            polygon_json=block.polygon, table_id=block.table_id, figure_id=block.figure_id,
            confidence=block.confidence, content_hash=block.content_hash, metadata_json=block.metadata)
        session.add(row)
        blocks[block.block_id] = row
    await session.flush()
    return run, blocks


async def link_document_evidence(session, paper_evidence, paper_chunk, run, blocks,
                                 *, block_id=None):
    if (paper_evidence.paper_id, paper_evidence.paper_revision) != (run.paper_id, run.paper_revision):
        raise ValueError("区域证据不能跨论文版本")
    if paper_chunk.id != paper_evidence.paper_chunk_id or paper_chunk.paper_file_id != run.paper_file_id:
        raise ValueError("区域证据不能跨来源文件")
    ir = DocumentIR.model_validate(run.document_json)
    candidates = [b for b in ir.blocks if (block_id is None or b.block_id == block_id)
                  and (paper_evidence.page_start or 1) <= b.pdf_page <= (paper_evidence.page_end or len(ir.pages))
                  and " ".join(paper_evidence.quote.split()) in " ".join(b.text.split())]
    if len(candidates) != 1:
        # 页码/引句旧来源仍有效；无法唯一定位时不伪造区域。
        return None
    block = candidates[0]
    source_kind = block.metadata.get("source_kind") or {"text": "text_layer", "ocr": "ocr", "vlm": "vision"}[run.mode]
    evidence = EvidenceLocator(file_id=str(run.paper_file_id), source_version=ir.source_version,
        pdf_page=block.pdf_page, block_id=block.block_id, quote=paper_evidence.quote,
        parser=run.parser_name, parser_version=run.parser_version, source_kind=source_kind)
    locator, error = locate_evidence(evidence, ir)
    if error:
        raise ValueError(error)
    key = content_hash(paper_evidence.id, run.id, block.block_id, locator.model_dump(mode="json"))
    existing = await session.scalar(select(models.PaperEvidenceLocator).where(models.PaperEvidenceLocator.locator_hash == key))
    if existing:
        return existing
    row = models.PaperEvidenceLocator(paper_evidence_id=paper_evidence.id, paper_id=run.paper_id,
        paper_revision=run.paper_revision, paper_file_id=run.paper_file_id, parser_run_id=run.id,
        document_block_id=blocks[block.block_id].id, pdf_page=locator.pdf_page,
        printed_page=locator.printed_page, bbox_json=locator.bbox, polygon_json=locator.polygon,
        table_id=locator.table_id, figure_id=locator.figure_id, quote=locator.quote,
        source_kind=locator.source_kind.value, parser_name=run.parser_name, parser_version=run.parser_version,
        source_version=ir.source_version, locator_hash=key)
    session.add(row)
    await session.flush()
    return row
