"""真实事务与截图渲染测试，拒绝跨文件关联和过期 PDF。"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend import models
from backend.database import Base
from backend.ingest.document_parsers import DocumentSource, ParseOptions, PyMuPDFParser
from backend.ingest.document_storage import persist_document, link_document_evidence
from backend.ingest.document_regions import render_region, region_document
from backend.ingest.pdf_evidence_crops import render_evidence_crops


def make_document(tmp_path):
    import pymupdf
    path=tmp_path/"source.pdf"
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_text((50,100),"Tc = 200 K at 150 GPa.")
        pdf.save(path)
    ir=PyMuPDFParser().parse(DocumentSource(path,"original"),ParseOptions())
    return path,ir


def test_real_ir_evidence_transaction_and_file_isolation(tmp_path):
    path,ir=make_document(tmp_path)
    async def run():
        engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        @event.listens_for(engine.sync_engine,"connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
        factory=async_sessionmaker(engine,expire_on_commit=False)
        async with factory() as session,session.begin():
            paper=models.Paper(year=2026,content_revision=1,review_status="pending")
            session.add(paper);await session.flush()
            file=models.PaperFile(paper_id=paper.id,paper_revision=1,role="main",sort_order=0,
                original_filename="source.pdf",stored_path=str(path),sha256=ir.source_sha256,size=path.stat().st_size)
            session.add(file);await session.flush()
            parser_run,blocks=await persist_document(session,paper,file,ir)
            chunk=models.PaperChunk(paper_id=paper.id,paper_revision=1,paper_file_id=file.id,chunk_index=0,content=ir.blocks[0].text)
            session.add(chunk);await session.flush()
            evidence=models.PaperEvidence(paper_id=paper.id,paper_revision=1,paper_chunk_id=chunk.id,
                field_path="tc",quote="200 K",page_start=1,page_end=1)
            session.add(evidence);await session.flush()
            locator=await link_document_evidence(session,evidence,chunk,parser_run,blocks)
            again=await link_document_evidence(session,evidence,chunk,parser_run,blocks)
            assert locator.id==again.id
            wrong=SimpleNamespace(id=chunk.id,paper_file_id=file.id+1)
            with pytest.raises(ValueError,match="来源文件"):
                await link_document_evidence(session,evidence,wrong,parser_run,blocks)
            paper_id=paper.id;file_id=file.id
        async with factory() as session:
            row=await session.scalar(select(models.PaperDocumentParserRun))
            assert row.document_json["source_file_id"]==str(file_id)
            assert row.document_json["pages"][0]["pdf_page"]==1
            data=await session.run_sync(lambda s:region_document(s,"paper",str(paper_id),str(file_id),
                SimpleNamespace(id=999,role="admin",is_approved=True)))
            assert render_region(*data,quote="200 K",pdf_page=1)["status"]=="located"
            with pytest.raises(HTTPException) as denied:
                await session.run_sync(lambda s:region_document(s,"paper",str(paper_id),str(file_id),
                    SimpleNamespace(id=888,role="user",is_approved=True)))
            assert denied.value.status_code == 403
        await engine.dispose()
    asyncio.run(run())


def test_region_render_does_not_save_images_and_checks_hash(tmp_path):
    path,ir=make_document(tmp_path)
    before=path.read_bytes()
    result=render_region(ir,path,ir.source_sha256,quote="200 K",pdf_page=1)
    assert result["status"]=="located"
    assert result["image"].startswith("data:image/png;base64,")
    assert all(0<=x<=1 for x in result["region"])
    assert path.read_bytes()==before
    assert list(tmp_path.iterdir())==[path]
    assert render_region(ir,path,"b"*64,quote="200 K",pdf_page=1)["status"]=="render_unavailable"
    assert render_region(ir,path,ir.source_sha256,quote="201 K",pdf_page=1)["status"]=="unlocated"
    assert render_region(None,None,None,quote="old quote",pdf_page=1)["status"]=="legacy_text"


def test_legacy_pdf_uses_unique_text_layer_quote_without_inventing_coordinates(tmp_path):
    path, ir = make_document(tmp_path)
    found = render_region(None, path, ir.source_sha256, quote="Tc = 200 K at 150 GPa.", pdf_page=None)
    assert found["status"] == "located"
    assert found["pdf_page"] == 1
    assert found["image"].startswith("data:image/png;base64,")
    assert found["parser"]["mode"] == "legacy_text"
    assert len(found["regions"]) >= 1
    assert all(0 <= value <= 1 for region in found["regions"] for value in region)
    assert render_region(None, path, "b" * 64, quote="Tc = 200 K at 150 GPa.", pdf_page=None)["status"] == "render_unavailable"
    assert render_region(None, path, ir.source_sha256, quote="Tc = 201 K", pdf_page=None)["status"] == "unlocated"
    corrected = render_region(None, path, ir.source_sha256, quote="Tc = 200 K at 150 GPa.", pdf_page=2)
    assert corrected["status"] == "located"
    assert corrected["pdf_page"] == 1
    assert corrected["dpi"] == 300
    crop = corrected["crops"][0]
    assert crop["width"] == pytest.approx((crop["clip_bbox_pdf"][2] - crop["clip_bbox_pdf"][0]) * 300 / 72, abs=3)
    assert crop["height"] == pytest.approx((crop["clip_bbox_pdf"][3] - crop["clip_bbox_pdf"][1]) * 300 / 72, abs=3)


def test_crop_contains_quote_and_three_adjacent_lines_not_full_page(tmp_path):
    import pymupdf
    path = tmp_path / "lines.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        for number in range(1, 10):
            page.insert_text((50, 60 + number * 24), f"Evidence line {number} remains readable.")
        pdf.save(path)
    digest = DocumentSource(path, "legacy").resolved_sha256()
    found = render_region(None, path, digest, quote="Evidence line 5 remains readable.", pdf_page=None)
    assert found["status"] == "located"
    crop = found["crops"][0]
    with pymupdf.open(path) as pdf:
        page = pdf[0]
        second = page.search_for("Evidence line 2")[0]
        eighth = page.search_for("Evidence line 8")[0]
        first = page.search_for("Evidence line 1")[0]
        ninth = page.search_for("Evidence line 9")[0]
        assert crop["clip_bbox_pdf"][1] <= second.y0
        assert crop["clip_bbox_pdf"][3] >= eighth.y1
        assert crop["clip_bbox_pdf"][1] > first.y1
        assert crop["clip_bbox_pdf"][3] < ninth.y0
        assert crop["height"] < page.rect.height * 300 / 72 / 2


def test_two_column_crop_does_not_include_neighbor_column(tmp_path):
    import pymupdf
    path = tmp_path / "columns.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        for number in range(7):
            page.insert_text((50, 90 + number * 20), f"Left result line {number}.")
            page.insert_text((340, 90 + number * 20), f"Right unrelated line {number}.")
        pdf.save(path)
    digest = DocumentSource(path, "legacy").resolved_sha256()
    found = render_region(None, path, digest, quote="Left result line 3.", pdf_page=None)
    assert found["status"] == "located"
    assert all(crop["clip_bbox_pdf"][2] < 340 for crop in found["crops"])


def test_quote_spanning_two_adjacent_pages_has_two_crops(tmp_path):
    import pymupdf
    path = tmp_path / "spanning.pdf"
    with pymupdf.open() as pdf:
        first = pdf.new_page()
        first.insert_text((50, 100), "The measured critical temperature")
        second = pdf.new_page()
        second.insert_text((50, 100), "reached 200 K under pressure.")
        pdf.save(path)
    digest = DocumentSource(path, "legacy").resolved_sha256()
    found = render_region(None, path, digest,
                          quote="The measured critical temperature reached 200 K under pressure.", pdf_page=None)
    assert found["status"] == "located"
    assert found["page_end"] == 2
    assert [crop["pdf_page"] for crop in found["crops"]] == [1, 2]
    assert all(crop["highlights"] for crop in found["crops"])


def test_low_resolution_scan_is_reported_without_lowering_render_dpi(tmp_path):
    from io import BytesIO
    import pymupdf
    from PIL import Image
    picture = BytesIO()
    Image.new("RGB", (100, 100), "white").save(picture, format="PNG")
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_image(pymupdf.Rect(50, 50, 350, 350), stream=picture.getvalue())
        pdf.save(path)
    with pymupdf.open(path) as pdf:
        crop = render_evidence_crops(pdf[0], [pymupdf.Rect(100, 100, 200, 200)])[0]
    assert crop["source_raster_dpi"] < 300
    assert crop["width"] > 400  # 100 PDF 点按 300 DPI，而非放大旧预览图。


def test_legacy_pdf_rejects_nonunique_quote(tmp_path):
    import pymupdf
    path = tmp_path / "repeated.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 100), "Tc = 200 K at 150 GPa.")
        page.insert_text((50, 200), "Tc = 200 K at 150 GPa.")
        pdf.save(path)
    digest = DocumentSource(path, "legacy").resolved_sha256()
    assert render_region(None, path, digest, quote="Tc = 200 K at 150 GPa.", pdf_page=None)["status"] == "unlocated"


def test_legacy_upload_returns_authenticated_pdf_for_on_demand_lookup(tmp_path, monkeypatch):
    from backend.ingest import upload_tasks
    path, ir = make_document(tmp_path)
    file_id = "source-file"
    monkeypatch.setattr(upload_tasks, "get_state", lambda _: {"user_id": 2, "files": [
        {"file_id": file_id, "stored_path": str(path), "sha256": ir.source_sha256, "kind": "pdf"}]})
    monkeypatch.setattr(upload_tasks, "data_path", lambda _: tmp_path)
    found_ir, found_path, found_hash = region_document(None, "upload", "a" * 32, file_id,
        SimpleNamespace(id=2, role="user", is_approved=True))
    assert found_ir is None
    assert found_path == path
    assert found_hash == ir.source_sha256


def test_image_evidence_requires_a_real_figure_block(tmp_path):
    path, ir = make_document(tmp_path)
    block = ir.blocks[0]
    block.block_type = "figure"
    located = render_region(ir, path, ir.source_sha256, quote="", pdf_page=1,
                            block_id=block.block_id)
    assert located["status"] == "located"
    assert located["dpi"] == 300
    assert located["crops"][0]["clip_bbox_pdf"][3] < ir.pages[0].height
    block.block_type = "text"
    assert render_region(ir, path, ir.source_sha256, quote="", pdf_page=1,
                         block_id=block.block_id)["status"] == "unlocated"


def test_trusted_figure_crop_includes_nearby_caption(tmp_path):
    import pymupdf
    path = tmp_path / "figure.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 100), "Tc trend image")
        page.insert_text((50, 140), "Figure 1. Tc trend at 150 GPa")
        pdf.save(path)
    ir = PyMuPDFParser().parse(DocumentSource(path, "original"), ParseOptions())
    assert len(ir.blocks) == 2
    ir.blocks[0].block_type = "figure"
    ir.blocks[1].block_type = "caption"
    found = render_region(ir, path, ir.source_sha256, quote="", pdf_page=1,
                          block_id=ir.blocks[0].block_id)
    assert found["status"] == "located"
    assert found["dpi"] == 300
    assert len(found["crops"]) == 1
    assert found["crops"][0]["clip_bbox_pdf"][3] > ir.blocks[1].bbox[3]


def test_upload_region_checks_owner_before_reading_path(monkeypatch):
    from backend.ingest import upload_tasks
    monkeypatch.setattr(upload_tasks,"get_state",lambda _:{"user_id":2,"files":[]})
    with pytest.raises(HTTPException) as error:
        region_document(None,"upload","a"*32,"f",SimpleNamespace(id=1,role="user",is_approved=True))
    assert error.value.status_code==403
