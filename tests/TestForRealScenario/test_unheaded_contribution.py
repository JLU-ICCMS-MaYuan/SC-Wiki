"""无章节小标题的本文结果必须贯穿流程选择、分类与来源核对。"""
import pytest

from backend.ingest import parsing_workflows as workflows
from backend.ingest.theoretical_subtype import assess_candidate
from backend.ingest.property_evidence import checked_result
from backend.ingest.scientific_evidence import field_records, PAPER_FIELDS

SOURCES = [dict(file_id="main", file_role="main", chunk_index=0, section_role="other",
    content="We predict YH10 with a Tc of 303 K at 400 GPa using calculated electron-phonon coupling.")]


def classification(ids=None):
    return dict(value="calculation", reason="本文用既有方法预测YH10的临界温度和电声耦合。",
        evidences=[{"source_id": "review-source-0"}],
        contribution_source_ids=["review-source-0"] if ids is None else ids)


def test_unheaded_results_route_to_current_workflow():
    raw = dict(paper_type="theoretical", theoretical_subtype="calculation",
        superconductor_kind="conventional", reason=classification()["reason"],
        source_ids=["review-source-0"], contribution_source_ids=["review-source-0"], paper={})
    report = workflows.assess(SOURCES, complete=lambda *_a, **_kw: raw)
    assert report["status"] == "matched"
    assert report["evidences"][0]["section_role"] == "other"


def test_unheaded_contribution_survives_classification_and_field_check():
    assessment = assess_candidate(SOURCES, classification())
    assert assessment["status"] == "completed"
    row = next(r for r in field_records("paper", "paper", {"theoretical_subtype": "calculation"},
        PAPER_FIELDS, assessment=assessment) if r["field"] == "paper.theoretical_subtype")
    checked = checked_result(row, {"status": "supported", "reason": "本文结果支持", "evidences": []}, SOURCES)
    assert checked["status"] == "supported"
    assert checked["evidences"][0]["section_role"] == "other"


@pytest.mark.parametrize("ids", [[], ["review-source-999"], ["review-source-1"]])
def test_missing_forged_or_unselected_contribution_cannot_pass(ids):
    extra = {**SOURCES[0], "chunk_index": 1, "content": "Other material."}
    assert assess_candidate([*SOURCES, extra], classification(ids))["status"] == "uncertain"


def test_supplement_only_cannot_claim_main_paper_contribution():
    sources = [{**SOURCES[0], "file_role": "supplementary"}]
    assert assess_candidate(sources, classification())["status"] == "uncertain"


def test_reference_cannot_claim_main_paper_contribution():
    sources = [{**SOURCES[0], "section_role": "reference"}]
    assert assess_candidate(sources, classification())["status"] == "uncertain"


@pytest.mark.parametrize("ids", [[], ["review-source-999"], ["review-source-1"]])
def test_workflow_rejects_invalid_contribution_even_with_result_heading(ids):
    sources = [{**SOURCES[0], "section_role": "result"},
               {**SOURCES[0], "chunk_index": 1, "section_role": "method"}]
    raw = dict(paper_type="theoretical", theoretical_subtype="calculation",
        superconductor_kind="conventional", reason=classification()["reason"],
        source_ids=["review-source-0"], contribution_source_ids=ids, paper={})
    assert workflows.assess(sources, complete=lambda *_a, **_kw: raw)["status"] == "uncertain"


def test_content_assessment_relocates_source_during_formal_handoff():
    from copy import deepcopy
    from backend.ingest.scientific_evidence import transfer_result
    from backend.ingest.property_evidence import complete_snapshot
    assessment = assess_candidate(SOURCES, classification())
    row = next(r for r in complete_snapshot("upload", "same-paper", field_records("paper", "paper",
        {"theoretical_subtype": "calculation"}, PAPER_FIELDS, assessment=assessment), SOURCES, {})["records"]
        if r["field"] == "paper.theoretical_subtype")
    result = checked_result(row, {"status": "supported", "reason": "已核对", "evidences": []}, SOURCES)
    formal = [{**SOURCES[0], "file_id": "42", "chunk_id": 51}]
    transferred = transfer_result(deepcopy(row), result, formal, {"main": "42"})
    assert transferred["status"] == "supported"
    assert transferred["evidences"][0]["file_id"] == "42"
    assert transferred["provenance"]["assessment"]["contribution_basis"] == "content"
    assert checked_result(transferred, {"status": "supported", "reason": "重读核对", "evidences": []}, formal)["status"] == "supported"
