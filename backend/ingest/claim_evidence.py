"""Claim/Evidence 中间契约及 Document IR 定位校验。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .document_ir import DocumentIR


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
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    value: Any = None
    raw_value: Any = None
    basis_kind: BasisKind
    source_kind: SourceKind
    status: ClaimStatus = ClaimStatus.CANDIDATE
    confidence: float | None = Field(default=None, ge=0, le=1)
    rule_version: str = "1"
    content_hash: str | None = None
    evidences: list[EvidenceLocator] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == ClaimStatus.VALIDATED and not self.evidences:
            raise ValueError("validated Claim 必须至少包含一条 Evidence")
        return self


class ClaimValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    reasons: list[str] = Field(default_factory=list)
    claim: Claim


def _contains_quote(text: str, quote: str) -> bool:
    normalized_text = " ".join((text or "").split())
    normalized_quote = " ".join((quote or "").split())
    return bool(normalized_quote) and normalized_quote in normalized_text


def validate_claim(claim: Claim, ir: DocumentIR) -> ClaimValidation:
    reasons: list[str] = []
    for evidence in claim.evidences:
        if evidence.file_id != ir.source_file_id:
            reasons.append("Evidence 文件不属于当前 DocumentIR")
            continue
        if evidence.source_version != ir.source_version:
            reasons.append("Evidence source_version 与 DocumentIR 不一致")
            continue
        if evidence.pdf_page > len(ir.pages) and ir.pages:
            reasons.append("Evidence PDF 页码超出文档范围")
            continue
        block = ir.block(evidence.block_id) if evidence.block_id else None
        if evidence.block_id and block is None:
            reasons.append(f"找不到 Evidence block_id：{evidence.block_id}")
            continue
        if block is not None:
            if block.pdf_page != evidence.pdf_page:
                reasons.append("Evidence 页码与块页码不一致")
            if evidence.quote and not _contains_quote(block.text, evidence.quote):
                reasons.append("Evidence quote 无法在对应块中定位")
        elif evidence.quote:
            page_text = "\n".join(b.text for b in ir.blocks if b.pdf_page == evidence.pdf_page)
            if not _contains_quote(page_text, evidence.quote):
                reasons.append("Evidence quote 无法在页面文本中定位")
    if claim.basis_kind == BasisKind.PAPER_QUOTE and not claim.evidences:
        reasons.append("paper_quote Claim 缺少 Evidence")
    valid = not reasons
    return ClaimValidation(valid=valid, reasons=reasons, claim=claim.model_copy(update={"status": ClaimStatus.VALIDATED if valid else ClaimStatus.UNCERTAIN}))
