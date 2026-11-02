"""图片尚未读入文字步骤不等于读取失败；真实不可读和未覆盖继续阻断。"""
import pytest

from backend.ingest.coverage_audit import audit_coverage
from backend.ingest.document_ir import DocumentBlock
from test_issue114_evidence_audit import document, candidate


def region(kind="figure", text=""):
    ir = document()
    ir.blocks.append(DocumentBlock(block_id="visual", block_type=kind, pdf_page=1,
                                   reading_order=1, text=text, content_hash="e" * 64))
    return ir


@pytest.mark.parametrize("category", [None, "unreadable"])
@pytest.mark.parametrize("kind", ["figure", "formula"])
def test_empty_visual_region_keeps_location_pending_without_failing_text_coverage(category, kind):
    ir = region(kind)
    original = ir.model_dump()
    exclusions = ([{"file_id": "f", "block_id": "visual", "category": category,
                    "reason": "No image pixels were supplied."}] if category else [])
    report = audit_coverage(ir, [candidate()], processed_pages=[1], exclusions=exclusions)
    assert report.status == "complete" and not report.requires_human
    assert report.figures_without_text_layer == 1
    assert report.pending_visual_regions == [{"file_id": "f", "pdf_page": 1,
        "block_id": "visual", "block_type": kind, "status": "not_read_in_text_pass"}]
    assert not report.unreadable_regions
    if category:
        assert report.exclusions[0]["category"] == "unreadable"
        assert report.exclusions[0]["disposition"] == "pending_image_reading"
    assert ir.model_dump() == original


@pytest.mark.parametrize("kind,text", [("paragraph", "damaged text"), ("figure", "Tc versus pressure"),
                                        ("formula", "Tc = ???"), ("table", "unreadable result")])
def test_real_unreadable_content_retains_page_and_reason_and_still_blocks(kind, text):
    report = audit_coverage(region(kind, text), [candidate()], processed_pages=[1], exclusions=[{
        "file_id": "f", "block_id": "visual", "category": "unreadable", "reason": "OCR failed"}])
    assert report.requires_human and "unreadable_exclusion_present" in report.limitations
    assert report.unreadable_regions[0]["pdf_page"] == 1
    assert report.unreadable_regions[0]["reason"] == "OCR failed"
    assert not report.pending_visual_regions


def test_image_pending_never_hides_a_real_missing_result_or_parser_failure():
    ir = region()
    ir.coverage["limitations"] = ["image_reader_failed"]
    report = audit_coverage(ir, [], processed_pages=[1], exclusions=[{
        "file_id": "f", "block_id": "visual", "category": "unreadable", "reason": "No pixels"}])
    assert report.requires_human
    assert "block:b" in report.uncovered_candidates
    assert "image_reader_failed" in report.limitations


def test_page_wide_unreadable_is_not_reclassified_as_an_empty_image():
    report = audit_coverage(region(), [candidate()], processed_pages=[1], exclusions=[{
        "file_id": "f", "pdf_page": 1, "category": "unreadable", "reason": "Page OCR failed"}])
    assert report.requires_human
    assert report.unreadable_regions[0]["pdf_page"] == 1


def test_coverage_error_names_unreadable_file_page_and_reason_without_inventing_missing_claims():
    from backend.ingest.coverage_audit import coverage_failure_message
    from backend.ingest.claim_evidence import validate_claim
    ir = region("figure", "unreadable chart labels")
    report = audit_coverage(ir, [candidate()], processed_pages=[1], exclusions=[{
        "file_id": "f", "block_id": "visual", "category": "unreadable", "reason": "坐标轴文字无法读取"}])
    claim = validate_claim(candidate(), ir).claim
    text = coverage_failure_message([claim], {"f": report.model_dump()}, {"f": "SI.pdf"}, {"f": ir})
    assert "SI.pdf" in text and "第 1 页" in text and "坐标轴文字无法读取" in text
    assert "科学候选无法定位" not in text


def test_coverage_error_keeps_genuinely_unlocated_claims_and_uncovered_blocks_distinct():
    from backend.ingest.coverage_audit import coverage_failure_message
    claim = candidate(quote="invented")
    report = audit_coverage(document(), [], processed_pages=[1])
    text = coverage_failure_message([claim], {"f": report.model_dump()}, {"f": "main.pdf"}, {"f": document()})
    assert "无法定位" in text and "未覆盖" in text and "第 1 页" in text


def test_parsing_detail_exposes_pending_image_locations_without_source_paths(tmp_path, monkeypatch):
    import json
    from backend.ingest import upload_jobs, upload_tasks
    report = audit_coverage(region(), [candidate()], processed_pages=[1])
    (tmp_path / "coverage.json").write_text(json.dumps({"f": report.model_dump()}))
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: {"status": "failed", "files": []})
    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path)
    monkeypatch.setattr(upload_jobs, "_chunk_manifest_path", lambda *a, **k: tmp_path / "manifest.json")
    monkeypatch.setattr(upload_tasks, "available_published_path", lambda _, path: path)
    detail = upload_jobs.public_parsing_detail("a" * 32)
    assert detail["pending_visual_regions"] == report.pending_visual_regions
    assert "stored_path" not in json.dumps(detail)
