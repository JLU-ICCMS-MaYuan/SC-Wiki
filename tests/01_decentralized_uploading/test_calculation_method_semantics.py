"""#139 US4：新提取、阶段补空、历史核对及建议采用共享方法语义。"""
from copy import deepcopy
import json

import pytest
from fastapi import HTTPException

from backend.ingest.calculation_methods import electronic_method_issue, validate_extracted_methods
from backend.ingest import scientific_context as context
from backend.ingest import property_evidence as evidence
from backend.ingest import evidence_proposals as proposals
from backend.ingest.scientific_contracts import validate_conditions
from test_issue139_scientific_context import draft


@pytest.mark.parametrize("value", ["DFPT", "density-functional perturbation theory", "DFT / DFPT",
    "有限位移法", "finite-displacement method", "frozen phonon", "Quantum ESPRESSO", "VASP", "PBE", "GGA", "HSE06"])
def test_wrong_categories_are_not_electronic_theories(value):
    assert electronic_method_issue(value)


@pytest.mark.parametrize("value", ["DFT", "density functional theory", "HF", "Hartree–Fock",
    "DFT+U", "GW", "DMFT", "MP2", None, "", "unknown"])
def test_valid_or_unreported_theories_are_not_a_closed_whitelist(value):
    assert electronic_method_issue(value) is None


def sources():
    return context.build_context([{"file_id": "main", "chunk_index": 0, "page_start": 5,
        "content": "For LaSc2H24 at 150 GPa, electronic structure uses density functional theory. "
        "Phonons and EPC use density functional perturbation theory with Quantum ESPRESSO."}])


def setting(key, value):
    return {"stage": "electron_phonon", "key": key, "value": value,
        "reported_value_raw": value, "unit_raw": "", "scope": {"material": "LaSc2H24"},
        "fact_evidences": [{"source_id": "source-0"}], "scope_evidences": [{"source_id": "source-0"}],
        "explanation": "本文明确报告该方法与对应阶段。"}


