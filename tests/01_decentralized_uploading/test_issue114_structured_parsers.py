"""真实供应商数据结构、区域转换和隔离解析进程回归。"""
from pathlib import Path

import pytest

from backend.ingest.document_ir import DocumentBlock, DocumentIR, PageGeometry
from backend.ingest.document_parsers import (
    DoclingParser, MinerUParser, DocumentSource, ParseOptions, ParserError,
    ParserRegistry, RuntimeCapabilities,
)
from backend.ingest.structured_pdf import convert_docling, convert_mineru, run_parser_worker


@pytest.fixture
def pdf(tmp_path):
    import pymupdf
    path = tmp_path / "paper.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((40, 80), "The critical temperature reaches 200 K at 150 GPa.")
        doc.new_page(width=600, height=800)
        doc.save(path)
    return DocumentSource(path=path, file_id="uploaded-1")


def test_docling_mapping_uses_real_schema(pdf):
    document = pytest.importorskip("docling_core.types.doc.document")
    from docling_core.types.doc.base import BoundingBox, CoordOrigin, Size
    doc = document.DoclingDocument(name="fixture")
    doc.add_page(page_no=1, size=Size(width=600, height=800))
    doc.add_page(page_no=2, size=Size(width=600, height=800))
    provenance = document.ProvenanceItem(page_no=1, charspan=(0, 10),
        bbox=BoundingBox(l=40, t=740, r=300, b=710, coord_origin=CoordOrigin.BOTTOMLEFT))
    doc.add_text(label=document.DocItemLabel.TEXT, text="Tc = 200 K", prov=provenance)
    doc.add_text(label=document.DocItemLabel.FORMULA, text="T_c", prov=provenance)
    doc.add_picture(prov=provenance)
    doc.add_table(data=document.TableData(num_rows=1, num_cols=2, table_cells=[
        document.TableCell(text="150 GPa", start_row_offset_idx=0, end_row_offset_idx=1,
                           start_col_offset_idx=0, end_col_offset_idx=1),
        document.TableCell(text="200 K", start_row_offset_idx=0, end_row_offset_idx=1,
                           start_col_offset_idx=1, end_col_offset_idx=2),
    ]), prov=provenance)
    output = {"document": doc.export_to_dict(), "mode": "text"}
    ir = convert_docling(output, pdf, ParseOptions(profile="layout"), "2.130.0")
    assert ir.blocks[0].bbox == (40, 60, 300, 90)
    assert ir.blocks[0].text == "Tc = 200 K"
    assert len(ir.formulas) == len(ir.figures) == len(ir.tables) == 1
    assert len(ir.tables[0].cells) == 2
    assert ir.tables[0].cells[1].text == "200 K"
    assert len(ir.pages) == 2
    again = convert_docling(output, pdf, ParseOptions(profile="layout"), "2.130.0")
    assert ir.model_dump() == again.model_dump()


def test_mineru_normalized_geometry_and_html_cells(pdf):
    output = {"mode": "ocr", "tier": "basic", "document": {
        "is_full_document": True, "pages": [
            {"page_idx": 0, "blocks": [
                {"type": "text", "bbox": [0.1, 0.1, 0.5, 0.2],
                 "content": [{"type": "text", "content": "200 K"}]},
                {"type": "table", "content": [
                    {"type": "table_body", "bbox": [0.1, 0.3, 0.9, 0.7],
                     "content": "<table><tr><th rowspan=\"2\">P</th><td>150</td></tr><tr><td>200 K</td></tr></table>"}]},
                {"type": "equation", "content": "T_c", "bbox": [0.1, 0.8, 0.9, 0.9]},
            ]}, {"page_idx": 1, "blocks": []}]}}
    ir = convert_mineru(output, pdf, ParseOptions(profile="ocr"), "4.0.6")
    assert ir.blocks[0].bbox == (60, 80, 300, 160)
    assert ir.blocks[0].metadata["source_kind"] == "ocr"
    table = ir.tables[0]
    assert (table.row_count, table.column_count) == (2, 2)
    assert table.cells[-1].row_index == 1 and table.cells[-1].column_index == 1
    assert table.cells[-1].bbox is None
    assert ir.formulas[0]["text"] == "T_c"
    assert "table_cell_geometry_unavailable" in ir.coverage["limitations"][0]
    output["document"]["pages"].pop()
    with pytest.raises(ValueError, match="missing pages"):
        convert_mineru(output, pdf, ParseOptions(profile="ocr"), "4.0.6")


