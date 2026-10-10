"""当前字段来源必须与原 PDF 的实际页和正文首页书目一致。"""

from contextlib import nullcontext

import pymupdf
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend import models
from backend.database import Base
from backend.ingest import property_evidence as evidence
from backend.ingest import pdf_source_pages
from backend.ingest import repair_pending_pdf_evidence as repair
from backend.ingest.document_parsers import DocumentSource
from backend.ingest.pdf_front_matter import correct_front_matter_results
from backend.ingest.scientific_evidence import item_identity
from backend.ingest.scientific_evidence import transfer_result


def fixture(tmp_path, monkeypatch):
    from backend.ingest import upload_tasks
    path = tmp_path / "main.pdf"
    title = "Pressure-induced superconductivity in H2S"
    authors = ["Defang Duan", "Tian Cui"]
    with pymupdf.open() as pdf:
        front = pdf.new_page()
        front.insert_text((50, 80), title)
        front.insert_text((50, 110), "Defang Duan, Tian Cui")
        front.insert_text((50, 170), "Tc reaches 200 K at 150 GPa.")
        last = pdf.new_page()
        last.insert_text((50, 80), "How to cite this article: " + title)
        pdf.save(path)
    digest = DocumentSource(path, "main").resolved_sha256()
    monkeypatch.setattr(upload_tasks, "get_state", lambda _: {"user_id": 2, "files": [{
        "file_id": "main", "role": "main", "kind": "pdf", "stored_path": str(path),
        "sha256": digest, "original_filename": "main.pdf"}]})
    records = [
        {"key": "title", "item_key": "t", "field": "paper.title", "current_value": title,
         "content_hash": "title-value", "source_hash": "source"},
        {"key": "authors", "item_key": "a", "field": "paper.authors", "current_value": authors,
         "content_hash": "author-value", "source_hash": "source"},
        {"key": "tc", "item_key": "c", "field": "material_states[0].tc", "current_value": 200,
         "content_hash": "tc-value", "source_hash": "source"},
    ]
    chunks = [
        {"file_id": "main", "chunk_index": 0, "heading": "## " + title,
         "section": title, "content": "Defang Duan, Tian Cui", "source_name": "main.pdf"},
        {"file_id": "main", "chunk_index": 1, "heading": "## Results",
         "section": "Results", "content": "Tc reaches 200 K at 150 GPa.", "source_name": "main.pdf"},
        {"file_id": "main", "chunk_index": 2, "heading": "## References",
         "section": "References", "content": "How to cite this article: " + title, "source_name": "main.pdf"},
    ]
    snapshot = {"target": "upload", "target_id": "fixture", "rule_version": "scientific-evidence-v7",
                "records": records, "chunks": chunks, "pdf_manifest": [{"file_id": "main", "role": "main",
                    "kind": "pdf", "stored_path": str(path), "sha256": digest, "original_filename": "main.pdf"}]}
    return path, snapshot


def test_title_and_authors_use_main_pdf_front_page_not_last_citation(tmp_path, monkeypatch):
    _, snapshot = fixture(tmp_path, monkeypatch)
    old = {"title": {"status": "supported", "evidences": [{"file_id": "main", "chunk_index": 2,
        "quote": "How to cite this article: " + snapshot["records"][0]["current_value"]}]}}
    corrected = correct_front_matter_results(None, snapshot, old)
    assert corrected["title"]["evidences"][0]["page_start"] == 1
    assert corrected["title"]["evidences"][0]["quote"] == snapshot["records"][0]["current_value"]
    assert "How to cite" not in corrected["title"]["evidences"][0]["quote"]
    assert corrected["authors"]["evidences"][0]["page_start"] == 1
    assert evidence.locate_with_reason(corrected["title"]["evidences"][0], snapshot["chunks"])[0]["page_start"] == 1


def test_wrong_page_hint_is_corrected_and_repeated_quote_loses_support(tmp_path, monkeypatch):
    _, snapshot = fixture(tmp_path, monkeypatch)
    old = {"tc": {"status": "supported", "evidences": [{"file_id": "main", "chunk_index": 1,
        "page_start": 2, "quote": "Tc reaches 200 K at 150 GPa."}]}}
    corrected = pdf_source_pages.correct_pdf_source_pages(None, snapshot, old)
    assert corrected["tc"]["status"] == "supported"
    assert corrected["tc"]["evidences"][0]["page_start"] == 1
    assert corrected["tc"]["evidences"][0]["locator_status"] == "verified_text_layer"
    repeated = {"tc": {"status": "supported", "evidences": [{"file_id": "main", "chunk_index": 1,
        "quote": "H2S"}]}}
    ambiguous = pdf_source_pages.correct_pdf_source_pages(None, snapshot, repeated)
    assert ambiguous["tc"]["status"] == "missing"
    assert ambiguous["tc"]["evidences"][0]["locator_status"] == "ambiguous"


def test_unverified_front_page_is_a_gap_and_approved_history_is_untouched(tmp_path, monkeypatch):
    _, snapshot = fixture(tmp_path, monkeypatch)
    old = {"title": {"status": "supported", "evidences": [{"file_id": "main", "chunk_index": 2,
        "quote": "How to cite this article: " + snapshot["records"][0]["current_value"]}]}}
    snapshot["pdf_manifest"][0]["sha256"] = "0" * 64
    missing = pdf_source_pages.current_pdf_results(None, snapshot, old)
    assert missing["title"]["status"] == "missing"
    assert missing["title"]["evidences"] == []
    approved = {**snapshot, "target": "paper", "target_id": "29", "review_state": ["approved", None, 1]}
    assert pdf_source_pages.current_pdf_results(None, approved, old) == old


