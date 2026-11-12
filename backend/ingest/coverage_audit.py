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
            stamp_text = re.sub(r'\s+', '', original).casefold()
            # 访客格式只接受完整下载日期，不能吞掉同块中附带的科学文字。
            guest_stamp = re.fullmatch(
                r'downloadedbygueston(?:january|february|march|april|may|june|july|august|'
                r'september|october|november|december)(?:0?[1-9]|[12]\d|3[01]),\d{4}\.?', stamp_text)
            if not re.match(r'downloadedfromhttps?://', stamp_text) and not guest_stamp:
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
    pending_visual_regions: list[dict[str, object]] = Field(default_factory=list)
    unreadable_regions: list[dict[str, object]] = Field(default_factory=list)
    truncation_signals: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    checker_version: str = "4"
    requires_human: bool = True


def reviewable_chart_limits(documents, reports, *, invalid_claims=False):
    """只将已实际读图的诚实缺失交既有表单核对；不改变原覆盖报告或接受科学值。"""
    from copy import deepcopy
    from .chart_reading import VERSION, unresolved_block
    if invalid_claims:return None
    result=[]
    for file_id,report in reports.items():
        if not report.get('requires_human'):continue
        if (report.get('uncovered_candidates') or report.get('truncation_signals') or report.get('empty_pages')
                or set(report.get('limitations') or [])-{'unreadable_exclusion_present'}):return None
        ir=documents.get(file_id)
        if ir is None:return None
        reading=ir.coverage.get('chart_reading')or{}
        if (reading.get('status')!='completed' or reading.get('version')!=VERSION
                or reading.get('source_sha256')!=ir.source_sha256
                or sorted(reading.get('scanned_pages')or[])!=sorted(p.pdf_page for p in ir.pages)):return None
        targets={t['region_id']:t for t in reading.get('targets')or[]}
        blocks={b.block_id:b for b in ir.blocks if b.metadata.get('selected_for_reading')is not False}
        regions=report.get('unreadable_regions')or[]
        if not regions:return None
        for region in regions:
            block=blocks.get(region.get('locator'));issue=(block.metadata.get('chart_unresolved')or{})if block else{}
            if (not issue or issue.get('reason_code') or issue.get('point') is not None
                    or block.metadata.get('source_kind')!='vision'
                    or issue.get('region_id')not in targets
                    or issue.get('page')!=block.pdf_page
                    or targets[issue['region_id']].get('page')!=block.pdf_page
                    or not str(issue.get('reason')or'').strip()):return None
            expected=unresolved_block(ir.source_sha256,issue,block.reading_order)
            if (block.block_id!=expected.block_id or block.content_hash!=expected.content_hash
                    or block.text!=expected.text):return None
            result.append({'file_id':file_id,'source_sha256':ir.source_sha256,'block_id':block.block_id,
                'content_hash':block.content_hash,'pdf_page':block.pdf_page,'observation':deepcopy(issue),
                'disposition':'no_numeric_value_generated_from_this_unread_source'})
    return result


