"""独立 demo 的原始解析执行与 Marker 来源适配；不注册生产解析器。"""
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import sys


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def worker(engine: str, source: Path, output: Path) -> None:
    """子进程只读 PDF 并保存原生输出；异常由父进程保留日志。"""
    distribution = {"docling": "docling", "mineru": "mineru", "marker": "marker-pdf"}[engine]
    version = importlib.metadata.version(distribution)
    import faulthandler
    faulthandler.dump_traceback_later(300, repeat=True)
    print(f"Starting {engine} {version}", flush=True)
    if engine in {"docling", "mineru"}:
        from backend.ingest.pdf_parser_worker import convert
        options = {"mineru_tier": "basic", "mineru_parse_mode": "ocr"}
        result = convert({"parser": engine, "path": str(source), "options": options})
        result["runtime"] = {"version": version, "options": options if engine == "mineru" else {
            "device": "cpu", "do_ocr": False, "do_table_structure": True, "enable_remote_services": False}}
        write_json(output / "raw.json", result)
    else:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser

        config = {"output_format": "json", "use_llm": False, "mode": "balanced"}
        parser = ConfigParser(config)
        converter = PdfConverter(config=parser.generate_config_dict(), artifact_dict=create_model_dict(),
                                 processor_list=parser.get_processors(), renderer=parser.get_renderer(),
                                 llm_service=parser.get_llm_service())
        result = converter(str(source))
        # JSON renderer 中的图片可能是 PIL 对象；图片以文件保存，JSON 只保存其位置。
        images = getattr(result, "images", {}) or {}
        image_files = {}
        for name, picture in images.items():
            safe_name = Path(name).name
            picture.save(output / safe_name)
            image_files[name] = safe_name
        document = result.model_dump(mode="json", exclude={"images"})
        write_json(output / "raw.json", {"document": document, "images": image_files,
                                          "runtime": {"version": version, "options": config,
                                          "inference_backend": "llamacpp", "inference_parallel": 2,
                                          "public_model_endpoint": os.environ.get("HF_ENDPOINT")}})
    write_json(output / "packages.json", {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()})


def convert_marker(raw, source, options):
    """保留页/块和 HTML 表格单元；不从父框推造单元坐标。"""
    import pymupdf
    from bs4 import BeautifulSoup
    from backend.ingest.document_ir import PageGeometry
    from backend.ingest.structured_pdf import IrBuilder, HtmlCells

    with pymupdf.open(source.path) as pdf:
        pages = [PageGeometry(pdf_page=i + 1, width=p.rect.width, height=p.rect.height) for i, p in enumerate(pdf)]
    builder = IrBuilder(source, options, "marker", raw["runtime"]["version"], pages, "vlm")
    roots = raw["document"]["children"]
    if len(roots) != len(pages):
        raise ValueError("Marker 输出页数不完整")
    labels = {"SectionHeader": "heading", "Title": "heading", "Table": "table", "TableOfContents": "table",
              "Equation": "formula", "Picture": "figure", "Figure": "figure", "Caption": "caption"}

    def visit(item, page, scale):
        kind = item.get("block_type", "Text")
        children = item.get("children") or []
        if children and kind not in labels:
            for child in children:
                visit(child, page, scale)
            return
        html = item.get("html") or ""
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        polygon = item.get("polygon")
        bbox = None
        if polygon:
            xs, ys = zip(*polygon)
            bbox = [min(xs) * scale[0], min(ys) * scale[1], max(xs) * scale[0], max(ys) * scale[1]]
        block = builder.add(page, labels.get(kind, "paragraph"), text, bbox,
                            metadata={"native_id": item.get("id"), "native_type": kind})
        if block.block_type == "table":
            cells = HtmlCells()
            cells.feed(html)
            if cells.cells:
                rows = max(r for r, _ in cells.occupied) + 1
                columns = max(c for _, c in cells.occupied) + 1
                builder.table(block, rows, columns, cells.cells)
                builder.limitations.append(f"table_cell_geometry_unavailable:{block.block_id}")
    for index, root in enumerate(roots):
        polygon = root.get("polygon")
        if not polygon:
            raise ValueError("Marker 页面缺少坐标基准")
        xs, ys = zip(*polygon)
        if min(xs) != 0 or min(ys) != 0 or max(xs) <= 0 or max(ys) <= 0:
            raise ValueError("Marker 页面坐标原点无法确认")
        page = pages[index]
        scale = (page.width / max(xs), page.height / max(ys))
        for child in root.get("children") or []:
            visit(child, index + 1, scale)
    return builder.finish()


def to_ir(engine, raw, source):
    from backend.ingest.document_parsers import ParseOptions
    from backend.ingest.structured_pdf import convert_docling, convert_mineru
    options = ParseOptions(profile=f"demo-{engine}")
    if engine == "marker":
        ir = convert_marker(raw, source, options)
    else:
        convert = convert_docling if engine == "docling" else convert_mineru
        ir = convert(raw, source, options, raw["runtime"]["version"])
    for block in ir.blocks:
        block.metadata["engine"] = engine
    return ir


if __name__ == "__main__":
    worker(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
