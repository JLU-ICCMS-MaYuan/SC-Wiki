"""#139：US5已撤销，历史可读；专用和普通关联不能再补猜QE泛函。"""
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



def candidate(d, ctx, *, rule=None):
    return {"target":"s/m/r", "expected_fingerprint":sc.scientific_fingerprint(d["material_states"][0]["property_modules"][0]["records"][0]),
        "target_path":"/payload/calculation_conditions/exchange_correlation_functional", "value":"PBE",
        "reported_value_raw":"PBE", "stage":"electron_phonon", "basis_kind":"paper_inference",
        "scope":{"material":"LaSc2H24"}, "explanation":"旧的跨软件泛函推断",
        "fact_evidences":[sc.located({"source_id":"source-0"},ctx["sources"])],
        "scope_evidences":[sc.located({"source_id":"source-1"},ctx["sources"])],
        **({"inference_rule":rule} if rule else {})}


def test_retired_dedicated_entry_never_returns_candidates():
    candidates,gaps=functional_inference_candidates([request()],settings(),targets(draft()),context())
    assert candidates == [] and gaps[0]["reason"]=="functional_inference_retired"


def test_old_cached_inference_and_untagged_cross_software_assignment_cannot_fill():
    for rule in [None,RULE]:
        d=draft()
        r=d["material_states"][0]["property_modules"][0]["records"][0]
        r["payload"]["calculation_conditions"]["calculation_code"]="Quantum ESPRESSO"
        applied,gaps=sc.apply_associations(d,[candidate(d,context(),rule=rule)],context())
        assert not applied and gaps[0]["reason"]=="software_functional_unreported"
        assert "exchange_correlation_functional" not in r["payload"]["calculation_conditions"]


def test_explicit_qe_functional_still_fills():
    d=draft()
    r=d["material_states"][0]["property_modules"][0]["records"][0]
    r["payload"]["calculation_conditions"]["calculation_code"]="Quantum ESPRESSO"
    ctx=sc.build_context([{"file_id":"main","chunk_index":0,"content":"For LaSc2H24, Quantum ESPRESSO uses PBE."},
                          {"file_id":"main","chunk_index":1,"content":"These settings apply to LaSc2H24."}])
    applied,gaps=sc.apply_associations(d,[candidate(d,ctx)],ctx)
    assert len(applied)==1 and not gaps
    assert r["payload"]["calculation_conditions"]["exchange_correlation_functional"]=="PBE"


def test_dfpt_association_adds_dft_definition_inference_without_guessing_functional():
    d=draft()
    ctx=sc.build_context([{"file_id":"main","chunk_index":0,
        "content":"For LaSc2H24, phonons are calculated with Quantum ESPRESSO using DFPT."}])
    def model(system,payload,**kwargs):
        data=json.loads(payload)
        if "sources" in data:
            return {"settings":[{"key":"phonon_method","stage":"electron_phonon","value":"DFPT",
                "scope":{"material":"LaSc2H24"},"reported_value_raw":"DFPT",
                "fact_evidences":[{"source_id":data["sources"][0]["source_id"]}],
                "scope_evidences":[{"source_id":data["sources"][0]["source_id"]}],"explanation":"当前流程明确使用DFPT"}]}
        return {"assignments":[{"setting_id":data["settings"][0]["setting_id"],
            "targets":[data["targets"][0]["target"]],"scope":{"material":"LaSc2H24"},
            "basis_kind":"paper_inference","explanation":"当前流程与本条材料相同"}]}
    ledger=sc.generate_context_associations(d,ctx,model)
    applied,gaps=sc.apply_associations(d,ledger["associations"],ctx)
    r=d["material_states"][0]["property_modules"][0]["records"][0]
    assert r["payload"]["calculation_conditions"]["electronic_method"]=="DFT"
    assert any(e["key"]=="electron_phonon.phonon_method" for e in r["payload"]["calculation_conditions"]["extensions"])
    assert "exchange_correlation_functional" not in r["payload"]["calculation_conditions"]
    assert not sc.association_issues(r)
