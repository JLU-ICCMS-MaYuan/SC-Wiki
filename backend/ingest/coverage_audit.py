"""Document IR 覆盖审计。审计结果用于停止条件，不负责写入科学数据。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .claim_evidence import Claim
from .document_ir import DocumentIR


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "incomplete"
    processed_pages: list[int] = Field(default_factory=list)
    empty_pages: list[int] = Field(default_factory=list)
    table_rows: dict[str, int] = Field(default_factory=dict)
    figure_count: int = 0
    formula_count: int = 0
    suspected_result_blocks: list[str] = Field(default_factory=list)
    covered_claim_ids: list[str] = Field(default_factory=list)
    uncovered_candidates: list[str] = Field(default_factory=list)
    truncation_signals: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    checker_version: str = "1"
    requires_human: bool = False


def audit_coverage(ir: DocumentIR, claims: list[Claim] | None = None, *, truncated: bool = False) -> CoverageReport:
    pages = {page.pdf_page for page in ir.pages}
    blocks_by_page = {page: [block for block in ir.blocks if block.pdf_page == page] for page in pages}
    covered = []
    uncovered = []
    for claim in claims or []:
        if claim.evidences:
            covered.append(claim.claim_id)
        else:
            uncovered.append(claim.claim_id)
    signals = ["output_truncated"] if truncated else []
    empty = sorted(page for page, blocks in blocks_by_page.items() if not blocks)
    status = "complete" if not signals and not uncovered else "incomplete"
    return CoverageReport(
        status=status,
        processed_pages=sorted(pages),
        empty_pages=empty,
        table_rows={table.table_id: table.row_count for table in ir.tables},
        figure_count=len(ir.figures),
        formula_count=len(ir.formulas),
        suspected_result_blocks=[block.block_id for block in ir.blocks if any(token in block.text.lower() for token in ("tc", "critical temperature", "superconducting"))],
        covered_claim_ids=covered,
        uncovered_candidates=uncovered,
        truncation_signals=signals,
        limitations=list(ir.coverage.get("limitations", [])) if isinstance(ir.coverage, dict) else [],
        requires_human=bool(signals or uncovered),
    )
