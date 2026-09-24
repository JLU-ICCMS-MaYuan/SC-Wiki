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


def test_upload_region_checks_owner_before_reading_path(monkeypatch):
    from backend.ingest import upload_tasks
    monkeypatch.setattr(upload_tasks,"get_state",lambda _:{"user_id":2,"files":[]})
    with pytest.raises(HTTPException) as error:
        region_document(None,"upload","a"*32,"f",SimpleNamespace(id=1,role="user",is_approved=True))
    assert error.value.status_code==403