def audit_coverage(ir: DocumentIR, claims: list[Claim] | None = None, *, truncated: bool = False,
                   processed_pages: list[int] | None = None,
                   exclusions: list[dict] | None = None) -> CoverageReport:
    source_ir = ir  # 备选原块仍是合法来源；覆盖计数只遍历主干选中区域。
    if ir.parse_profile == "complementary":
        selected = {b.block_id for b in ir.blocks if b.metadata.get("selected_for_reading") is not False}
        ir = ir.model_copy(deep=True)
        ir.blocks = [b for b in ir.blocks if b.block_id in selected]
        ir.tables = [t for t in ir.tables if t.block_id in selected]
    pages = {page.pdf_page for page in ir.pages}
    processed = set(processed_pages or [])
    covered_claims, missing, covered_blocks, result_blocks = [], [], set(), set()
    for claim in claims or []:
        result = validate_claim(claim, source_ir)
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
    blocks = {b.block_id: b for b in ir.blocks}
    tables = {t.table_id: t for t in ir.tables}
    unreadable_regions = []
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
            block = blocks.get(entry.get("block_id"))
            if block and block.block_type in {"figure", "formula"} and not block.text.strip():
                # 文字输入没有该区域的像素；保留原始标记，但不能据此断言图像读取失败。
                recorded[-1].update(pdf_page=block.pdf_page, disposition="pending_image_reading")
                continue
            unreadable = True
            table = tables.get(entry.get("table_id"))
            unreadable_regions.append({"file_id": ir.source_file_id,
                "pdf_page": block.pdf_page if block else table.pdf_page if table else entry.get("pdf_page"),
                "locator": recorded[-1]["locator"], "reason": recorded[-1]["reason"]})
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
    pending_visual_regions = []
    for block in ir.blocks:
        if block.block_type in {"figure", "formula"} and block.block_id not in covered_blocks \
                and block.block_id not in excluded_blocks:
            # 文本层为空的图/公式块：当前解析方案不读取图像内容，属于管线能力边界
            # （#114 视觉/原生方案范围外），不要求提取覆盖，只记录计数供审计。
            if not (block.text or "").strip():
                figures_without_text += 1
                pending_visual_regions.append({"file_id": ir.source_file_id, "pdf_page": block.pdf_page,
                    "block_id": block.block_id, "block_type": str(block.block_type), "status": "not_read_in_text_pass"})
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
        pending_visual_regions=pending_visual_regions, unreadable_regions=unreadable_regions,
        truncation_signals=signals,
        limitations=limitations, requires_human=not complete)


def coverage_failure_message(claims, reports, file_names, documents):
    """按实际阻塞原因生成提示；没有未定位 Claim 时不能捏造定位失败。"""
    parts = []
    unlocated = [c for c in claims if c.status != "validated"]
    if unlocated:
        parts.append(f"{len(unlocated)} 组科学候选无法定位，请核对其原句与来源")
    for file_id, report in reports.items():
        if not report["requires_human"]:
            continue
        name = file_names.get(file_id, file_id[:8])
        regions = report.get("unreadable_regions") or []
        if regions:
            pages = sorted({r["pdf_page"] for r in regions if r.get("pdf_page") is not None})
            location = "第 " + ", ".join(map(str, pages)) + " 页" if pages else "页码未确定"
            reasons = list(dict.fromkeys(str(r.get("reason") or "内容读取失败") for r in regions))
            parts.append(f"{name} {location}：{len(regions)} 处内容读取失败（{'；'.join(reasons[:3])}）")
        missing = report.get("uncovered_candidates") or []
        if missing:
            ir = documents[file_id]
            block_pages = {b.block_id: b.pdf_page for b in ir.blocks}
            table_pages = {t.table_id: t.pdf_page for t in ir.tables}
            pages = set()
            for locator in missing:
                match = re.fullmatch(r"(?:block|region):(.+)", locator)
                page = block_pages.get(match[1]) if match else None
                table = re.fullmatch(r"table:(.+):(?:row:\d+|unread|structure_missing)", locator)
                page = table_pages.get(table[1]) if table else page
                if page is not None:
                    pages.add(page)
                if re.fullmatch(r"page:\d+", locator):
                    pages.add(int(locator.split(":")[1]))
            location = " 第 " + ", ".join(map(str, sorted(pages))) + " 页" if pages else ""
            parts.append(f"{name}{location}：{len(missing)} 项内容尚未覆盖")
        for limitation in report.get("limitations") or []:
            if limitation == "unreadable_exclusion_present" and regions:
                continue
            label = {"unreadable_exclusion_present": "存在尚未解决的读取失败",
                "empty_page_content_unconfirmed": "存在尚未确认的空白页",
                "excluded_ratio_above_threshold": "过多疑似结果被排除，需核对是否漏提",
                "document_has_no_pages": "未读到有效页面",
                "processed_page_not_in_document": "处理页码与原文件不一致"}.get(limitation, "解析器报告了尚未解决的读取限制")
            parts.append(f"{name}：{label}")
        if report.get("truncation_signals"):
            parts.append(f"{name}：提取输出被截断")
    return "来源或覆盖检查未完成：" + "；".join(parts or ["存在尚未解决的读取限制"]) + "。请核对解析检查明细后重试"
