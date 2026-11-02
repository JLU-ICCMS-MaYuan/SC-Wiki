"""多解析器同源图注：定位沿用已选原块，备选与真实歧义保持隔离。"""
from copy import deepcopy
import json

import pytest

from backend.ingest.document_claims import apply_claim_evidence, claims_from_candidates
from backend.ingest.document_ir import DocumentBlock, DocumentIR, PageGeometry, content_hash


QUOTE = "CaH6 at 150 GPa has Tc = 235 K. DFT structural relaxation was performed."


def sources(selected=(True, False)):
    blocks = []
    for index, (engine, active) in enumerate(zip(("mineru", "marker"), selected)):
        blocks.append(DocumentBlock(
            block_id=engine + "-caption", block_type="caption", pdf_page=1,
            reading_order=index, text=QUOTE, bbox=(10, 10, 300, 100),
            content_hash=content_hash(QUOTE, engine),
            metadata={"source_parser": engine, "selected_for_reading": active,
                      "source_kind": "ocr" if engine == "mineru" else "vision"},
        ))
    ir = DocumentIR(
        document_id="complementary-document", source_file_id="main", source_sha256="a" * 64,
        parse_profile="complementary", parser={"name": "complementary", "version": "1", "mode": "ocr"},
        pages=[PageGeometry(pdf_page=1, width=600, height=800)], blocks=blocks,
    )
    return {"main": ir}


def candidate(evidence=None):
    return {"material_states": [{
        "material": "CaH6", "pressure_value_gpa": 150, "structure_optimization": "classical_static",
        "evidences": [evidence or {"file_id": "main", "quote": QUOTE}],
        "tc_results": [{"tc_value_k": 235, "tc_method": "unknown", "result_kind": "theoretical"}],
    }]}


def test_selected_mineru_block_survives_claim_application_and_reread():
    documents, draft = sources(), candidate()
    original = deepcopy(draft)
    original_ir = documents["main"].model_dump()
    claims = claims_from_candidates(draft, documents)
    assert len(claims) == 2
    assert all(c.status == "validated" for c in claims)
    assert all(e.block_id == "mineru-caption" and e.source_kind == "ocr"
               for c in claims for e in c.evidences)
    apply_claim_evidence(draft, claims)
    reread = json.loads(json.dumps(draft))
    assert [(c.target_path, c.value) for c in claims_from_candidates(reread, documents)] == [
        (c.target_path, c.value) for c in claims_from_candidates(original, documents)]
    assert all(c.status == "validated" for c in claims_from_candidates(reread, documents))
    assert documents["main"].model_dump() == original_ir


def test_selection_can_use_marker_instead_of_hardcoding_mineru():
    claims = claims_from_candidates(candidate(), sources((False, True)))
    assert all(c.status == "validated" for c in claims)
    assert {e.block_id for c in claims for e in c.evidences} == {"marker-caption"}


@pytest.mark.parametrize("selected", [(True, True), (False, False)])
def test_multiple_or_missing_selected_blocks_remain_uncertain(selected):
    assert all(c.status == "uncertain" for c in claims_from_candidates(candidate(), sources(selected)))


def test_quote_only_present_in_unselected_backup_is_not_implicitly_adopted():
    documents = sources()
    documents["main"].blocks[0].text = "The selected source does not report this result."
    assert all(c.status == "uncertain" for c in claims_from_candidates(candidate(), documents))


def test_explicit_backup_reference_keeps_existing_access_and_validation():
    draft = candidate({"file_id": "main", "quote": QUOTE, "block_id": "marker-caption"})
    claims = claims_from_candidates(draft, sources())
    assert all(c.status == "validated" for c in claims)
    assert {e.block_id for c in claims for e in c.evidences} == {"marker-caption"}


@pytest.mark.parametrize("invalid", [
    {"file_id": "other"}, {"pdf_page": 2}, {"block_id": "missing"},
    {"quote": "The model invented this sentence."}, {"source_version": 2},
    {"parser": "different-parser"}, {"parser_version": "old"},
    {"source_kind": "text_layer"}, {"bbox": [10, 10, 301, 100]},
])
def test_invalid_identity_or_quote_is_never_repaired_by_source_selection(invalid):
    evidence = {"file_id": "main", "quote": QUOTE, "block_id": "mineru-caption", **invalid}
    assert all(c.status == "uncertain" for c in claims_from_candidates(candidate(evidence), sources()))


@pytest.mark.parametrize("duplicates", [False, True])
def test_legacy_sources_without_selection_metadata_still_require_uniqueness(duplicates):
    documents = sources()
    for block in documents["main"].blocks:
        block.metadata.pop("selected_for_reading")
    if not duplicates:
        documents["main"].blocks.pop()
    expected = "uncertain" if duplicates else "validated"
    assert all(c.status == expected for c in claims_from_candidates(candidate(), documents))
