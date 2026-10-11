"""#120：论文级材料家族优先使用当前目录，并保存全文判断依据。"""

import json
from types import SimpleNamespace

from backend.ingest import material_family_classification as classifier
from backend.ingest import upload_jobs
from backend.ingest.material_family_classification import (
    classify,
    current_candidate_context,
    matching_assessment,
)
from backend.ingest.language_contract import validate_draft_generated_english
from backend.ingest.property_evidence import complete_snapshot, evaluate_batch, _fill_empty_fields
from backend.ingest.upload_jobs import _normalize_draft


CATALOG = [
    {"id": 1, "name": "氢基超导体", "name_en": "Hydrogen-based superconductor",
     "aliases": ["hydride", "hydrogen-rich superconductor"]},
    {"id": 2, "name": "铜基超导体", "name_en": "Copper-based superconductor",
     "aliases": ["cuprate"]},
]
QUOTE = "Hydrogen-rich materials of (H2S)2H2 or H3S show superconductivity."
CHUNKS = [{"file_id": "main", "chunk_index": 0, "content": QUOTE,
           "page_start": 2, "page_end": 2, "section": "Results"}]
DRAFT = {"paper": {"title": "Superconductivity of H3S", "abstract": QUOTE,
                   "research_materials": ["(H2S)2H2", "H3S"]},
         "material_states": [{"material": "(H2S)2H2"}, {"material": "H3S"}]}


def response(families):
    return {"families": families, "reason": "根据本文研究对象判断。"}


def family(catalog_id=None, new_name=None, quote=QUOTE):
    return {"catalog_id": catalog_id, "new_name": new_name,
            "reason": "本文研究的材料属于该家族。",
            "evidences": [{"file_id": "main", "chunk_index": 0, "quote": quote}]}


def test_h3s_selects_existing_database_family_with_located_evidence():
    calls = []

    def complete(prompt, payload):
        calls.append((prompt, payload))
        return response([family(catalog_id=1)])

    result = classify(CATALOG, DRAFT, CHUNKS, complete=complete, model="test")
    assert result["status"] == "completed"
    assert result["families"] == [{"id": 1, "name": "氢基超导体", "status": "confirmed",
                                   "evidence": {"file_id": "main", "chunk_index": 0,
                                                "section": "Results", "page": 2, "quote": QUOTE}}]
    assert result["evidences"][0]["quote"] == QUOTE
    assert result["reason"] == "本文研究的材料属于该家族。"
    assert len(calls) == 1


def test_novel_h2_label_is_checked_against_catalog_before_pending():
    calls = []

    def complete(prompt, payload):
        calls.append(prompt)
        if len(calls) == 1:
            return response([family(new_name="H2-containing compounds")])
        return {"catalog_id": 1, "reason": "现有氢基分类已经涵盖该材料。"}

    result = classify(CATALOG, DRAFT, CHUNKS, complete=complete)
    assert [item["id"] for item in result["families"]] == [1]
    assert len(calls) == 2


def test_new_family_only_stays_pending_after_catalog_recheck():
    def complete(prompt, payload):
        if "二次" in prompt:
            return {"catalog_id": None, "reason": "现有家族均不涵盖该体系。"}
        return response([family(new_name="Novel intermetallic superconductors")])

    result = classify(CATALOG, DRAFT, CHUNKS, complete=complete)
    assert result["families"][0]["id"] is None
    assert result["families"][0]["status"] == "pending"


def test_multiple_families_and_aliases_are_deduplicated():
    result = classify(CATALOG, DRAFT, CHUNKS, complete=lambda *_: response([
        family(catalog_id=1), family(new_name="hydride"), family(catalog_id=2),
    ]))
    assert [item["id"] for item in result["families"]] == [1, 2]


def test_invalid_catalog_id_never_becomes_new_family():
    result = classify(CATALOG, DRAFT, CHUNKS,
                      complete=lambda *_: response([family(catalog_id=999, new_name="Invented")]))
    assert result["status"] == "uncertain"
    assert result["families"] == []


def test_missing_or_unlocatable_evidence_leaves_family_blank():
    result = classify(CATALOG, DRAFT, CHUNKS,
                      complete=lambda *_: response([family(catalog_id=1, quote="A quote not in the paper")]))
    assert result["status"] == "uncertain"
    assert result["families"] == []


def test_catalog_or_model_failure_does_not_guess_family():
    empty = classify([], DRAFT, CHUNKS, complete=lambda *_: response([family(catalog_id=1)]))
    assert empty["status"] == "failed"
    assert empty["families"] == []

    def broken(*_):
        raise RuntimeError("model unavailable")

    failed = classify(CATALOG, DRAFT, CHUNKS, complete=broken)
    assert failed["status"] == "failed"
    assert failed["families"] == []


def test_long_paper_uses_all_source_batches_before_final_classification(monkeypatch):
    second = {"file_id": "supp", "chunk_index": 1,
              "content": "The current work studies cuprate superconductors.",
              "page_start": 5, "page_end": 5, "section": "Results"}
    monkeypatch.setattr(classifier, "source_batches", lambda chunks: [[chunks[0]], [chunks[1]]])
    calls = []

    def complete(prompt, payload):
        calls.append((prompt, json.loads(payload)))
        if len(calls) < 3:
            return {"materials": [{"material": "H3S" if len(calls) == 1 else "cuprate"}]}
        return response([{"catalog_id": 2, "new_name": None, "reason": "本文研究铜基材料。",
                          "evidences": [{"file_id": "supp", "chunk_index": 1,
                                         "quote": second["content"]}]}])

    result = classify(CATALOG, DRAFT, [*CHUNKS, second], complete=complete)
    assert result["status"] == "completed"
    assert [item["id"] for item in result["families"]] == [2]
    assert len(calls) == 3
    assert calls[-1][1]["coverage"] == {"read": 2, "total": 2}
    assert len(calls[-1][1]["window_summaries"]) == 2


