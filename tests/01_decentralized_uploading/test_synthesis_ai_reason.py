"""模型归纳字段必须把判断桥梁送到 AI 理由，直接来源保持原语义。"""

import json

from backend.ingest import property_evidence as evidence


QUOTE = "Hydrogen-rich (H2S)2H2 was investigated for high-pressure superconductivity."
CHUNKS = [{"file_id": "main", "chunk_index": 0, "content": QUOTE,
           "section": "Results", "page_start": 2, "page_end": 2}]
SOURCE = {"file_id": "main", "chunk_index": 0, "quote": QUOTE}
LOGIC = "论文将 (H2S)2H2 称为富氢材料并研究其高压超导；现有氢基家族涵盖这类体系，分类限于本文研究对象。"


def row(field="paper.material_families", *, synthesis=True, provenance=None):
    return {"key": field, "item_key": field, "field": field, "label": "材料家族",
            "claim": {"value": ["氢基超导体"]}, "current_value": ["氢基超导体"],
            "kind": "field", "required": True, "evidences": [],
            "content_hash": "content", "source_hash": "source",
            **({"check_mode": "synthesis"} if synthesis else {}),
            **({"provenance": provenance} if provenance else {})}


def check(reason=LOGIC, status="supported"):
    return {"status": status, "reason": reason, "evidences": [SOURCE]}


def test_old_supported_family_reason_becomes_current_ai_explanation():
    result = evidence.checked_result(row(), check(), CHUNKS)
    assert result["status"] == "supported"
    assert result["source_kind"] == "paper_synthesis"
    assert result["ai_reason"] == LOGIC
    assert result["evidences"][0]["quote"] == QUOTE


def test_other_synthesis_fields_use_same_rule():
    for field in ("paper.paper_type", "paper.superconductor_kind",
                  "paper.research_motivation", "paper.knowledge_graph_title",
                  "material_states[0].material_dimensionality"):
        result = evidence.checked_result(row(field), check(), CHUNKS)
        assert result["source_kind"] == "paper_synthesis", field
        assert result["ai_reason"] == LOGIC, field


def test_generic_or_missing_logic_cannot_remain_supported():
    for reason in ("", "原文直接记载，无需额外推断。", "与原文一致。"):
        result = evidence.checked_result(row(), check(reason), CHUNKS)
        assert result["status"] == "uncertain"
        assert "重新核对" in result["ai_reason"]


def test_direct_quote_and_author_keywords_are_not_model_inference():
    direct = evidence.checked_result(row("paper.title", synthesis=False), check("标题逐字见首页"), CHUNKS)
    assert direct["source_kind"] == "paper_quote"
    assert direct["ai_reason"] is None

    author = evidence.checked_result(row("paper.keywords_tags", provenance={"kind": "author_keywords"}),
                                     check("作者在关键词栏列出这些词"), CHUNKS)
    assert author["source_kind"] == "author_keywords"


def test_model_receives_synthesis_mode_and_must_explain_inference(monkeypatch):
    captured = {}

    def complete(system, payload, **_kwargs):
        captured["system"] = system
        captured["payload"] = json.loads(payload)
        return {"results": [{"key": "paper.material_families", **check()}]}

    monkeypatch.setattr("backend.rag.llm.complete_json", complete)
    result = evidence.evaluate_batch([row()], CHUNKS)
    assert result[0]["status"] == "supported"
    assert captured["payload"]["records"][0]["check_mode"] == "synthesis"
    assert "依据" in captured["system"] and "判断" in captured["system"]


def test_recheck_replaces_old_model_reason_for_current_synthesis_value(monkeypatch):
    def complete(_system, _payload, **_kwargs):
        return {"results": [{"key": "paper.material_families", **check()}]}

    monkeypatch.setattr("backend.rag.llm.complete_json", complete)
    prior = {"paper.material_families": {"ai_reason": "旧模型把原文标签直接当作分类结论，没有解释归类依据。"}}
    result = evidence.evaluate_batch([row()], CHUNKS, prior=prior)[0]
    assert result["ai_reason"] == LOGIC
