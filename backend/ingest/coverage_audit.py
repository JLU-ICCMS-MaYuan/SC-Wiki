"""独立检查来源范围与结果覆盖；不能把有引句或模型声称读完当作覆盖完成。"""
from __future__ import annotations

import re
from pydantic import BaseModel, ConfigDict, Field
from .claim_evidence import Claim, validate_claim
from .document_ir import DocumentIR

RESULT_PATTERN = re.compile(r"\bT\s*[_c]?c\b|\bcritical\s+temperature\b|\bsuperconduct|临界温度|超导", re.I)

# 疑似结果项被排除的比例上限：超过即认定大面积漏提，保留人工复核，不产出 ready。
MAX_EXCLUDED_RATIO = 0.5


def verified_download_stamps(ir: DocumentIR, source_path, claims: list[Claim]) -> list[dict]:
    """仅识别原 PDF 文字层可确认的页侧下载水印；不把 OCR 不可读等同于非结果。"""
    from .document_parsers import DocumentSource
    from .document_ir import content_hash
    import pymupdf
    used = {e.block_id for c in claims for e in c.evidences if e.file_id==ir.source_file_id}
    pages = {p.pdf_page:p for p in ir.pages}
    candidates = []
    for b in ir.blocks:
        if b.block_id in used or not b.bbox or b.metadata.get('selected_for_reading') is False:
            continue
        if b.block_type not in {'paragraph','ocr_text'}:
            continue
        x0,y0,x1,y1 = b.bbox
        p = pages[b.pdf_page]
        if (x1 <= p.width*0.04 or x0 >= p.width*0.96) and y1-y0 >= 8*max(x1-x0,1):
            candidates.append(b)
    if not candidates or DocumentSource(source_path,ir.source_file_id).resolved_sha256()!=ir.source_sha256:
        return []
    results = []
    with pymupdf.open(source_path) as pdf:
        for b in candidates:
            original = pdf[b.pdf_page-1].get_textbox(pymupdf.Rect(b.bbox))
            if not re.match(r'downloadedfromhttps?://',re.sub(r'\s+','',original).casefold()):
                continue
            results.append({'file_id':ir.source_file_id,'block_id':b.block_id,
                'category':'non_result_content','reason':'Publisher download stamp verified against the original PDF text layer; not scientific content.',
                'verification':{'rule':'download-stamp-v1','source_sha256':ir.source_sha256,
                    'pdf_page':b.pdf_page,'bbox':list(b.bbox),'text_layer_hash':content_hash(original)}})
    return results


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
    exclusions: list[dict[str, object]] = Field(default_factory=list)
    figures_without_text_layer: int = 0
    truncation_signals: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    checker_version: str = "3"
    requires_human: bool = True


def audit_coverage(ir: DocumentIR, claims: list[Claim] | None = None, *, truncated: bool = False,
                   processed_pages: list[int] | None = None,
                   exclusions: list[dict] | None = None) -> CoverageReport:
    if ir.parse_profile == "complementary":
        selected = {b.block_id for b in ir.blocks if b.metadata.get("selected_for_reading") is not False}
        ir = ir.model_copy(deep=True)
        ir.blocks = [b for b in ir.blocks if b.block_id in selected]
        ir.tables = [t for t in ir.tables if t.block_id in selected]
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
    # 带理由的显式排除：模型审阅后判定某块/表行不产生科学候选。排除不是证据，
    # 只解除覆盖计数；unreadable 类别仍保留人工复核。
    excluded_blocks: set[str] = set()
    excluded_rows: set[tuple[str, int]] = set()
    recorded: list[dict[str, object]] = []
    unreadable = False
    for entry in exclusions or []:
        if entry.get("file_id") not in (ir.source_file_id, None):
            continue
        recorded.append({"locator": entry.get("block_id") or (
            f"table:{entry.get('table_id')}:row:{entry.get('row_index')}"
            if entry.get("table_id") is not None else f"page:{entry.get('pdf_page')}"),
            "category": entry.get("category"), "reason": str(entry.get("reason") or "")[:200]})
        if entry.get('verification'):
            recorded[-1]['verification'] = entry['verification']
        if entry.get("category") == "unreadable":
            unreadable = True
        if entry.get("block_id") is not None:
            excluded_blocks.add(str(entry["block_id"]))
        elif entry.get("table_id") is not None and entry.get("row_index") is not None:
            excluded_rows.add((str(entry["table_id"]), int(entry["row_index"])))
    suspected = [b.block_id for b in ir.blocks if RESULT_PATTERN.search(b.text)
                 and b.block_type not in {"table", "table_cell"}]
    missing.extend(f"block:{block}" for block in suspected
                   if block not in result_blocks and block not in excluded_blocks)
    for table in ir.tables:
        if table.row_count == 0 or not table.cells:
            missing.append(f"table:{table.table_id}:unread")
        # 一条表格引用不能自动覆盖所有结果行，必须定位到各行的单元格；带理由排除的行除外。
        for row in range(table.row_count):
            cells = [c for c in table.cells if c.row_index == row]
            if (table.table_id, row) in excluded_rows:
                continue
            if not cells or not any(c.block_id in result_blocks for c in cells):
                missing.append(f"table:{table.table_id}:row:{row}")
    figures_without_text = 0
    for block in ir.blocks:
        if block.block_type in {"figure", "formula"} and block.block_id not in covered_blocks \
                and block.block_id not in excluded_blocks:
            # 文本层为空的图/公式块：当前解析方案不读取图像内容，属于管线能力边界
            # （#114 视觉/原生方案范围外），不要求提取覆盖，只记录计数供审计。
            if not (block.text or "").strip():
                figures_without_text += 1
            else:
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
    # 防滥用阈值：疑似结果段落被批量申报为"非结果内容"说明提取可能不充分，保留人工复核。
    # 仅统计 non_result_content（背景引用与模型无法表达的内容是正当归类）；小样本
    # （疑似块不足 4 个）比例无统计意义，不触发。
    excluded_suspected_nonresult = sum(
        1 for entry in exclusions or []
        if entry.get("category") == "non_result_content" and str(entry.get("block_id") or "") in set(suspected))
    if len(suspected) >= 4 and excluded_suspected_nonresult / len(suspected) > MAX_EXCLUDED_RATIO:
        limitations.append("excluded_ratio_above_threshold")
    if unreadable:
        limitations.append("unreadable_exclusion_present")
    signals = ["output_truncated"] if truncated else []
    complete = not (missing or signals or limitations)
    return CoverageReport(status="complete" if complete else "incomplete",
        processed_pages=sorted(processed & pages), empty_pages=empty,
        table_rows={t.table_id: t.row_count for t in ir.tables},
        figure_count=sum(b.block_type == "figure" for b in ir.blocks),
        formula_count=sum(b.block_type == "formula" for b in ir.blocks),
        suspected_result_blocks=suspected, covered_claim_ids=covered_claims,
        uncovered_candidates=list(dict.fromkeys(missing)),
        exclusions=recorded, figures_without_text_layer=figures_without_text,
        truncation_signals=signals,
        limitations=limitations, requires_human=not complete)