def test_read_retry_then_assignment_roundtrip_keeps_phonon_method_separate(tmp_path):
    calls = []
    def model(prompt, body, **kwargs):
        calls.append(json.loads(body))
        return {"settings": [setting("electronic_method", "DFPT")]} if len(calls) == 1 else {
            "settings": [setting("electronic_method", "DFT"), setting("phonon_method", "DFPT"),
                         setting("calculation_code", "Quantum ESPRESSO")]}
    ctx = sources()
    ledger = context.read_context(ctx, model, cache_dir=tmp_path)
    assert len(calls) == 2 and "电子结构方法" in calls[1]["previous_validation_error"]
    assert ledger["complete"] and not ledger["gaps"]
    original = draft()
    root = original["material_states"][0]["property_modules"][0]["records"][0]
    target = {"target": "s/m/r", "expected_fingerprint": context.scientific_fingerprint(root), "record": root}
    assignment = {"basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
                  "explanation": "分别保留原文明确报告的电子理论、声子响应方法和软件。"}
    candidates = [context.candidate_from_setting(item, assignment, target) for item in ledger["settings"]]
    applied, gaps = context.apply_associations(original, candidates, ctx)
    assert len(applied) == 3 and not gaps
    # 以现有JSON草稿持久化格式重读，扩展、阶段和来源保持。
    restored = json.loads(json.dumps(original))
    conditions = restored["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]
    assert conditions["electronic_method"] == "DFT"
    assert conditions["calculation_code"] == "Quantum ESPRESSO"
    assert conditions["extensions"][0]["key"] == "electron_phonon.phonon_method"
    assert conditions["extensions"][0]["value_raw"] == "DFPT"
    assert all(a["association"]["fact_evidences"] for a in applied)
    # 缓存仍可复用当前语义的结果，不能重复调用或回退成DFPT电子方法。
    assert context.read_context(ctx, lambda *a, **kw: pytest.fail("不应重读有效缓存"), cache_dir=tmp_path)["settings"] == ledger["settings"]


def test_only_dfpt_does_not_invent_dft():
    ctx = context.build_context([{"file_id": "main", "content": "Phonons use density functional perturbation theory."}])
    ledger = context.read_context(ctx, lambda *a, **kw: {"settings": [setting("phonon_method", "DFPT")]})
    assert ledger["complete"]
    assert [s["key"] for s in ledger["settings"]] == ["phonon_method"]


@pytest.mark.parametrize("extension", [False, True])
def test_bad_association_cannot_overwrite_user_dft_or_enter_stage_extension(extension):
    d = draft(); root = d["material_states"][0]["property_modules"][0]["records"][0]
    root["payload"]["calculation_conditions"]["electronic_method"] = "DFT"
    before = deepcopy(d)
    source = {"source_id": "source-0"}
    c = {"target": "s/m/r", "expected_fingerprint": context.scientific_fingerprint(root),
         "target_path": "/payload/calculation_conditions/electronic_method", "value": "DFPT",
         "stage": "electron_phonon", "basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
         "explanation": "错误模型试图把原文中的声子方法作为电子理论。", "reported_value_raw": "DFPT",
         "fact_evidences": [source], "scope_evidences": [source]}
    if extension:
        c.update(target_path="/payload/calculation_conditions/extensions/-",
                 value={"key": "electronic_structure.electronic_method", "value_kind": "text", "value_raw": "DFPT"})
    applied, gaps = context.apply_associations(d, [c], sources())
    assert not applied and gaps[0]["reason"] == "method_category_mismatch"
    assert d == before


def test_new_extraction_rejects_wrong_method_without_modifying_input():
    d = draft(); r = d["material_states"][0]["property_modules"][0]["records"][0]
    r["payload"]["calculation_conditions"]["electronic_method"] = "DFPT"
    before = deepcopy(d)
    with pytest.raises(ValueError, match="电子结构方法"):
        validate_extracted_methods(d)
    with pytest.raises(ValueError, match="电子结构方法"):
        validate_conditions(d["material_states"][0], r)
    assert d == before
    with pytest.raises(ValueError):
        validate_extracted_methods({"material_states": [{"tc_results": [{"calculation_context": {"electronic_method": "DFPT"}}]}]})


def snapshot(value="DFPT"):
    d = draft();r = d["material_states"][0]["property_modules"][0]["records"][0]
    r["payload"]["calculation_conditions"]["electronic_method"] = value
    rows = evidence.draft_records(d, {})
    snap = evidence.complete_snapshot("upload", "test", rows, sources()["sources"], d)
    leaf = next(r for r in snap["records"] if r.get("record_field") == "payload.calculation_conditions.electronic_method")
    return snap, leaf


def old_result(leaf):
    return {"status": "supported", "reason": "旧错误结论：原文出现DFPT。",
            "evidences": [{"file_id": "main", "quote": sources()["sources"][0]["content"]}],
            "proposal_draft": {"accepted": True, "values": {"": "DFPT"}}, "resolution": "旧人工理由",
            "decision": {"human_confirmed": True, "accepted": True, "actor_user_id": 1, "reason": "旧人工理由",
                         "final_content_hash": leaf["content_hash"], "source_hash": leaf["source_hash"]}}


def test_old_supported_and_accepted_cache_no_longer_grants_passage():
    snap, leaf = snapshot()
    raw = old_result(leaf); original = deepcopy(raw)
    result = next(r for r in evidence.public_snapshot(snap, {leaf["key"]: raw})["records"] if r["key"] == leaf["key"])
    assert result["status"] == "unsupported" and not result["human_confirmed"]
    assert result["proposal_draft"] is None and result["decision"] is None and not result["resolution"]
    assert result["current_value"] == "DFPT" and result["evidences"]
    assert "旧核对意见" in result["reason"] and raw == original
    with pytest.raises(HTTPException):
        proposals.validate_values(leaf, {"": "DFPT"})
    assert proposals.validate_values(leaf, {"": "DFT"}) == {"": "DFT"}
    # 已接受的正确修正候选仍保留，不能因当前旧值错误而丢弃修正。
    raw["proposal_draft"] = {"accepted": True, "values": {"": "DFT"}}
    assert evidence.checked_result(leaf, raw, snap["chunks"])["proposal_draft"]["accepted"]


def test_correct_dft_value_is_preserved_and_other_scientific_fields_are_not_invalidated():
    snap, leaf = snapshot("DFT")
    result = evidence.checked_result(leaf, {"status": "supported", "evidences": old_result(leaf)["evidences"]}, snap["chunks"])
    # DFT不是类别错误；自动通过还需当前软件/物相和完整来源规则，本例没有提供。
    assert result["status"] == "uncertain" and result["current_value"] == "DFT"
    bad_snap, _ = snapshot()
    unrelated = next(r for r in bad_snap["records"] if r.get("record_field") == "payload.parameters.lambda_ep")
    result = evidence.checked_result(unrelated, {"status": "supported", "evidences": old_result(leaf)["evidences"]}, bad_snap["chunks"])
    assert result["status"] == "supported"


def test_domain_extraction_entry_rejects_dfpt_and_preserves_hf():
    from test_issue114_domain_extraction import extraction
    from backend.ingest.domain_extraction import normalize_extraction
    raw = extraction()
    r = raw["material_states"][0]["property_modules"][0]["records"][0]
    r.update(record_type="predicted_tc", method_code="unknown",
             payload={"calculation_conditions": {"electronic_method": "DFPT"}})
    with pytest.raises(ValueError, match="电子结构方法"):
        normalize_extraction(raw, allowed_blocks={("main", 1, "b1")})
    r["payload"]["calculation_conditions"]["electronic_method"] = "HF"
    r['evidences'][0]['quote'] += ' The electronic structure uses Hartree-Fock theory.'
    restored = normalize_extraction(raw, allowed_blocks={("main", 1, "b1")})
    assert restored["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]["electronic_method"] == "HF"


def test_legacy_extraction_entry_retries_category_errors_and_expires_old_cache(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.chunker import Chunk
    calls = []
    def model(*args, **kwargs):
        calls.append(args)
        return {"material_states": [{"material": "LaSc2H24",
            "calculation_context": {"electronic_method": "DFPT" if len(calls) == 1 else "DFT"}}]}
    monkeypatch.setattr(jobs, "complete_json", model)
    monkeypatch.setattr(jobs, "_ensure_not_cancelled", lambda _: None)
    chunk = Chunk(paper_id=1, heading=None, token_count=20,
                  content="Electronic structure uses DFT; phonons use DFPT.", chunk_index=0, section_name="Methods")
    path = tmp_path / "chunk.json"
    monkeypatch.setattr(jobs, "_chunk_result_path", lambda *args: path)
    result = jobs._read_chunk("test", chunk)
    assert len(calls) == 2
    assert result["material_states"][0]["calculation_context"]["electronic_method"] == "DFT"
    old = deepcopy(result); old["_schema_version"] = 12
    old["material_states"][0]["calculation_context"]["electronic_method"] = "DFPT"
    path.write_text(json.dumps(old))
    assert jobs._read_chunk("test", chunk)["material_states"][0]["calculation_context"]["electronic_method"] == "DFT"
    assert len(calls) == 3


def test_hf_from_another_stage_remains_separate_from_existing_dft():
    d = draft(); root = d["material_states"][0]["property_modules"][0]["records"][0]
    root["payload"]["calculation_conditions"]["electronic_method"] = "DFT"
    ctx = context.build_context([{"file_id": "main", "content": "For LaSc2H24, relaxation uses Hartree-Fock, while EPC uses DFT."}])
    atomic = setting("electronic_method", "HF") | {"stage": "structural_relaxation"}
    c = context.candidate_from_setting(atomic, {"basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
        "explanation": "HF只属于本例的结构优化阶段，不替换EPC的DFT。"},
        {"target": "s/m/r", "expected_fingerprint": context.scientific_fingerprint(root), "record": root})
    applied, gaps = context.apply_associations(d, [c], ctx)
    assert len(applied) == 1 and not gaps
    assert root["payload"]["calculation_conditions"]["electronic_method"] == "DFT"
    assert root["payload"]["calculation_conditions"]["extensions"][0]["value_raw"] == "HF"
