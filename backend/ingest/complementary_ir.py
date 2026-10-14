"""MinerU 主干的内容选择与补强账本；原始块不改写科学值。"""
from __future__ import annotations

from .document_ir import DocumentIR, content_hash


def repair_pages(ir):
    tables = sorted({t.pdf_page for t in ir.tables})
    marker = set()
    reasons = []
    for block in ir.blocks:
        if block.block_type in {"formula", "figure"} or "\ufffd" in block.text:
            marker.add(block.pdf_page)
            reasons.append({"pdf_page": block.pdf_page, "block_id": block.block_id,
                            "reason": "formula_or_visual_region" if block.block_type in {"formula", "figure"} else "damaged_text"})
    for page in ir.pages:
        if not any(b.pdf_page == page.pdf_page and b.text.strip() for b in ir.blocks):
            marker.add(page.pdf_page)
            reasons.append({"pdf_page": page.pdf_page, "reason": "empty_text_page"})
    return {"docling": tables, "marker": sorted(marker), "reasons": reasons}


def overlap(a, b):
    if not a or not b:
        return 0
    area = lambda c: max(0, c[2]-c[0])*max(0, c[3]-c[1])
    inter = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
    return area(inter)/max(min(area(a), area(b)), 1e-9)


def compose(documents):
    base = documents["mineru"]
    for ir in documents.values():
        if (ir.source_file_id, ir.source_sha256, ir.source_version) != (base.source_file_id, base.source_sha256, base.source_version):
            raise ValueError("补强来源身份不一致")
        geometry = {p.pdf_page: p for p in base.pages}
        if any(p.pdf_page not in geometry or abs(p.width-geometry[p.pdf_page].width) > .01 or
               abs(p.height-geometry[p.pdf_page].height) > .01 for p in ir.pages):
            raise ValueError("补强页码或坐标不一致")
    roots = {e: [b for b in d.blocks if not b.parent_block_id] for e, d in documents.items()}
    table_map = {t.block_id: t for d in documents.values() for t in d.tables}
    selected, routes = [], []

    def family(block, engine):
        return [block, *(b for b in documents[engine].blocks if b.parent_block_id == block.block_id)]

    def table_quality(block):
        table = table_map.get(block.block_id)
        if not table:
            return (0, 0)
        return (sum(c.bbox is not None for c in table.cells), sum(bool(c.text.strip()) for c in table.cells))

    for block in roots["mineru"]:
        primary, engine = block, "mineru"
        candidates = []
        kind = str(block.block_type)
        for other_engine in ("docling", "marker"):
            for other in roots.get(other_engine, []):
                if other.pdf_page == block.pdf_page and other.block_type == block.block_type and overlap(block.bbox, other.bbox) >= .6:
                    candidates.append((other_engine, other))
        tables = [(e, b) for e, b in candidates if e == "docling" and kind == "table"]
        if len(tables) == 1 and table_quality(tables[0][1]) > table_quality(block):
            engine, primary = tables[0]
        elif "\ufffd" in block.text or not block.text.strip():
            readable = [(e, b) for e, b in candidates if e == "marker" and b.text.strip() and "\ufffd" not in b.text]
            if len(readable) == 1:
                engine, primary = readable[0]
        selected.extend(b.block_id for b in family(primary, engine))
        different = [dict(engine=e, block_id=b.block_id, text=b.text, bbox=b.bbox)
                     for e, b in [("mineru", block), *candidates]
                     if b.block_id != primary.block_id and " ".join(b.text.split()) != " ".join(primary.text.split())]
        routes.append({"anchor": block.block_id, "pdf_page": block.pdf_page, "kind": kind,
                       "selected": primary.block_id, "selected_text": primary.text, "engine": engine,
                       "reason": "table_cell_structure" if engine == "docling" else "readable_repair" if engine == "marker" else "mineru_main",
                       "alternatives": different, "semantic_status": "unreviewed" if different else "not_compared"})
    # 专门组件识别出的独有表格/公式不丢失；普通正文仍使用 MinerU。
    for engine, items in roots.items():
        if engine == "mineru":
            continue
        for block in items:
            if block.block_type not in {"table", "formula"}:
                continue
            if any(b.pdf_page == block.pdf_page and overlap(b.bbox, block.bbox) >= .6 for b in roots["mineru"]):
                continue
            selected.extend(b.block_id for b in family(block, engine))
            routes.append({"anchor": None, "pdf_page": block.pdf_page, "kind": str(block.block_type),
                           "selected": block.block_id, "engine": engine, "reason": "missing_specialized_region", "alternatives": []})
    selected = list(dict.fromkeys(selected))
    order = {identifier: index for index, identifier in enumerate(selected)}
    result = base.model_copy(deep=True)
    for page in result.pages:
        peers = [p for d in documents.values() for p in d.pages if p.pdf_page == page.pdf_page]
        page.width, page.height = max(p.width for p in peers), max(p.height for p in peers)
    result.blocks = []
    for engine, ir in documents.items():
        for original in ir.blocks:
            block = original.model_copy(deep=True)
            block.metadata.update(source_parser=engine, source_parser_version=ir.parser["version"],
                                  selected_for_reading=block.block_id in order)
            block.reading_order = order.get(block.block_id, len(order)+len(result.blocks))
            result.blocks.append(block)
    result.tables = [t.model_copy(deep=True) for d in documents.values() for t in d.tables]
    result.figures = [f for d in documents.values() for f in d.figures]
    result.formulas = [f for d in documents.values() for f in d.formulas]
    result.document_id = content_hash("four-tools-v1", [d.model_hash() for d in documents.values()])
    result.parse_profile = "complementary"
    result.parser = {"name": "complementary", "version": "1", "mode": "ocr",
                     "components": {e: d.parser for e, d in documents.items()}}
    capabilities = [s for d in documents.values() for s in d.coverage.get("limitations", [])]
    result.coverage = {"status": "unchecked", "limitations": [s for s in capabilities if s.startswith("invalid_geometry")],
                       "capability_limitations": capabilities, "routing": routes,
                       "selected_blocks": len(order), "raw_blocks": len(result.blocks)}
    return DocumentIR.model_validate(result.model_dump(mode="json"))
