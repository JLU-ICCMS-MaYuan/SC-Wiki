"""#120：减少上传校对表单的无效标红，同时不放宽原文定位。"""
import re

from backend.ingest import property_evidence as ev
from backend.ingest import scientific_evidence as science
from backend.ingest.chunker import Chunk
from backend.ingest.upload_jobs import (
    EXTRACTION_WINDOW_CHARS,
    _chunks_with_preamble,
    _formula_from_material,
    _merge_extraction_windows,
    _normalize_material_states,
)


def test_grouped_formula_keeps_material_identity():
    state = _normalize_material_states([{"material": "(H2S)2H2"}])[0]
    assert state["material"] == "(H2S)2H2"
    assert state["element_count"] == 2


def test_formula_extraction_never_takes_a_fragment():
    assert _formula_from_material("H3S (Im-3m)") == "H3S"
    # 替代式合金不能截成 H9 或 La。
    assert _formula_from_material("(La,Ce)H9") == ""
    assert _formula_from_material("YH6 and YH9") == ""


def test_unparseable_material_is_kept_as_name():
    state = _normalize_material_states([{"material": "(La,Ce)H9"}])[0]
    assert state["material"] == ""
    assert state["material_name"] == "(La,Ce)H9"
    assert state["element_count"] == 3
    named = _normalize_material_states([{"material": "(La,Ce)H9", "material_name": "La-Ce superhydride"}])[0]
    assert named["material_name"] == "La-Ce superhydride"


def rows_by_name(state):
    return {row["field"].rsplit(".", 1)[-1]: row for row in science.state_records(state, 0)}


def test_space_group_number_and_crystal_system_are_derived_from_symbol():
    rows = rows_by_name({"state_key": "s", "material": "H3S", "reported_space_group_symbol": "Im-3m",
                         "reported_space_group_number": 229, "crystal_system": "cubic"})
    for name in ("reported_space_group_number", "crystal_system"):
        assert rows[name]["kind"] == "derived"
        assert rows[name]["dependency"] == rows["reported_space_group_symbol"]["item_key"]
    records = [
        {**rows["reported_space_group_symbol"], "status": "supported", "evidences": [{"quote": "Im-3m"}], "content_hash": "c", "source_hash": "s"},
        {**rows["reported_space_group_number"], "status": "unchecked", "content_hash": "c2", "source_hash": "s"},
    ]
    derived = science.apply_derived(records)[1]
    assert derived["status"] == "supported"


def test_inconsistent_space_group_number_is_still_checked_against_paper():
    rows = rows_by_name({"state_key": "s", "material": "H3S", "reported_space_group_symbol": "Im-3m",
                         "reported_space_group_number": 221, "crystal_system": "cubic"})
    assert rows["reported_space_group_number"]["kind"] == "field"
    assert rows["crystal_system"]["kind"] == "derived"


def result(status, evidences):
    return {"status": status, "evidences": evidences, "reason": status, "suggestion": "", "fields": []}


def test_batch_without_located_evidence_does_not_downgrade_supported():
    record = {"key": "k"}
    quote = {"file_id": "main", "chunk_index": 1, "quote": "Tc of 203 K"}
    results = ev.aggregate_candidates([record], {"k": [result("supported", [quote]), result("missing", [])]}, {"k": []}, "m")
    assert results["k"]["status"] == "supported"
    conflict = ev.aggregate_candidates([record], {"k": [result("supported", [quote]), result("unsupported", [quote])]}, {"k": []}, "m")
    assert conflict["k"]["status"] == "uncertain"


def test_reference_list_is_not_used_as_evidence_source():
    chunks = [dict(file_id="main", chunk_index=0, content="Tc reaches 250 K.", section="Results"),
              dict(file_id="main", chunk_index=1, content="1. Drozdov A. P. et al.", section="References")]
    assert [c["chunk_index"] for batch in ev.source_batches(chunks) for c in batch] == [0]