@pytest.mark.parametrize("name,profile", [("docling", "layout"), ("mineru", "ocr")])
def test_subprocess_timeout_is_bounded(pdf, name, profile):
    with pytest.raises(ParserError) as error:
        run_parser_worker(name, pdf.path, ParseOptions(profile=profile, parser_options={"timeout_seconds": 0.001}))
    assert error.value.code == "parser_timeout"
    assert str(pdf.path) not in str(error.value)


@pytest.mark.parametrize("parser,profile", [(DoclingParser, "layout"), (MinerUParser, "ocr")])
def test_media_routing_rejects_structure_before_import(pdf, parser, profile):
    source = DocumentSource(pdf.path, pdf.file_id, media_type="chemical/x-cif")
    with pytest.raises(ParserError) as error:
        parser().parse(source, ParseOptions(profile=profile))
    assert error.value.code == "parser_unsupported_media"


def test_registry_selects_real_adapters_and_never_fallback(pdf):
    registry = ParserRegistry()
    capabilities = RuntimeCapabilities(installed=frozenset({"docling", "mineru"}))
    assert isinstance(registry.choose("layout", pdf, capabilities), DoclingParser)
    assert isinstance(registry.choose("ocr", pdf, capabilities), MinerUParser)
    with pytest.raises(ParserError):
        registry.choose("layout", pdf, RuntimeCapabilities(installed=frozenset({"fitz"})))


@pytest.mark.parametrize("bbox", [(0, 0, 700, 10), (0, 0, float("nan"), 10)])
def test_ir_checks_document_geometry_even_if_block_lies(bbox):
    with pytest.raises(ValueError):
        block = DocumentBlock(block_id="b", block_type="paragraph", pdf_page=1,
                              reading_order=0, content_hash="a" * 64, bbox=bbox, page_width=1000, page_height=1000)
        DocumentIR(document_id="d", source_file_id="f", source_sha256="a" * 64,
                   parse_profile="layout", pages=[PageGeometry(pdf_page=1, width=600, height=800)], blocks=[block])


def test_ir_rejects_unknown_page():
    with pytest.raises(ValueError, match="不存在"):
        DocumentIR(document_id="d", source_file_id="f", source_sha256="a" * 64, parse_profile="layout",
            pages=[PageGeometry(pdf_page=1, width=600, height=800)],
            blocks=[DocumentBlock(block_id="b", block_type="paragraph", pdf_page=2,
                                   reading_order=0, content_hash="a" * 64)])


@pytest.mark.skipif(__import__("os").environ.get("ISSUE114_REAL_PARSERS") != "1", reason="需要已安装供应商及模型资源")
@pytest.mark.parametrize("profile", ["layout", "ocr"])
def test_real_pdf_conversion(pdf, profile):
    # flash/txt 是显式指定的无模型文本档位，不作为 OCR 成功依据。
    parser = DoclingParser() if profile == "layout" else MinerUParser()
    ir = parser.parse(pdf, ParseOptions(profile=profile, parser_options={
        "mineru_tier": "flash", "mineru_parse_mode": "txt", "timeout_seconds": 300}))
    assert len(ir.pages) == 2
    assert any("200 K" in block.text for block in ir.blocks)
    assert ir.parser["version"] not in {"optional", "unavailable"}
    assert ir.parser["mode"] == "text"


@pytest.mark.skipif(__import__("os").environ.get("ISSUE114_REAL_PARSERS") != "1", reason="需要 MinerU OCR 模型")
def test_real_mineru_scanned_pdf(tmp_path):
    import pymupdf
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as original:
        page = original.new_page()
        page.insert_text((50, 100), "The critical temperature is 200 K at 150 GPa.", fontsize=16)
        image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
        with pymupdf.open() as scanned:
            scanned.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect, stream=image)
            scanned.save(path)
    with pymupdf.open(path) as pdf:
        assert not pdf[0].get_text().strip()
    ir = MinerUParser().parse(DocumentSource(path, "scan"), ParseOptions(profile="ocr"))
    text = " ".join(block.text for block in ir.blocks)
    assert "200 K" in text and "150 GPa" in text
    assert ir.parser["mode"] == "ocr"
    assert any(block.bbox for block in ir.blocks)
