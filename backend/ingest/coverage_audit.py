"""独立检查来源范围与结果覆盖；不能把有引句或模型声称读完当作覆盖完成。"""
from __future__ import annotations

import re
from pydantic import BaseModel, ConfigDict, Field
from .claim_evidence import Claim, validate_claim
from .document_ir import DocumentIR

RESULT_PATTERN = re.compile(r"\bT\s*[_c]?c\b|\bcritical\s+temperature\b|\bsuperconduct|临界温度|超导", re.I)


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
    checker_version: str = "2"
    requires_human: bool = True


def audit_coverage(ir: DocumentIR, claims: list[Claim] | None = None, *, truncated: bool = False,
                   processed_pages: list[int] | None = None) -> CoverageReport:
    pages = {page.pdf_page for page in ir.pages}
    processed = set(processed_pages or [])
    covered_claims, missing, covered_blocks, result_blocks = [], [], set(), set()
    for claim in claims or []:
        result = validate_claim(claim, ir)
        if result.valid:
            covered_claims.append(claim.claim_id)
            covered_blocks.update(e.block_id for e in result.claim.evidences)
            value = result.claim.value
            is_result = isinstance(value, (int, float, bool)) or isinstance(value, dict) and any(
                value.get(key) is not None and value.get(key) != ""
                for key in ("tc", "tc_value_k", "tc_min_k", "tc_max_k", "value", "value_number",
                            "value_min", "value_max", "value_text", "value_raw", "value_boolean"))
            if is_result:
                result_blocks.update(e.block_id for e in result.claim.evidences)
        else:
            missing.append(claim.claim_id)
    suspected = [b.block_id for b in ir.blocks if RESULT_PATTERN.search(b.text)
                 and b.block_type not in {"table", "table_cell"}]
    missing.extend(f"block:{block}" for block in suspected if block not in result_blocks)
    for table in ir.tables:
        if table.row_count == 0 or not table.cells:
            missing.append(f"table:{table.table_id}:unread")
        # 一条表格引用不能自动覆盖所有结果行，必须定位到各行的单元格。
        for row in range(table.row_count):
            cells = [c for c in table.cells if c.row_index == row]
            if not cells or not any(c.block_id in result_blocks for c in cells):
                missing.append(f"table:{table.table_id}:row:{row}")
    for block in ir.blocks:
        if block.block_type in {"figure", "formula"} and block.block_id not in covered_blocks:
            missing.append(f"region:{block.block_id}")
    empty = sorted(p for p in pages if not any(b.pdf_page == p and
        (b.text.strip() or b.block_type in {"figure","formula","table"}) for b in ir.blocks))
    for block in ir.blocks:
        if block.block_type == "table" and block.block_id not in {t.block_id for t in ir.tables}:
            missing.append(f"table:{block.block_id}:structure_missing")
    missing.extend(f"page:{page}" for page in sorted(pages - processed))
    limitations = list(ir.coverage.get("limitations", []))
    if not pages:
        limitations.append("document_has_no_pages")
    if processed - pages:
        limitations.append("processed_page_not_in_document")
    if empty:
        limitations.append("empty_page_content_unconfirmed")
    signals = ["output_truncated"] if truncated else []
    complete = not (missing or signals or limitations)
    return CoverageReport(status="complete" if complete else "incomplete",
        processed_pages=sorted(processed & pages), empty_pages=empty,
        table_rows={t.table_id: t.row_count for t in ir.tables},
        figure_count=sum(b.block_type == "figure" for b in ir.blocks),
        formula_count=sum(b.block_type == "formula" for b in ir.blocks),
        suspected_result_blocks=suspected, covered_claim_ids=covered_claims,
        uncovered_candidates=list(dict.fromkeys(missing)), truncation_signals=signals,
        limitations=limitations, requires_human=not complete)
