"""Claim/Evidence 中间契约及 Document IR 定位校验。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .document_ir import DocumentIR


CLAIM_RULE_VERSION = "2"


class BasisKind(StrEnum):
    PAPER_QUOTE = "paper_quote"
    PAPER_INFERENCE = "paper_inference"
    GENERAL_KNOWLEDGE = "general_knowledge"


class SourceKind(StrEnum):
    TEXT_LAYER = "text_layer"
    OCR = "ocr"
    VISION = "vision"
    DERIVED = "derived"
    EXTERNAL_METADATA = "external_metadata"
    EXTERNAL_BACKGROUND = "external_background"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


class EvidenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    file_id: str = Field(min_length=1)
    source_version: int = Field(default=1, ge=1)
    pdf_page: int = Field(ge=1)
    printed_page: int | None = None
    block_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    polygon: list[tuple[float, float]] | None = None
    quote: str = ""
    parser: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    source_kind: SourceKind = SourceKind.TEXT_LAYER
    table_id: str | None = None
    figure_id: str | None = None


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    claim_id: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    value: Any = None
    raw_value: Any = None
    basis_kind: BasisKind
    source_kind: SourceKind
    status: ClaimStatus = ClaimStatus.CANDIDATE
    confidence: float | None = Field(default=None, ge=0, le=1)
    rule_version: str = CLAIM_RULE_VERSION
    content_hash: str | None = None
    evidences: list[EvidenceLocator] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == ClaimStatus.VALIDATED and not self.evidences:
            raise ValueError("validated Claim 必须至少包含一条 Evidence")
        return self


class ClaimValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    valid: bool
    reasons: list[str] = Field(default_factory=list)
    claim: Claim


def _contains_quote(text: str, quote: str) -> bool:
    normalized_text = " ".join((text or "").split())
    normalized_quote = " ".join((quote or "").split())
    return bool(normalized_quote) and normalized_quote in normalized_text


def locate_evidence(evidence: EvidenceLocator, ir: DocumentIR) -> tuple[EvidenceLocator | None, str | None]:
    """只从受信任 IR 回填位置；原句、来源类型和解析版本都必须一致。"""
    if evidence.file_id != ir.source_file_id:
        return None, "Evidence 文件不属于当前 DocumentIR"
    if evidence.source_version != ir.source_version:
        return None, "Evidence source_version 与 DocumentIR 不一致"
    if evidence.pdf_page not in {page.pdf_page for page in ir.pages}:
        return None, "Evidence PDF 页码不存在"
    if evidence.parser != ir.parser.get("name") or evidence.parser_version != ir.parser.get("version"):
        return None, "Evidence 解析器或版本不一致"
    if not evidence.quote.strip():
        return None, "Evidence quote 不能为空"
    if evidence.block_id:
        blocks = [b for b in ir.blocks if b.block_id == evidence.block_id]
    else:
        blocks = [b for b in ir.blocks if b.pdf_page == evidence.pdf_page and _contains_quote(b.text, evidence.quote)]
    if len(blocks) != 1:
        return None, "Evidence 块不存在或引句不能唯一定位"
    block = blocks[0]
    if block.metadata.get("estimated"):
        return None, "视觉估读不能作为论文直接报告值"
    if block.pdf_page != evidence.pdf_page or not _contains_quote(block.text, evidence.quote):
        return None, "Evidence 页码或引句与块不一致"
    expected_kind = block.metadata.get("source_kind") or {
        "text": "text_layer", "ocr": "ocr", "vlm": "vision",
    }.get(ir.parser.get("mode", "text"))
    if evidence.source_kind != expected_kind:
        return None, "Evidence 来源类型与解析结果不一致"
    if evidence.printed_page is not None and evidence.printed_page != block.printed_page:
        return None, "Evidence 印刷页码不一致"
    for field in ("bbox", "polygon", "table_id", "figure_id"):
        supplied = getattr(evidence, field)
        if supplied is not None and supplied != getattr(block, field):
            return None, f"Evidence {field} 与原文块不一致"
    values = evidence.model_dump()
    values.update(block_id=block.block_id, bbox=block.bbox, polygon=block.polygon,
                  printed_page=block.printed_page, table_id=block.table_id, figure_id=block.figure_id)
    return EvidenceLocator.model_validate(values), None


def validate_claim(claim: Claim, ir: DocumentIR | dict[str, DocumentIR]) -> ClaimValidation:
    """validated 仅表示已定位；科学语义仍须经过既有来源核对与人工审核。"""
    documents = {ir.source_file_id: ir} if isinstance(ir, DocumentIR) else ir
    reasons, located = [], []
    if claim.basis_kind != BasisKind.PAPER_QUOTE:
        reasons.append("论文推断或通用知识只能作为待采用建议")
    if claim.source_kind not in {SourceKind.TEXT_LAYER, SourceKind.OCR, SourceKind.VISION}:
        reasons.append("科学 Claim 必须来自上传文件")
    if not claim.evidences:
        reasons.append("Claim 缺少 Evidence")
    for evidence in claim.evidences:
        document = documents.get(evidence.file_id)
        if document is None:
            reasons.append("Evidence 文件不属于当前文档集合")
            continue
        locator, reason = locate_evidence(evidence, document)
        if reason:
            reasons.append(reason)
        else:
            located.append(locator)
    # 每个证据可以有各自的 text/OCR 来源；Claim 汇总来源必须出现在实际证据中。
    if located and claim.source_kind not in {e.source_kind for e in located}:
        reasons.append("Claim 来源类型与 Evidence 不一致")
    valid = not reasons
    values = claim.model_dump()
    values.update(status=ClaimStatus.VALIDATED if valid else ClaimStatus.UNCERTAIN, rule_version=CLAIM_RULE_VERSION)
    if valid:
        values["evidences"] = located
    return ClaimValidation(valid=valid, reasons=list(dict.fromkeys(reasons)), claim=Claim.model_validate(values))