def test_pending_title_repair_backs_up_before_write_and_is_idempotent(tmp_path, monkeypatch):
    from backend.ingest import upload_tasks
    _, snapshot = fixture(tmp_path, monkeypatch)
    engine = create_engine("sqlite:///:memory:")
    models.Paper.__table__.create(engine)
    models.ScientificEvidenceSource.__table__.create(engine)
    models.ScientificEvidenceCheck.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repair, "SessionLocal", factory)
    monkeypatch.setattr(evidence, "upload_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(upload_tasks, "upload_task_lock", lambda _: nullcontext())
    old_quote = "How to cite this article: " + snapshot["records"][0]["current_value"]
    with factory.begin() as session:
        session.add(models.ScientificEvidenceCheck(target="upload", target_id="fixture", item_key="t",
            content_hash="title-value", source_hash="source", rule_version="scientific-evidence-v7",
            actor_user_id=2, resolutions={}, result={"status": "supported", "evidences": [{
                "file_id": "main", "chunk_index": 2, "quote": old_quote}], "history": [{
                "status": "supported", "evidences": [{"file_id": "main", "quote": old_quote}]}]}))
    backup_dir = tmp_path / "backups"
    assert repair.run(target_id="fixture", backup_root=backup_dir) == 1
    with factory() as session:
        assert session.query(models.ScientificEvidenceCheck).one().result["evidences"][0]["quote"] == old_quote
    assert not backup_dir.exists()
    assert repair.run(apply=True, target_id="fixture", backup_root=backup_dir) == 1
    with factory() as session:
        saved = session.query(models.ScientificEvidenceCheck).one().result
        assert saved["evidences"][0]["page_start"] == 1
        assert saved["evidences"][0]["quote"] == snapshot["records"][0]["current_value"]
        assert saved["history"] == []
    backups = list(backup_dir.glob("*.json"))
    assert len(backups) == 1
    assert backups[0].stat().st_mode & 0o777 == 0o600
    assert repair.run(apply=True, target_id="fixture", backup_root=backup_dir) == 0
    engine.dispose()


def test_pending_paper_repair_updates_permanent_source_and_review_snapshot(tmp_path, monkeypatch):
    path, _ = fixture(tmp_path, monkeypatch)
    title = "Pressure-induced superconductivity in H2S"
    old_quote = "How to cite this article: " + title
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repair, "SessionLocal", factory)
    with factory.begin() as session:
        paper = models.Paper(title=title, year=2026, content_revision=1, review_status="pending")
        session.add(paper)
        session.flush()
        file = models.PaperFile(paper_id=paper.id, paper_revision=1, role="main", sort_order=0,
            original_filename="main.pdf", stored_path=str(path),
            sha256=DocumentSource(path, "main").resolved_sha256(), size=path.stat().st_size)
        session.add(file)
        session.flush()
        chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=file.id,
            chunk_index=0, section_name=title, content="Defang Duan, Tian Cui")
        session.add(chunk)
        session.flush()
        key = item_identity("paper", "title")
        session.add(models.ScientificEvidenceSource(paper_id=paper.id, paper_revision=1,
            item_key=key, field_path="paper.title", content_hash="old", source_hash="old",
            rule_version="scientific-evidence-v7", result={"status": "supported", "evidences": [{
                "file_id": str(file.id), "chunk_index": 0, "quote": old_quote}]}))
        session.add(models.PaperEvidence(paper_id=paper.id, paper_revision=1, paper_chunk_id=chunk.id,
            field_path="paper.title", quote=old_quote, page_start=2))
        session.add(models.PaperHistoryEvent(paper_id=paper.id, paper_revision=1,
            event_type="reviewed", review_status="pending", classification_snapshot={"evidence_review": [{
                "field": "paper.title", "evidences": [{"file_id": str(file.id), "quote": old_quote}]}]}))
        paper_id = str(paper.id)
    assert repair.run(apply=True, target_id=paper_id, backup_root=tmp_path / "paper-backup") >= 3
    with factory() as session:
        source = session.query(models.ScientificEvidenceSource).one()
        assert source.result["evidences"][0]["page_start"] == 1
        assert session.query(models.PaperEvidence).count() == 0
        history = session.query(models.PaperHistoryEvent).one().classification_snapshot
        assert history["evidence_review"][0]["evidences"][0]["page_start"] == 1
    engine.dispose()


def test_front_page_title_survives_upload_to_paper_chunk_rebinding():
    title = "Pressure-induced superconductivity in H2S"
    record = {"key": "title", "item_key": "title-key", "field": "paper.title",
              "content_hash": "value", "source_hash": "source"}
    result = {"content_hash": "value", "source_hash": "source", "status": "supported",
              "evidences": [{"file_id": "main", "chunk_index": 0, "page_start": 1, "page_end": 1,
                             "quote": title, "origin_kind": "verified_front_matter"}]}
    chunks = [{"file_id": "9", "chunk_id": 42, "chunk_index": 0,
               "section": title, "content": "Defang Duan, Tian Cui", "page_start": None}]
    transferred = transfer_result(record, result, chunks, {"main": "9"})
    assert transferred["evidences"][0]["chunk_id"] == 42
    assert transferred["evidences"][0]["page_start"] == 1
    assert transferred["evidences"][0]["quote"] == title