def test_extraction_windows_merge_small_chunks_without_exceeding_limit():
    chunks = [Chunk(0, i, "Results", None, f"<!-- page: {i + 1} -->\n" + "x" * 3000, 750) for i in range(10)]
    windows = _merge_extraction_windows(chunks)
    assert len(windows) < len(chunks)
    assert all(len(w.content) <= EXTRACTION_WINDOW_CHARS for w in windows)
    assert "".join(w.content for w in windows).count("page:") == 10


def test_window_page_is_where_window_starts():
    # 与实际解析 Markdown 一致：页标记位于段落之间；第二个窗口从第 2 页中部开始。
    body = "\n\n".join(f"<!-- page: {page} -->\n\n" + "\n\n".join(f"p{page} " * 700 for _ in range(4)) for page in (1, 2, 3))
    chunks = [c for c in _chunks_with_preamble("## Results\n\n" + body) if "p1 " in c.content or "p2 " in c.content or "p3 " in c.content]
    assert len(chunks) > 1
    assert chunks[0].source_page == 1
    for chunk in chunks[1:]:
        first_text_page = int(re.search(r"\bp(\d) ", chunk.content).group(1))
        assert chunk.source_page == first_text_page


CHECK_CHUNKS = [dict(file_id="main", chunk_index=0, content="The resulting l of R3m is 2.07 at 130 GPa.", section="Results")]


def field_rows(values):
    return {r["field"]: r for r in science.field_records("paper", "paper", values, science.PAPER_FIELDS)}


def test_synthesis_fields_are_marked_and_keep_model_judgment():
    rows = field_rows({"research_motivation": "Hydrogen-rich compounds are promising.", "keywords_tags": ["hydride"]})
    assert rows["paper.research_motivation"].get("check_mode") == "synthesis"
    assert rows["paper.keywords_tags"].get("check_mode") == "synthesis"
    assert "check_mode" not in rows["paper.doi"]
    # 概括文字不必逐字出现，但没有任何可定位依据时不能标为原文支持。
    outcome = ev.checked_result(rows["paper.research_motivation"],
                                result("supported", [{"file_id": "main", "chunk_index": 9, "quote": "模型凭记忆复述的走样引句"}]),
                                CHECK_CHUNKS)
    assert outcome["status"] == "missing"
    assert "未在所选来源" not in outcome["reason"]


def test_verbatim_record_falls_back_to_validated_draft_evidence():
    # 模型复述引句走样时，回退用提取阶段已逐字验证的记录自带证据定位。
    record = {"key": "k", "field": "material_states[2].property_modules[0].records[0]",
              "evidences": [{"file_id": "main", "chunk_index": 0, "quote": "The resulting l of R3m is 2.07 at 130 GPa."}]}
    outcome = ev.checked_result(record, result("supported", [{"file_id": "main", "chunk_index": 0, "quote": "模型改写后原文不存在的句子"}]), CHECK_CHUNKS)
    assert outcome["status"] == "supported"
    assert outcome["evidences"][0]["quote"] == "The resulting l of R3m is 2.07 at 130 GPa."


def test_verbatim_record_without_located_evidence_stays_missing():
    record = {"key": "k", "field": "material_states[2].property_modules[0].records[0]", "evidences": []}
    outcome = ev.checked_result(record, result("supported", [{"file_id": "main", "chunk_index": 0, "quote": "原文没有这句话"}]), CHECK_CHUNKS)
    assert outcome["status"] == "missing"


def test_aggregation_ignores_unmentioned_batch_for_synthesis():
    record = {"key": "k", "field": "paper.research_motivation", "check_mode": "synthesis"}
    results = ev.aggregate_candidates([record], {"k": [result("supported", []), result("missing", [])]}, {"k": []}, "m")
    assert results["k"]["status"] == "supported"
    # 事实字段不受影响：未定位批次的 supported 仍被已定位批次覆盖，冲突仍判 uncertain。
    fact = ev.aggregate_candidates([{"key": "k", "field": "f"}], {"k": [result("supported", [{"quote": "q"}]), result("missing", [])]}, {"k": []}, "m")
    assert fact["k"]["status"] == "supported"
