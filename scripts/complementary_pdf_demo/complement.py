"""内容触发的互补输入：保留真实块身份及解析差异，不投票改写科学值。"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import re

from backend.ingest.document_ir import DocumentIR, content_hash
from .parsers import write_json


def overlap(left, right):
    if left is None or right is None:
        return 0.0
    area = lambda b: max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    intersection = (max(left[0], right[0]), max(left[1], right[1]), min(left[2], right[2]), min(left[3], right[3]))
    return area(intersection) / max(min(area(left), area(right)), 1e-9)


def needs_complement(block):
    if block.block_type in {"table", "formula", "figure", "caption"}:
        return "structured_content"
    if re.search(r"\d|[�μλω×−=]|\\(?:frac|times|mu|lambda)", block.text):
        return "scientific_symbols_or_numeric_content"
    if not block.text.strip():
        return "empty_content"
    return None


def compatible(left, right):
    kinds = {str(left.block_type), str(right.block_type)}
    return len(kinds) == 1 or kinds <= {"paragraph", "heading", "ocr_text", "formula"}


def complement(documents):
    base = documents["docling"]
    if any((d.source_file_id, d.source_sha256, [p.pdf_page for p in d.pages]) !=
           (base.source_file_id, base.source_sha256, [p.pdf_page for p in base.pages]) or
           any(not math.isclose(getattr(p, dim), getattr(q, dim), rel_tol=0, abs_tol=0.01)
               for p, q in zip(d.pages, base.pages) for dim in ("width", "height")) for d in documents.values()):
        raise ValueError("互补文件身份或页面几何不一致")
    candidates = {engine: [b for b in ir.blocks if b.block_type != "table_cell"] for engine, ir in documents.items()}
    selected, groups, matched = {}, [], set()

    def retain(engine, block, group_id, role):
        if block.block_id not in selected:
            copy = block.model_copy(deep=True)
            copy.metadata.update(engine=engine, routing_groups=[], selection_role=role)
            selected[block.block_id] = copy
        selected[block.block_id].metadata["routing_groups"].append(group_id)
        for child in documents[engine].blocks:
            if child.parent_block_id == block.block_id:
                copy = child.model_copy(deep=True)
                copy.metadata.update(engine=engine, routing_groups=[group_id], selection_role=role)
                selected.setdefault(copy.block_id, copy)

    for anchor in candidates["docling"]:
        group_id = f"group-{len(groups)}"
        reason = needs_complement(anchor)
        related = []
        if reason:
            for engine in ("mineru", "marker"):
                for other in candidates[engine]:
                    if other.pdf_page != anchor.pdf_page or not compatible(anchor, other):
                        continue
                    score = overlap(anchor.bbox, other.bbox)
                    if score >= 0.45:
                        related.append((engine, other, score))
                        matched.add(other.block_id)
        # 数学专门块优先让 OCR 候选表达公式；原文文本层仍保留供冲突核对。
        primary_engine, primary = "docling", anchor
        if anchor.block_type == "formula":
            formulas = [(e, b) for e, b, _ in related if e == "mineru" and b.block_type == "formula" and b.text.strip()]
            if len(formulas) == 1:
                primary_engine, primary = formulas[0]
        retain("docling", anchor, group_id, "primary" if primary is anchor else "alternative")
        members = [{"engine": "docling", "block_id": anchor.block_id, "overlap": 1.0}]
        for engine, block, score in related:
            retain(engine, block, group_id, "primary" if block is primary else "alternative")
            members.append({"engine": engine, "block_id": block.block_id, "overlap": round(score, 4)})
        per_engine = Counter(x["engine"] for x in members)
        texts = {" ".join(b.text.split()) for b in [anchor, *(b for _, b, _ in related)]}
        groups.append({"group_id": group_id, "file_id": base.source_file_id, "pdf_page": anchor.pdf_page,
                       "kind": str(anchor.block_type), "reason": reason or "baseline_text",
                       "primary": {"engine": primary_engine, "block_id": primary.block_id}, "members": members,
                       "has_text_difference": len(texts) > 1,
                       "alignment": "uncertain_one_to_many" if max(per_engine.values()) > 1 else "spatial_candidate",
                       "semantic_resolution": "unreviewed"})
    # 别的引擎独有的表格、公式、图像或未被骨架覆盖的内容不能直接丢弃。
    for engine in ("mineru", "marker"):
        for block in candidates[engine]:
            if block.block_id in matched:
                continue
            covered = any(a.pdf_page == block.pdf_page and compatible(a, block) and overlap(a.bbox, block.bbox) >= 0.45
                          for a in candidates["docling"])
            if covered and not needs_complement(block):
                continue
            if covered and block.block_type not in {"table", "formula", "figure", "caption"}:
                continue
            group_id = f"group-{len(groups)}"
            retain(engine, block, group_id, "unmatched")
            groups.append({"group_id": group_id, "file_id": base.source_file_id, "pdf_page": block.pdf_page,
                           "kind": str(block.block_type), "reason": "unmatched_or_specialized_content",
                           "primary": {"engine": engine, "block_id": block.block_id},
                           "members": [{"engine": engine, "block_id": block.block_id, "overlap": None}],
                           "has_text_difference": False, "alignment": "unmatched", "semantic_resolution": "unreviewed"})
    ir = base.model_copy(deep=True)
    # 各库浮点页宽差异在 0.01 pt 内；包络尺寸避免边缘框因百万分之一点越界。
    for index, page in enumerate(ir.pages):
        page.width = max(d.pages[index].width for d in documents.values())
        page.height = max(d.pages[index].height for d in documents.values())
    ir.document_id = content_hash([d.model_hash() for d in documents.values()], "complement-v1")
    ir.parse_profile = "demo-complementary"
    ir.parser = {"name": "complementary", "version": "1", "engines": {e: d.parser for e, d in documents.items()}}
    ir.blocks = list(selected.values())
    ir.tables = [t.model_copy(deep=True) for d in documents.values() for t in d.tables if t.block_id in selected]
    ir.figures = [f for d in documents.values() for f in d.figures if f["block_id"] in selected]
    ir.formulas = [f for d in documents.values() for f in d.formulas if f["block_id"] in selected]
    ir.coverage = {"status": "unchecked", "limitations": ["spatial_alignment_is_not_semantic_agreement"]}
    return DocumentIR.model_validate(ir.model_dump(mode="json")), groups


def build_complementary(run: Path, manifest):
    for item in manifest["case"]["files"]:
        documents = {engine: DocumentIR.model_validate_json((run / engine / item["file_id"] / "ir.json").read_text())
                     for engine in ("docling", "mineru", "marker")}
        ir, groups = complement(documents)
        output = run / "complementary" / item["file_id"]
        write_json(output / "ir.json", ir.model_dump(mode="json"))
        write_json(output / "routing.json", groups)
