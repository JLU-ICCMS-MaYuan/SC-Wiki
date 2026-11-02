"""仅扩展经原PDF文字层确认的访客下载水印；不以乱码或页侧位置替代确认。"""
import pytest

from backend.ingest.coverage_audit import audit_coverage, verified_download_stamps
from backend.ingest.document_ir import PageGeometry
from backend.ingest.document_parsers import DocumentSource, ParseOptions
from backend.ingest.structured_pdf import IrBuilder


def source(tmp_path, text, *, margin=True):
    import pymupdf
    path = tmp_path / "source.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((12, 720) if margin else (150, 150), text,
                         rotate=90 if margin else 0, fontsize=8)
        pdf.save(path)
    with pymupdf.open(path) as pdf:
        block = pdf[0].get_text("blocks")[0]
    builder = IrBuilder(DocumentSource(path, "main"), ParseOptions(profile="mineru"),
                        "mineru", "test", [PageGeometry(pdf_page=1, width=600, height=800)], "ocr")
    stamp = builder.add(1, "paragraph", "Dow n 0 q e o 21", block[:4])
    return path, builder.finish(), stamp


@pytest.mark.parametrize("text", [
    "Downloaded by guest on September 16, 2021",
    "Downloaded by guest on January 1, 2026.",
    "DOWNLOADED BY GUEST ON DECEMBER 31, 2025",
    "Downloaded from https://publisher.invalid/paper on October 15",
])
def test_guest_and_existing_url_stamps_require_native_confirmation(tmp_path, text):
    path, ir, stamp = source(tmp_path, text)
    verified = verified_download_stamps(ir, path, [])
    assert [e["block_id"] for e in verified] == [stamp.block_id]
    assert verified[0]["verification"]["source_sha256"] == ir.source_sha256
    before = audit_coverage(ir, [], processed_pages=[1], exclusions=[{
        "file_id": "main", "block_id": stamp.block_id, "category": "unreadable", "reason": "OCR garbled"}])
    assert before.requires_human
    after = audit_coverage(ir, [], processed_pages=[1], exclusions=verified)
    assert after.status == "complete" and not after.requires_human


@pytest.mark.parametrize("text", [
    "Tc = 200 K at 150 GPa",
    "Downloaded by guest on superconductivity measurements",
    "Downloaded by guest on September 16, 2021; Tc = 200 K",
    "Downloaded by guest on September 99, 2021",
])
def test_non_stamp_or_additional_scientific_text_cannot_be_excluded(tmp_path, text):
    path, ir, _ = source(tmp_path, text)
    assert verified_download_stamps(ir, path, []) == []


def test_guest_statement_in_body_is_not_a_margin_stamp(tmp_path):
    path, ir, _ = source(tmp_path, "Downloaded by guest on September 16, 2021", margin=False)
    assert verified_download_stamps(ir, path, []) == []


@pytest.mark.parametrize("protection", ["source_hash", "not_selected", "scientific_reference"])
def test_existing_source_and_scientific_reference_protections_remain(tmp_path, protection):
    from types import SimpleNamespace
    path, ir, stamp = source(tmp_path, "Downloaded by guest on September 16, 2021")
    claims = []
    if protection == "source_hash":
        ir.source_sha256 = "0" * 64
    elif protection == "not_selected":
        ir.blocks[0].metadata["selected_for_reading"] = False
    else:
        claims = [SimpleNamespace(evidences=[SimpleNamespace(file_id="main", block_id=stamp.block_id)])]
    assert verified_download_stamps(ir, path, claims) == []
