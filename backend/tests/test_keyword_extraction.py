"""关键词优先采用原文列表，并在无列表时覆盖全文。"""

import json
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/scwiki-keywords-test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

from backend.ingest.keyword_extraction import select_keywords, task_sources
from backend.ingest.language_contract import GeneratedFieldLanguageError, validate_draft_generated_english
from backend.ingest.property_evidence import _fill_empty_fields, checked_result, source_chunks
from backend.ingest.scientific_evidence import field_records


def source(content, role="main", file_id="main"):
    return {"file_id": file_id, "role": role, "source_name": file_id + ".pdf", "content": content}


def forbidden_model(*_args):
    raise AssertionError("作者关键词已找到，不应调用全文提炼模型")


def test_author_keywords_keep_original_language_order_and_front_matter_page():
    text = "<!-- page: 1 -->\n博士学位论文\n关键词：高压超导；富氢化合物；晶体结构预测\n\n## 第一章 绪论\n本文研究高压富氢化合物。"
    result = select_keywords([source(text)], complete=forbidden_model)
    assert result["status"] == "completed" and result["kind"] == "author_list"
    assert result["values"] == ["高压超导", "富氢化合物", "晶体结构预测"]
    assert result["evidences"][0]["page_start"] == 1
    assert result["evidences"][0]["quote"] == "关键词：高压超导；富氢化合物；晶体结构预测"
    validate_draft_generated_english({"paper": {"keywords_tags": result["values"]}, "keyword_assessment": result})
    with pytest.raises(GeneratedFieldLanguageError):
        validate_draft_generated_english({"paper": {"keywords_tags": result["values"]}})


def test_english_keywords_preserve_parenthesized_comma_and_ignore_supplement():
    main = source("<!-- page: 2 -->\nAbstract text about hydrides.\nKeywords: (La,Ce)H9, pressure, superconductivity\n\n## Results\nThe sample is superconducting.")
    supplement = source("Keywords: incorrect, supplementary\nAdditional measurements.", "supplementary", "supp")
    result = select_keywords([main, supplement], complete=forbidden_model)
    assert result["values"] == ["(La,Ce)H9", "pressure", "superconductivity"]
    assert result["evidences"][0]["file_id"] == "main"


def test_standalone_keyword_heading_skips_document_block_marker():
    text = ("<!-- page: 1 -->\n## Abstract\nThe paper studies hydrides.\n"
            "## Keywords\n<!-- block: keyword-values -->\nhydrides; pressure; superconductivity\n"
            "## Introduction\nThe study continues here.")
    result = select_keywords([source(text)], complete=forbidden_model)
    assert result["kind"] == "author_list"
    assert result["values"] == ["hydrides", "pressure", "superconductivity"]


def test_pdf_text_layer_through_task_sources_keeps_author_keywords(tmp_path):
    import fitz
    from backend.ingest.pdf_extractor import extract_text_from_pdf

    pdf_path = tmp_path / "paper.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((60, 70), "Keywords: hydrides; high pressure; superconductivity")
        page.insert_text((60, 100), "The authors study a high pressure hydride phase.")
        pdf.save(pdf_path)
    root = tmp_path / "parsed_markdown"
    task_id = "a" * 32
    stored = root / task_id / "main.md"
    stored.parent.mkdir(parents=True)
    stored.write_text(extract_text_from_pdf(pdf_path), encoding="utf-8")
    state = {"files": [{"file_id": "main", "role": "main", "kind": "pdf", "original_filename": "paper.pdf"}]}
    result = select_keywords(task_sources(task_id, state, root), complete=forbidden_model)
    assert result["values"] == ["hydrides", "high pressure", "superconductivity"]
    assert result["evidences"][0]["page_start"] == 1


def test_reference_keyword_label_does_not_count_as_author_list():
    text = "<!-- page: 1 -->\n## Introduction\nThe present paper studies a material using a new method.\n## References\nKeywords: unrelated; cited paper"
    calls = []

    def model(prompt, payload):
        calls.append(prompt)
        sources = json.loads(payload).get("sources")
        if sources is not None:
            return {"summary": "The current paper studies a material and a method.",
                    "evidences": [{"file_id": "main", "quote": "The present paper studies a material using a new method."}]}
        return {"keywords_tags": ["material study", "new method", "research result"]}

    result = select_keywords([source(text)], complete=model)
    assert result["kind"] == "fulltext_synthesis" and len(calls) == 2
    assert "unrelated" not in result["values"]