def test_referenced_work_is_excluded_from_classification_context():
    candidates = [
        {"material_states": [{"scope": "referenced_work", "material": "YBCO",
                              "material_family": {"name": "cuprate"}}]},
        {"material_states": [{"scope": "current_paper", "material": "H3S",
                              "material_family": {"name": "hydride"}}]},
    ]
    context = current_candidate_context(candidates)
    assert [item["material"] for item in context] == ["H3S"]


def test_user_change_invalidates_old_classification_assessment():
    result = classify(CATALOG, DRAFT, CHUNKS, complete=lambda *_: response([family(catalog_id=1)]))
    assert matching_assessment(result, result["families"])
    assert not matching_assessment(result, [{"id": 2, "name": "铜基超导体", "status": "confirmed"}])


def test_classification_assessment_is_bound_to_current_evidence_record():
    result = classify(CATALOG, DRAFT, CHUNKS, complete=lambda *_: response([family(catalog_id=1)]))
    record = {"key": "family", "item_key": "family", "field": "paper.material_families",
              "claim": {"value": ["氢基超导体"]}, "current_value": ["氢基超导体"],
              "label": "材料家族", "kind": "field", "evidences": []}
    draft = {"paper": {"material_families": result["families"]},
             "material_family_assessment": result}
    bound = complete_snapshot("upload", "task", [record.copy()], CHUNKS, draft)["records"][0]
    assert bound["provenance"]["kind"] == "paper_synthesis"
    assert bound["evidences"][0]["quote"] == QUOTE
    assert bound["source_hash"]

    changed = {**draft, "paper": {"material_families": [{"id": 2, "name": "铜基超导体"}]}}
    stale = complete_snapshot("upload", "task", [record.copy()], CHUNKS, changed)["records"][0]
    assert "provenance" not in stale
    assert stale["evidences"] == []


def test_catalog_name_can_be_chinese_and_snapshot_survives_normalization():
    result = classify(CATALOG, DRAFT, CHUNKS, complete=lambda *_: response([family(catalog_id=1)]))
    raw = {"paper": {"material_families": result["families"]},
           "material_states": [], "material_family_assessment": result,
           "material_family_error": "insufficient_evidence"}
    normalized = _normalize_draft(raw)
    validate_draft_generated_english(normalized)
    assert matching_assessment(normalized["material_family_assessment"], normalized["paper"]["material_families"])
    assert normalized["material_family_error"] == "insufficient_evidence"


def test_generic_suggestion_cannot_bypass_catalog_first_classification():
    draft = {"paper": {"material_families": []}}
    record = {"field": "paper.material_families", "editable_fields": [{"path": "", "value": []}]}
    proposal = {"basis_kind": "paper_inference", "values": {"": ["H2-containing compounds"]}}
    assert not _fill_empty_fields(draft, record, proposal)
    assert draft["paper"]["material_families"] == []


def test_evidence_model_cannot_offer_uncatalogued_family_proposal(monkeypatch):
    from backend.rag import llm

    monkeypatch.setattr(llm, "complete_json", lambda *_args, **_kwargs: {"results": [{
        "key": "family", "status": "uncertain", "reason": "需人工确认", "evidences": [],
        "proposal": {"values": {"": ["H2-containing compounds"]},
                     "basis_kind": "paper_inference", "explanation": "从本文材料推断", "evidences": []},
    }]})
    record = {"key": "family", "item_key": "family", "field": "paper.material_families",
              "claim": {"value": []}, "current_value": [], "label": "材料家族", "kind": "field",
              "evidences": [], "required": False, "content_hash": "content", "source_hash": "source"}
    result = evaluate_batch([record], CHUNKS, purpose="generate")
    assert result[0]["proposal"] is None


def test_shared_post_summary_step_keeps_other_fields_on_catalog_failure(monkeypatch):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(upload_jobs, "SessionLocal", lambda: Session())
    monkeypatch.setattr(classifier, "load_catalog", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    draft = {"paper": {"title": "H3S", "material_families": [{"id": None, "name": "H2-containing compounds"}]},
             "material_states": [{"material": "H3S"}]}
    upload_jobs._classify_material_family_draft("task", {}, draft, [])
    assert draft["paper"]["title"] == "H3S"
    assert draft["material_states"] == [{"material": "H3S"}]
    assert draft["paper"]["material_families"] == []
    assert draft["material_family_error"] == "catalog_unavailable"


def test_shared_post_summary_step_handles_both_draft_shapes(monkeypatch):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(upload_jobs, "SessionLocal", lambda: Session())
    monkeypatch.setattr(classifier, "load_catalog", lambda _: CATALOG)
    monkeypatch.setattr(classifier, "task_sources", lambda *_: CHUNKS)
    monkeypatch.setattr(classifier, "classify", lambda catalog, draft, chunks, **kwargs:
                        {"status": "completed", "families": [{"id": 1, "name": "氢基超导体", "status": "confirmed"}],
                         "evidences": [{"quote": QUOTE}], "reason": "归入现有氢基分类"})
    from backend.rag import llm_context
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: SimpleNamespace(model="test"))
    for states in ([{"material": "H3S"}], []):
        draft = {"paper": {"title": "H3S", "material_families": []}, "material_states": states}
        upload_jobs._classify_material_family_draft("task", {}, draft, [])
        assert draft["paper"]["material_families"][0]["id"] == 1
        assert draft["material_family_error"] is None
        assert draft["material_states"] == states
