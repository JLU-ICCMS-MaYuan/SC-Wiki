"""Marker 独立运行环境及原生 JSON 到 DocumentIR 的适配。"""
from __future__ import annotations

import importlib.metadata
from pathlib import Path


def parse_marker(path, options):
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict, shutdown_models

    config = {"output_format": "json", "use_llm": False, "mode": "balanced"}
    parser = ConfigParser(config)
    models = create_model_dict()
    try:
        converter = PdfConverter(config=parser.generate_config_dict(), artifact_dict=models,
                                 processor_list=parser.get_processors(), renderer=parser.get_renderer(),
                                 llm_service=parser.get_llm_service())
        result = converter(str(path))
        return {"document": result.model_dump(mode="json", exclude={"images"}), "mode": "vlm",
                "version": importlib.metadata.version("marker-pdf"), "options": config}
    finally:
        shutdown_models(models)


def convert_marker(output, source, options, version):
    import pymupdf
    from bs4 import BeautifulSoup
    from .document_ir import PageGeometry
    from .structured_pdf import IrBuilder, HtmlCells

    with pymupdf.open(source.path) as pdf:
        selected = output.get("page_map") or list(range(1, len(pdf) + 1))
        pages = [PageGeometry(pdf_page=i, width=pdf[i-1].rect.width, height=pdf[i-1].rect.height) for i in selected]
    roots = output["document"]["children"]
    if len(roots) != len(pages):
        raise ValueError("Marker 输出缺页")
    builder = IrBuilder(source, options, "marker", version, pages, "vlm")
    labels = {"SectionHeader": "heading", "Title": "heading", "Table": "table", "Equation": "formula",
              "Picture": "figure", "Figure": "figure", "Caption": "caption"}

    def visit(item, page, scale):
        kind = item.get("block_type", "Text")
        if item.get("children") and kind not in labels:
            for child in item["children"]:
                visit(child, page, scale)
            return
        html = item.get("html") or ""
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        polygon = item.get("polygon")
        bbox = None
        if polygon:
            xs, ys = zip(*polygon)
            bbox = [min(xs)*scale[0], min(ys)*scale[1], max(xs)*scale[0], max(ys)*scale[1]]
        block = builder.add(page, labels.get(kind, "paragraph"), text, bbox,
                            metadata={"native_id": item.get("id"), "native_type": kind})
        if block.block_type == "table":
            table = HtmlCells()
            table.feed(html)
            if table.cells:
                builder.table(block, max(r for r, _ in table.occupied)+1,
                              max(c for _, c in table.occupied)+1, table.cells)
                builder.limitations.append(f"table_cell_geometry_unavailable:{block.block_id}")
    for page, root in zip(pages, roots):
        polygon = root.get("polygon")
        if not polygon:
            raise ValueError("Marker 页面没有坐标基准")
        xs, ys = zip(*polygon)
        if min(xs) != 0 or min(ys) != 0 or max(xs) <= 0 or max(ys) <= 0:
            raise ValueError("Marker 坐标基准无效")
        for child in root.get("children") or []:
            visit(child, page.pdf_page, (page.width/max(xs), page.height/max(ys)))
    return builder.finish()
