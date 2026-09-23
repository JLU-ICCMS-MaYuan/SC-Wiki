"""Issue #114 基础契约测试。"""

from pathlib import Path

import pytest

from backend.ingest.claim_evidence import (
    BasisKind,
    Claim,
    ClaimStatus,
    EvidenceLocator,
    SourceKind,
    validate_claim,
)
from backend.ingest.coverage_audit import audit_coverage
from backend.ingest.document_ir import BlockType, DocumentBlock, DocumentIR, PageGeometry, content_hash
from backend.ingest.document_parsers import (
    DocumentSource,
    ParseOptions,
    ParserError,
    ParserProfile,
    ParserRegistry,
    RuntimeCapabilities,
    parse_with_profile,
)
from backend.ingest.parser_rollout import RolloutConfig, RolloutStage, select_profile


def _ir() -> DocumentIR:
    text = "The critical temperature reaches 200 K at 150 GPa."
    bbox = (0.0, 0.0, 300.0, 30.0)
    return DocumentIR(
        document_id="doc-1:1:pymupdf",
        source_file_id="file-1",
        source_sha256="a" * 64,
        parse_profile="text",
        parser={"name": "pymupdf", "version": "1"},
        pages=[PageGeometry(pdf_page=1, width=600, height=800)],
        blocks=[DocumentBlock(
            block_id="block-1", block_type=BlockType.PARAGRAPH, pdf_page=1,
            reading_order=0, text=text, bbox=bbox, page_width=600, page_height=800,
            content_hash=content_hash(text, bbox),
        )],
    )


def test_document_ir_rejects_out_of_bounds_geometry():
    with pytest.raises(ValueError, match="超出页面边界"):
        DocumentBlock(
            block_id="block-1", block_type=BlockType.PARAGRAPH, pdf_page=1,
            reading_order=0, bbox=(0, 0, 700, 30), page_width=600, page_height=800,
            content_hash="a" * 64,
        )


def test_claim_evidence_must_resolve_in_same_ir():
    ir = _ir()
    claim = Claim(
        claim_id="claim-1", target_path="material_states[0].property_modules[0].records[0]",
        value={"tc": 200}, raw_value="200 K", basis_kind=BasisKind.PAPER_QUOTE,
        source_kind=SourceKind.TEXT_LAYER, evidences=[EvidenceLocator(
            file_id="file-1", pdf_page=1, block_id="block-1", quote="200 K",
            parser="pymupdf", parser_version="1", source_kind=SourceKind.TEXT_LAYER,
        )],
    )
    result = validate_claim(claim, ir)
    assert result.valid is True
    assert result.claim.status is ClaimStatus.VALIDATED


def test_claim_from_another_file_is_uncertain():
    ir = _ir()
    claim = Claim(
        claim_id="claim-2", target_path="x", value=1, raw_value="1",
        basis_kind=BasisKind.PAPER_QUOTE, source_kind=SourceKind.TEXT_LAYER,
        evidences=[EvidenceLocator(file_id="other", pdf_page=1, quote="1", parser="x", parser_version="1")],
    )
    result = validate_claim(claim, ir)
    assert result.valid is False
    assert "文件" in result.reasons[0]


def test_coverage_reports_uncovered_claim_and_truncation():
    ir = _ir()
    claim = Claim(claim_id="claim-3", target_path="x", value=1, raw_value="1", basis_kind=BasisKind.PAPER_INFERENCE, source_kind=SourceKind.DERIVED)
    report = audit_coverage(ir, [claim], truncated=True)
    assert report.status == "incomplete"
    assert report.uncovered_candidates == ["claim-3"]
    assert report.truncation_signals == ["output_truncated"]
    assert report.requires_human is True


def test_parser_profile_does_not_silently_switch_when_unavailable(tmp_path: Path):
    source_path = tmp_path / "paper.pdf"
    source_path.write_bytes(b"%PDF-1.4\n")
    source = DocumentSource(path=source_path, file_id="file-1")
    caps = RuntimeCapabilities(installed=frozenset())
    with pytest.raises(ParserError) as error:
        parse_with_profile(source, ParseOptions(profile=ParserProfile.LAYOUT), capabilities=caps)
    assert error.value.code == "parser_profile_unavailable"
    assert error.value.profile == ParserProfile.LAYOUT


def test_pymupdf_text_profile_returns_locatable_ir(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    source_path = tmp_path / "paper.pdf"
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_text((40, 80), "The critical temperature reaches 200 K at 150 GPa.")
    document.save(source_path)
    document.close()
    source = DocumentSource(path=source_path, file_id="file-1")
    ir, run = parse_with_profile(
        source,
        ParseOptions(profile=ParserProfile.TEXT),
        capabilities=RuntimeCapabilities(installed=frozenset({"fitz"})),
    )
    assert run.status == "succeeded"
    assert ir.blocks and ir.blocks[0].pdf_page == 1
    assert "200 K" in ir.blocks[0].text


def test_rollout_profile_is_stable_and_explicit():
    config = RolloutConfig(stage=RolloutStage.DEFAULT, default_profile=ParserProfile.LAYOUT)
    assert select_profile(config, task_id="a" * 32) == ParserProfile.LAYOUT
    assert select_profile(config, task_id="a" * 32, requested_profile=ParserProfile.TEXT) == ParserProfile.TEXT
