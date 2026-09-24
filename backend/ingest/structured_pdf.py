"""Docling / MinerU 原生输出到统一 IR 的转换，及受限子进程调用。"""
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from .document_ir import DocumentBlock, DocumentIR, DocumentTable, PageGeometry, TableCell, content_hash


def run_parser_worker(name, path, options):
    from .document_parsers import ParserError

    def error(code):
        return ParserError(code, "指定解析方案执行失败，请检查依赖、模型资源或重试",
                           profile=options.profile, parser=name)

    timeout = options.parser_options.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 1800:
        raise error("parser_invalid_options")
    tier = options.parser_options.get("mineru_tier", "basic")
    mode = options.parser_options.get("mineru_parse_mode", "ocr")
    if tier not in {"flash", "basic", "standard", "advanced"} or mode not in {"txt", "ocr"}:
        raise error("parser_invalid_options")
    with tempfile.TemporaryDirectory(prefix="scwiki-parser-") as directory:
        root = Path(directory)
        request, response = root / "request.json", root / "response.json"
        request.write_text(json.dumps({"parser": name, "path": str(path.resolve()),
                                      "options": {"mineru_tier": tier, "mineru_parse_mode": mode}}))
        env = os.environ.copy()
        # 上游配置只在隔离子进程生效，不修改正在运行的 Worker 配置。
        env["HF_HUB_DISABLE_TELEMETRY"] = "1"
        env["MINERU_CONFIG"] = str(root / "mineru.yaml")
        (root / "mineru.yaml").write_text("{}")
        process = subprocess.Popen(
            [sys.executable, "-m", "backend.ingest.pdf_parser_worker", str(request), str(response)],
            cwd=Path(__file__).resolve().parents[2], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        try:
            process.wait(timeout=timeout)
        except BaseException as exc:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                raise error("parser_timeout") from exc
            raise
        if process.returncode != 0 or not response.is_file():
            raise error("parser_execution_failed")
        try:
            output = json.loads(response.read_text())
        except (ValueError, OSError) as exc:
            raise error("parser_invalid_output") from exc
        if "error" in output:
            raise error(output["error"])
        return output


class IrBuilder:
    def __init__(self, source, options, name, version, pages, mode):
        self.source, self.options = source, options
        self.name, self.version, self.mode = name, version, mode
        self.pages = pages
        self.page_map = {p.pdf_page: p for p in pages}
        self.blocks, self.tables, self.figures, self.formulas = [], [], [], []
        self.limitations = []
        self.sha256 = source.resolved_sha256()

    def add(self, page, kind, text, bbox, *, parent=None, metadata=None):
        geometry = self.page_map[page]
        if bbox is not None:
            bbox = tuple(float(x) for x in bbox)
            if (len(bbox) != 4 or not all(math.isfinite(x) for x in bbox)
                    or not 0 <= bbox[0] < bbox[2] <= geometry.width
                    or not 0 <= bbox[1] < bbox[3] <= geometry.height):
                self.limitations.append(f"invalid_geometry:{page}:{len(self.blocks)}")
                bbox = None
        digest = content_hash(kind, text, bbox)
        block_id = content_hash(self.source.file_id, self.sha256, self.source.source_version, self.name,
                                self.version, self.options.profile, page, len(self.blocks), digest)
        block = DocumentBlock(block_id=block_id, block_type=kind, pdf_page=page,
                              reading_order=len(self.blocks), text=text, bbox=bbox,
                              page_width=geometry.width, page_height=geometry.height,
                              parent_block_id=parent, content_hash=digest,
                              metadata={"source_kind": {"text": "text_layer", "ocr": "ocr", "vlm": "vision"}[self.mode], **(metadata or {})})
        self.blocks.append(block)
        if kind == "figure":
            block.figure_id = block_id
            self.figures.append({"figure_id": block_id, "block_id": block_id, "pdf_page": page})
        if kind == "formula":
            self.formulas.append({"formula_id": block_id, "block_id": block_id, "pdf_page": page, "text": text})
        return block

    def table(self, block, rows, columns, cells):
        block.table_id = block.block_id
        result = []
        for row, column, text, bbox, spans in cells:
            child = self.add(block.pdf_page, "table_cell", text, bbox, parent=block.block_id, metadata=spans)
            child.table_id = block.block_id
            result.append(TableCell(cell_id=child.block_id, block_id=child.block_id,
                                    row_index=row, column_index=column, text=text, bbox=child.bbox))
        self.tables.append(DocumentTable(table_id=block.block_id, block_id=block.block_id,
                                         pdf_page=block.pdf_page, row_count=rows, column_count=columns, cells=result))

    def finish(self):
        return DocumentIR(document_id=content_hash(self.sha256, self.name, self.version, self.options.profile),
                          source_file_id=self.source.file_id, source_sha256=self.sha256,
                          source_version=self.source.source_version, parse_profile=self.options.profile,
                          parser={"name": self.name, "version": self.version, "mode": self.mode},
                          pages=self.pages, blocks=self.blocks, tables=self.tables,
                          figures=self.figures, formulas=self.formulas,
                          coverage={"limitations": self.limitations, "status": "unchecked"})


def docling_bbox(value, page):
    if value is None:
        return None
    if value.get("coord_origin", "TOPLEFT") == "BOTTOMLEFT":
        return (value["l"], page.height - value["t"], value["r"], page.height - value["b"])
    return (value["l"], value["t"], value["r"], value["b"])


def convert_docling(output, source, options, version):
    doc = output["document"]
    pages = [PageGeometry(pdf_page=int(key), width=value["size"]["width"], height=value["size"]["height"])
             for key, value in sorted(doc["pages"].items(), key=lambda pair: int(pair[0]))]
    builder = IrBuilder(source, options, "docling", version, pages, output["mode"])
    labels = {"title": "heading", "section_header": "heading", "table": "table",
              "picture": "figure", "formula": "formula", "caption": "caption"}

    def resolve(ref):
        collection, index = ref["$ref"].lstrip("#/").split("/")
        return doc[collection][int(index)]

    visited = set()
    def visit(item):
        identity = item.get("self_ref")
        if identity in visited:
            return
        visited.add(identity)
        kind = labels.get(item.get("label"), "paragraph")
        for provenance in item.get("prov", []):
            page = int(provenance["page_no"])
            text = item.get("text", "")
            data = item.get("data", {})
            if kind == "table":
                text = "\n".join(cell["text"] for cell in data["table_cells"])
            block = builder.add(page, kind, text, docling_bbox(provenance.get("bbox"), builder.page_map[page]))
            if kind == "table":
                builder.table(block, data["num_rows"], data["num_cols"], [
                    (cell["start_row_offset_idx"], cell["start_col_offset_idx"], cell["text"],
                     docling_bbox(cell.get("bbox"), builder.page_map[page]),
                     {"row_span": cell.get("row_span", 1), "column_span": cell.get("col_span", 1)})
                    for cell in data["table_cells"]])
        for child in item.get("children", []):
            visit(resolve(child))
    for root in ("body", "furniture"):
        for child in doc.get(root, {}).get("children", []):
            visit(resolve(child))
    return builder.finish()


class HtmlCells(HTMLParser):
    """解析表格行列跨度，不从无坐标 HTML 编造单元格区域。"""
    def __init__(self):
        super().__init__()
        self.row, self.column = -1, 0
        self.cells, self.occupied = [], set()
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row += 1
            self.column = 0
        elif tag in {"td", "th"}:
            while (self.row, self.column) in self.occupied:
                self.column += 1
            values = dict(attrs)
            self.current = [self.row, self.column, "", None,
                            {"row_span": max(1, int(values.get("rowspan", 1))),
                             "column_span": max(1, int(values.get("colspan", 1)))}]
        elif tag == "br" and self.current:
            self.current[2] += "\n"

    def handle_data(self, data):
        if self.current is not None:
            self.current[2] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.current is not None:
            row, col, _, _, spans = self.current
            for r in range(row, row + spans["row_span"]):
                for c in range(col, col + spans["column_span"]):
                    self.occupied.add((r, c))
            self.cells.append(self.current)
            self.column += spans["column_span"]
            self.current = None


def inline_text(content):
    if isinstance(content, str):
        return content
    return "".join(inline_text(item["content"]) for item in content or [])


def convert_mineru(output, source, options, version):
    import pymupdf
    # MinerU 4 输出归一化坐标；物理页面尺寸从同一份原 PDF 取得。
    with pymupdf.open(source.path) as pdf:
        pages = [PageGeometry(pdf_page=i + 1, width=p.rect.width, height=p.rect.height) for i, p in enumerate(pdf)]
    builder = IrBuilder(source, options, "mineru", version, pages, output["mode"])
    doc = output["document"]
    if not doc["is_full_document"]:
        raise ValueError("partial document")
    if [p["page_idx"] + 1 for p in doc["pages"]] != [p.pdf_page for p in pages]:
        raise ValueError("missing pages")
    labels = {"doc_title": "heading", "paragraph_title": "heading", "equation": "formula",
              "image": "figure", "chart": "figure", "table": "table", "table_body": "table",
              "image_body": "figure", "chart_body": "figure"}

    def visit(item, page, parent=None):
        original_kind = item["type"]
        kind = labels.get(original_kind, "caption" if "caption" in original_kind else "paragraph")
        content = item.get("content", "")
        # 视觉容器由主体块保存；图注/脚注继续保留独立区域。
        if original_kind in {"image", "chart", "table", "list", "index", "code"}:
            for child in content:
                visit(child, page, parent)
            return
        text = inline_text(content)
        bbox = item.get("bbox")
        geometry = builder.page_map[page]
        if bbox is not None:
            bbox = [bbox[0] * geometry.width, bbox[1] * geometry.height,
                    bbox[2] * geometry.width, bbox[3] * geometry.height]
        table = None
        if original_kind == "table_body":
            table = HtmlCells()
            table.feed(text)
            text = "\n".join(cell[2] for cell in table.cells)
        block = builder.add(page, kind, text, bbox, parent=parent,
                            metadata={"mineru_tier": output["tier"]})
        if table is not None:
            rows = max((r for r, _ in table.occupied), default=-1) + 1
            columns = max((c for _, c in table.occupied), default=-1) + 1
            builder.table(block, rows, columns, table.cells)
            builder.limitations.append(f"table_cell_geometry_unavailable:{block.block_id}")
    for page in doc["pages"]:
        for item in page["blocks"]:
            visit(item, page["page_idx"] + 1)
    return builder.finish()
