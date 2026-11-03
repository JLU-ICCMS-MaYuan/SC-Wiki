"""#207/#209：交接不能用候选背景资料覆盖已经核对通过的字段引用。"""
from copy import deepcopy
import pytest


@pytest.mark.parametrize("target", ["upload", "revision", "paper"])
def test_transfer_preserves_reviewed_selection_instead_of_candidate_bundle(target, monkeypatch):
    from backend.ingest import scientific_evidence as science, property_evidence as ev
    from backend.ingest.model_review import bind_result
    from backend.ingest.reviewed_sources import checked_references
    monkeypatch.setattr("backend.rag.llm.complete_json", lambda *a, **kw: pytest.fail("交接不新增模型调用"))
    chunks = [{"file_id": "218", "chunk_id": 3900+i, "chunk_index": i, "content": text}
              for i, text in enumerate(["Original coordinate table.", "Other source context."])]
    snapshot = ev.complete_snapshot(target, "isolated-h3s", [{"key": "structure", "item_key": "structure",
        "field": "material_states[0].structure.structure_text", "kind": "field",
        "claim": {"value": "verified CIF"}, "current_value": "verified CIF", "required": True}], chunks, {})
    record = snapshot["records"][0]
    record["evidences"] = [{"file_id": "218", "source_sha256": "a"*64, "quote": "Document IR background"}]
    result = bind_result(record, {"status": "supported", "reason": "原坐标表支持当前结构",
        "evidences": [{"file_id": "old-file", "chunk_index": 0, "quote": "Original coordinate table."}],
        "human_confirmed": False}, chunks)
    before = deepcopy(record)
    moved = science.transfer_result(record, result, chunks, {"old-file": "218"}, source_transfer_verified=True)
    assert record == before
    assert moved["evidences"][0]["chunk_id"] == 3900
    assert moved["evidences"][0]["quote"] == result["evidences"][0]["quote"]
    assert checked_references([moved], chunks)[0]["evidences"] == moved["evidences"]
    assert not moved.get("human_confirmed")


def test_missing_reviewed_reference_cannot_fall_back_to_candidate_context():
    from backend.ingest import scientific_evidence as science
    from backend.ingest.reviewed_sources import SourceReferenceError
    record={"field":"paper.summary", "content_hash":"value", "source_hash":"source",
            "evidences":[{"file_id":"218","chunk_index":0,"quote":"Candidate background"}]}
    result={**record,"status":"supported","evidences":[{"file_id":"missing","chunk_index":0,"quote":"Reviewed source"}]}
    chunks=[{"file_id":"218","chunk_id":1,"chunk_index":0,"content":"Readable background"}]
    with pytest.raises(SourceReferenceError):
        science.transfer_result(record,result,chunks,source_transfer_verified=True)


def test_submit_uses_exact_current_subject_instead_of_rounded_cache_copy():
    from backend.ingest import property_evidence as ev
    from backend.ingest.model_review import bind_result
    current = 119.99999999999999
    chunks = [{'file_id': '218', 'chunk_index': 0, 'content': 'Reviewed R3m structure.'}]
    snap = ev.complete_snapshot('paper', 'isolated-r3m', [{'key': 'gamma', 'item_key': 'gamma',
        'field': 'material_states[0].structure.cell_parameters.gamma', 'kind': 'field',
        'current_value': current, 'claim': {'value': current}, 'required': True}], chunks, {})
    row = snap['records'][0]
    result = bind_result(row, {'status': 'supported', 'reason': '从同一CIF派生的晶胞角',
        'evidences': [{'file_id': '218', 'chunk_index': 0, 'quote': 'Reviewed R3m structure.'}]}, chunks)
    # 实际H3S的同版本结果副本为120.0，当前CIF派生值仍保持精确原值。
    result['current_value'] = 120.0
    accepted = ev.resolve_results(snap, {'gamma': result}, 1, None, snap['version'])
    assert accepted[0]['current_value'] == current
    assert accepted[0]['current_value'] != result['current_value']