def test_fulltext_reads_every_batch_and_failure_does_not_use_partial_values(monkeypatch):
    from backend.ingest import property_evidence

    monkeypatch.setattr(property_evidence, "SOURCE_BATCH_CHARS", 100)
    text = ("<!-- page: 1 -->\n## Introduction\n" +
            "The current paper studies sulfur hydride superconductivity at high pressure. " * 5 +
            "\n## Results\n" +
            "Density functional calculations find a superconducting transition. " * 5)
    batches = []

    def model(prompt, payload):
        parsed = json.loads(payload)
        if "sources" in parsed:
            batch = parsed["sources"]
            batches.append(batch)
            return {"summary": "This window describes the current paper's contribution.",
                    "evidences": [{"file_id": batch[0]["file_id"], "chunk_index": batch[0]["chunk_index"],
                                   "quote": "The current paper studies sulfur hydride superconductivity at high pressure."
                                   if "The current paper" in batch[0]["content"] else "Density functional calculations find a superconducting transition."}]}
        return {"keywords_tags": ["sulfur hydride", "superconductivity", "high pressure"]}

    result = select_keywords([source(text)], complete=model)
    assert result["kind"] == "fulltext_synthesis"
    assert result["covered_batches"] == result["total_batches"] == len(batches) >= 2
    assert result["evidences"]

    attempts = 0

    def fail_second(prompt, payload):
        nonlocal attempts
        if "sources" in json.loads(payload):
            attempts += 1
            if attempts == 2:
                raise RuntimeError("model down")
        return model(prompt, payload)

    failed = select_keywords([source(text)], complete=fail_second)
    assert failed["status"] == "failed" and failed["values"] == []
    assert failed["covered_batches"] < failed["total_batches"]


def test_fulltext_rejects_non_english_or_short_model_output():
    text = "<!-- page: 1 -->\nThe present paper studies hydrides under pressure with calculations."

    def model(_prompt, payload):
        if "sources" in json.loads(payload):
            return {"summary": "Hydrides and high-pressure calculations are studied.",
                    "evidences": [{"file_id": "main", "quote": "The present paper studies hydrides under pressure with calculations."}]}
        return {"keywords_tags": ["富氢化合物", "high pressure", "calculations"]}

    rejected = select_keywords([source(text)], complete=model)
    assert rejected["kind"] == "none" and rejected["values"] == []

    def too_short(prompt, payload):
        if "sources" in json.loads(payload):
            return model(prompt, payload)
        return {"keywords_tags": ["hydrides"]}

    assert select_keywords([source(text)], complete=too_short)["values"] == []


def test_keyword_source_is_bound_to_current_value():
    text = "<!-- page: 1 -->\nKeywords: hydrides; pressure\n## Results\nThe paper studies hydrides under pressure."
    chunks = source_chunks(text, "main")
    assessment = select_keywords([source(text)], complete=forbidden_model)
    row = field_records("paper", "paper", {"keywords_tags": assessment["values"]},
                        {"keywords_tags": "科学关键词"}, keyword_assessment=assessment)[0]
    current = checked_result(row, {"status": "supported", "reason": "作者列出关键词", "evidences": []}, chunks)
    assert current["source_kind"] == "author_keywords"
    assert current["evidences"]
    assert checked_result(row, {"status": "unsupported", "reason": "模型误判", "evidences": []}, chunks)["status"] == "supported"
    changed = field_records("paper", "paper", {"keywords_tags": ["edited term"]},
                            {"keywords_tags": "科学关键词"}, keyword_assessment=assessment)[0]
    assert "provenance" not in changed and changed["evidences"] == []


def test_partial_source_suggestion_cannot_fill_empty_keyword_field():
    draft = {"paper": {"keywords_tags": []}}
    record = {"field": "paper.keywords_tags", "editable_fields": [{"path": "paper.keywords_tags", "value": []}]}
    proposal = {"basis_kind": "paper_inference", "values": {"paper.keywords_tags": ["hydrides"]}}
    assert not _fill_empty_fields(draft, record, proposal)
    assert draft["paper"]["keywords_tags"] == []
