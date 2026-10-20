"""#139 US5：完整生成→补空→核对链中的有据PBE推断与反例。"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import json

import pytest
from backend.ingest import scientific_context as sc, property_evidence as ev, scientific_evidence as science
from backend.ingest.functional_inference import functional_inference_candidates, RULE
from test_issue139_scientific_context import draft


def context():
    return sc.build_context([
        {"file_id": "main", "chunk_index": 0, "page_start": 5,
         "content": "LaSc2H24 structures at 150 GPa were optimized using VASP with the PBE functional."},
        {"file_id": "main", "chunk_index": 1, "page_start": 5,
         "content": "For the same optimized LaSc2H24 phase, phonons and EPC were calculated with Quantum ESPRESSO."},
    ])


def settings():
    raw = [
        ("calculation_code", "VASP", "structural_relaxation", "source-0"),
        ("exchange_correlation_functional", "PBE", "structural_relaxation", "source-0"),
        ("calculation_code", "Quantum ESPRESSO", "electron_phonon", "source-1"),
    ]
    ctx = context()
    return {f"setting-{i}": {
        "setting_id": f"setting-{i}", "key": key, "value": value, "stage": stage,
        "reported_value_raw": value, "scope": {"material": "LaSc2H24"}, "exceptions": [],
        "fact_evidences": [sc.located({"source_id": ref}, ctx["sources"])],
        "scope_evidences": [sc.located({"source_id": ref}, ctx["sources"])],
        "explanation": "本文报告的阶段设置。"
    } for i, (key, value, stage, ref) in enumerate(raw)}


def request():
    return {"target": "s/m/r", "vasp_software_setting_id": "setting-0",
            "vasp_functional_setting_id": "setting-1", "qe_software_setting_id": "setting-2",
            "scope": {"material": "LaSc2H24"}, "scope_evidences": [{"source_id": "source-1"}],
            "explanation": "QE用于同一VASP优化物相的声子/EPC，未另报泛函，故作相同PBE推断。"}


def targets(d):
    return {key: {"target": key, "state": state, "record": record,
                  "expected_fingerprint": sc.scientific_fingerprint(record)}
            for key, (state, module, record) in sc.targets(d).items()}


def test_inference_is_a_separate_fill_with_two_sources_and_survives_reload():
    d = draft()
    original = deepcopy(d)
    # 即使模型自报直接支持，程序也只构造独立的paper_inference。
    candidates, gaps = functional_inference_candidates([request() | {"basis_kind": "paper_quote"}],
                                                       settings(), targets(d), context())
    assert not gaps and candidates[0]["basis_kind"] == "paper_inference"
    applied, gaps = sc.apply_associations(d, candidates, context())
    assert len(applied) == 1 and not gaps
    stored = json.loads(json.dumps(d))
    root = stored["material_states"][0]["property_modules"][0]["records"][0]
    assert root["payload"]["calculation_conditions"] == {"exchange_correlation_functional": "PBE"}
    assert root["payload"]["parameters"] == original["material_states"][0]["property_modules"][0]["records"][0]["payload"]["parameters"]
    association = root["payload"]["source_associations"][0]
    assert association["inference_rule"] == RULE
    assert len(association["fact_evidences"]) == 2
    assert "未直接报告" in association["explanation"]
    snap = ev.complete_snapshot("upload", "test", ev.draft_records(stored, {}), context()["sources"], stored)
    leaf = next(r for r in snap["records"] if r.get("record_field") == "payload.calculation_conditions.exchange_correlation_functional")
    result = ev.checked_result(leaf, {"status": "supported", "reason": "模型认可同一流程的推断",
        "evidences": association["fact_evidences"]}, snap["chunks"])
    assert result["status"] == "uncertain" and result["adopted_basis"] == "paper_inference"
    root["payload"]["calculation_conditions"]["exchange_correlation_functional"] = "LDA"
    changed = ev.complete_snapshot("upload", "test", ev.draft_records(stored, {}), context()["sources"], stored)
    assert next(r for r in changed["records"] if r["key"] == leaf["key"])["source_associations"][0]["stale"]
    association["basis_kind"] = "paper_quote"
    assert sc.association_issues(root)  # 保存时也不能把有标记的推断改装为直接证据。


@pytest.mark.parametrize("case", [
    "missing_donor", "pbesol", "wrong_donor_software", "wrong_receiver_software",
    "wrong_stage", "different_material", "different_pressure", "exception",
    "multiple_functionals", "explicit_qe_lda", "explicit_qe_pbe",
    "user_lda", "user_pbe", "source_missing", "scope_missing", "incomplete",
])
def test_unsupported_or_existing_conditions_are_not_filled(case):
    d, atoms, req, ctx = draft(), settings(), request(), context()
    if case == "missing_donor":
        del atoms["setting-1"]
    elif case == "pbesol":
        atoms["setting-1"]["value"] = "PBEsol"
    elif case == "wrong_donor_software":
        atoms["setting-0"]["value"] = "ABINIT"
    elif case == "wrong_receiver_software":
        atoms["setting-2"]["value"] = "VASP"
    elif case == "wrong_stage":
        atoms["setting-1"]["stage"] = "aimd"
    elif case == "different_material":
        req["scope"]["material"] = "H3S"
    elif case == "different_pressure":
        atoms["setting-1"]["scope"]["pressure_value_gpa"] = 300
    elif case == "exception":
        atoms["setting-1"]["exceptions"] = ["QE does not use PBE"]
    elif case == "multiple_functionals":
        atoms["extra"] = atoms["setting-1"] | {"value": "LDA"}
    elif case.startswith("explicit_qe"):
        atoms["extra"] = atoms["setting-1"] | {"stage": "electron_phonon", "value": "LDA" if case.endswith("lda") else "PBE"}
    elif case.startswith("user_"):
        d["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]["exchange_correlation_functional"] = case[5:].upper()
    elif case == "source_missing":
        atoms["setting-1"]["fact_evidences"] = [{"file_id": "main", "quote": "invented PBE evidence"}]
    elif case == "scope_missing":
        req["scope_evidences"] = []
    else:
        ctx["complete"] = False
    before = deepcopy(d)
    candidates, gaps = functional_inference_candidates([req], atoms, targets(d), ctx)
    assert not candidates and gaps
    assert d == before


def test_another_materials_functional_is_not_a_conflict_for_this_target():
    atoms = settings()
    atoms["other"] = atoms["setting-1"] | {"value": "LDA", "scope": {"material": "H3S"}}
    candidates, gaps = functional_inference_candidates([request()], atoms, targets(draft()), context())
    assert candidates and not gaps


def test_existing_vasp_extension_does_not_count_as_existing_qe_functional():
    d = draft()
    conditions = d["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]
    donor = {"key": "structural_relaxation.exchange_correlation_functional",
             "value_kind": "text", "value_raw": "PBE"}
    conditions["extensions"] = [deepcopy(donor)]
    candidates, gaps = functional_inference_candidates([request()], settings(), targets(d), context())
    assert len(candidates) == 1 and not gaps
    applied, gaps = sc.apply_associations(d, candidates, context())
    assert len(applied) == 1 and not gaps
    saved = d["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]
    assert saved["exchange_correlation_functional"] == "PBE"
    assert saved["extensions"] == [donor]


@pytest.mark.parametrize("explicit", [False, True])
def test_actual_generation_preserves_stages_and_prioritizes_explicit_qe(explicit):
    d = draft(); ctx = context()
    if explicit:
        ctx = sc.build_context([*ctx["sources"], {"file_id": "main", "content": "QE uses LDA for LaSc2H24."}])
    atoms = settings()
    if explicit:
        atoms["setting-3"] = atoms["setting-1"] | {"setting_id": "setting-3", "stage": "electron_phonon", "value": "LDA",
            "reported_value_raw": "LDA", "fact_evidences": [sc.located({"source_id": "source-2"}, ctx["sources"])],
            "scope_evidences": [sc.located({"source_id": "source-2"}, ctx["sources"])]}
    def model(prompt, body, **kwargs):
        data = json.loads(body)
        if "targets" not in data:
            return {"settings": list(atoms.values())}
        return {"assignments": [{"setting_id": a["setting_id"], "targets": ["s/m/r"], "excluded_targets": [],
                                "basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
                                "scope_evidences": a["scope_evidences"], "explanation": "本文明确报告该阶段。"}
                               for a in data["settings"]],
                "functional_inferences": [request()]}
    ledger = sc.generate_context_associations(d, ctx, model)
    applied, gaps = sc.apply_associations(d, ledger["associations"], ctx)
    assert not gaps
    root = d["material_states"][0]["property_modules"][0]["records"][0]
    assert root["payload"]["calculation_conditions"]["exchange_correlation_functional"] == ("LDA" if explicit else "PBE")
    assert any(x["key"] == "structural_relaxation.exchange_correlation_functional" and x["value_raw"] == "PBE"
               for x in root["payload"]["calculation_conditions"]["extensions"])
    assert sum(a["association"].get("inference_rule") == RULE for a in applied) == (0 if explicit else 1)


def test_source_change_invalidates_inference_binding():
    d = draft(); ctx = context()
    candidates, _ = functional_inference_candidates([request()], settings(), targets(d), ctx)
    sc.apply_associations(d, candidates, ctx)
    snap = ev.complete_snapshot("upload", "test", ev.draft_records(d, {}), ctx["sources"], d)
    leaf = next(r for r in snap["records"] if r.get("record_field") == "payload.calculation_conditions.exchange_correlation_functional")
    old_hash = leaf["source_hash"]
    changed = ev.complete_snapshot("upload", "test", ev.draft_records(d, {}),
                                   [{"file_id": "main", "content": "A different source."}], d)
    current = next(r for r in changed["records"] if r["key"] == leaf["key"])
    assert current["source_hash"] != old_hash
    # 当前关联携带原文；来源版本不一致时不能复用旧核对结果。


@pytest.mark.parametrize("decline", [False, True])
def test_silent_omission_is_retried_and_explicit_decline_is_respected(decline):
    calls = []
    def model(prompt, body, **kwargs):
        data = json.loads(body)
        if "targets" not in data:
            return {"settings": list(settings().values())}
        calls.append(data)
        result = {"assignments": [{"setting_id": a["setting_id"], "targets": ["s/m/r"],
                  "basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
                  "scope_evidences": a["scope_evidences"], "explanation": "各自的原阶段设置。"} for a in data["settings"]]}
        if len(calls) > 1:
            if decline:
                result["functional_inference_exclusions"] = [{"target": "s/m/r", "reason": "本例工作流联系仍存在歧义。"}]
            else:
                result["functional_inferences"] = [request()]
        return result
    ledger = sc.generate_context_associations(draft(), context(), model)
    assert len(calls) == 2 and "functional_inferences" in calls[1]["previous_validation_error"]
    assert sum(a.get("inference_rule") == RULE for a in ledger["associations"]) == (0 if decline else 1)
    if decline:
        assert any(g["reason"] == "functional_inference_declined" for g in ledger["gaps"])


def test_real_suggestion_producer_marks_auto_fill_as_inference(tmp_path, monkeypatch):
    d, ctx = draft(), context()
    stored = []
    def snapshot(task, owner, *, parsing_draft):
        return ev.complete_snapshot("upload", task, ev.draft_records(parsing_draft, {}), ctx["sources"], parsing_draft)
    monkeypatch.setattr(ev, "upload_snapshot", snapshot)
    monkeypatch.setattr(ev, "evaluate_batch", lambda rows, *a, **kw: [
        {"status": "supported", "reason": "测试原文直接报告其他字段",
         "evidences": [settings()["setting-0"]["fact_evidences"][0]], "location_errors": []} for _ in rows])
    monkeypatch.setattr("backend.ingest.upload_jobs._ensure_not_cancelled", lambda _: None)
    monkeypatch.setattr("backend.ingest.upload_tasks.artifact_directory", lambda _: tmp_path)
    @contextmanager
    def begin():
        yield object()
    monkeypatch.setattr("backend.database.SessionLocal", SimpleNamespace(begin=begin))
    monkeypatch.setattr(science, "save_results", lambda session, snap, results, owner: stored.append((deepcopy(snap), deepcopy(results))))
    monkeypatch.setattr("backend.ingest.pdf_source_pages.current_pdf_results", lambda session, snap, results: results)
    def model(prompt, body, **kwargs):
        data = json.loads(body)
        if "targets" not in data:
            return {"settings": list(settings().values())}
        return {"assignments": [{"setting_id": a["setting_id"], "targets": ["s/m/r"],
                                "basis_kind": "paper_quote", "scope": {"material": "LaSc2H24"},
                                "scope_evidences": a["scope_evidences"], "explanation": "同一计算流程的原文设置。"} for a in data["settings"]],
                "functional_inferences": [request()]}
    monkeypatch.setattr("backend.rag.llm.complete_json", model)
    checks = ev.generate_upload_suggestions("test", d, 1, scientific_sources=ctx["sources"])
    snap, saved = stored[0]
    leaf = next(r for r in snap["records"] if r.get("record_field") == "payload.calculation_conditions.exchange_correlation_functional")
    assert checks[leaf["key"]]["auto_filled"]
    assert saved[leaf["key"]]["adopted_basis"] == "paper_inference"
    assert saved[leaf["key"]]["status"] == "uncertain"
    assert leaf["source_associations"][0]["inference_rule"] == RULE
