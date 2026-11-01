"""#181：真实旧响应与四层方法语义，保留电子数值和来源。"""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from backend.ingest.calculation_methods import electronic_method_issue, record_method_issue
from backend.ingest.material_state_contract import state_metadata, structure_nuclear_treatment
from backend.ingest.state_optimization import resolve_candidates

FIXTURE = Path(__file__).parents[1] / "fixtures/issue181/optimization-replay.json"


def test_original_optimizer_response_cannot_broadcast_phonon_approximation():
    fixture = json.loads(FIXTURE.read_text())
    before = fixture["candidates"]
    result, issues = resolve_candidates(before, fixture["sources"], lambda *args: deepcopy(fixture["response"]))
    assert not issues
    original = [r for c in before for s in c["material_states"] for m in s["property_modules"] for r in m["records"]]
    final = [r for c in result for s in c["material_states"] for m in s["property_modules"] for r in m["records"]]
    assert [r["payload"] for r in final] == [r["payload"] for r in original]
    assert [r.get("value_number") for r in final[:3]] == [3.05, 0.48, 0.02234]
    assert [r["property_code"] for r in final[:3]] == ["band_gap", "band_gap", "dos_fermi"]
    assert before == fixture["candidates"]


@pytest.mark.parametrize("value", ["harmonic", "anharmonic", "SSCHA", "quasi-harmonic"])
def test_vibrations_are_not_electronic_theories(value):
    assert electronic_method_issue(value)


@pytest.mark.parametrize("optimization,nuclear", [
    ("classical_static", "classical_static"), ("quasi_harmonic", "quasi_harmonic"),
    ("anharmonic_quantum", "unknown"), ("unknown", "unknown"),
    ("sscha", "anharmonic_quantum"),
])
def test_structural_objectives_and_legacy_alias(optimization, nuclear):
    state={"state_kind":"theoretical","structure_optimization":optimization,
           "structure_optimization_details":{"method":"reported method","temperature_k":0,
             "centroids":"optimized","volume":"fixed","cell_shape":"unknown"}}
    assert "structure_optimization_details" not in state_metadata(state)
    assert structure_nuclear_treatment(state) == nuclear


def record(code="band_gap", **conditions):
    return {"property_code":code,"record_type":"property" if code!="tc" else "predicted_tc",
            "value_number":3.05,"payload":{"calculation_conditions":conditions}}


def test_electronic_result_does_not_inherit_epc_treatment():
    assert record_method_issue(record(vibrational_treatment="harmonic"))
    assert record_method_issue(record(phonon_method="DFPT"))
    assert record_method_issue(record(electronic_method="DFT")) is None
    assert record_method_issue(record("tc",electronic_method="DFT",phonon_method="DFPT",vibrational_treatment="harmonic")) is None


def test_reported_electron_phonon_correction_is_allowed_with_relation_evidence():
    r=record(phonon_method="finite displacement",vibrational_treatment="harmonic",
             method_scope={"physical_object":"electronic","stage":"electronic_structure",
               "relation":"electron_phonon_renormalization",
               "relation_evidences":[{"quote":"The electronic band gap is renormalized by electron-phonon coupling."}]})
    r["evidences"] = deepcopy(r["payload"]["calculation_conditions"]["method_scope"]["relation_evidences"])
    assert record_method_issue(r) is None
    r["payload"]["calculation_conditions"]["method_scope"]["relation_evidences"]=[]
    assert record_method_issue(r)


@pytest.mark.parametrize("field,value",[("phonon_method","DFT"),("vibrational_treatment","DFPT"),("vibrational_treatment","DFT")])
def test_other_method_fields_reject_category_errors(field,value):
    assert record_method_issue(record("tc",**{field:value}))


def test_retired_geometry_details_are_ignored_not_written_as_active_parameters():
    for value in ({"volume":"automatic"}, {"electronic_method":"harmonic"}):
        assert "structure_optimization_details" not in state_metadata({
            "state_kind":"theoretical", "structure_optimization":"classical_static",
            "structure_optimization_details":value})


def test_partial_save_validates_only_changed_method_and_preserves_history():
    from backend.ingest.field_drafts import apply_changes
    from fastapi import HTTPException
    r=record(electronic_method="DFT")
    r.update(record_key="r")
    d={"paper":{"title":"Old"},"material_states":[{"state_key":"s","property_modules":[{"module_key":"m","records":[r]}]}]}
    path=["material_states",{"key":"state_key","value":"s"},"property_modules",{"key":"module_key","value":"m"},
          "records",{"key":"record_key","value":"r"},"payload","calculation_conditions","electronic_method"]
    before=deepcopy(d)
    with pytest.raises(HTTPException):
        apply_changes(d,[{"path":path,"before":"DFT","value":"harmonic"}])
    assert d==before
    changed=apply_changes(d,[{"path":path,"before":"DFT","value":"HF"}])
    assert changed["material_states"][0]["property_modules"][0]["records"][0]["value_number"]==3.05
    r["payload"]["approximation"]="harmonic"
    r["payload"]["manual_history"]=[{"reason":"Keep this note"}]
    title=apply_changes(d,[{"path":["paper","title"],"before":"Old","value":"New"}])
    assert title["material_states"]==d["material_states"]


@pytest.mark.parametrize("objective,text,success", [
 ("quasi_harmonic","The QHA free energy of CaH2 was minimized over volume at 0 K; the optimized structure is unchanged.",True),
 ("anharmonic_quantum","SSCHA was used for structural relaxation by minimizing the quantum free energy over centroids at 0 K, keeping cell volume fixed.",True),
 ("anharmonic_quantum","DFT structural optimization was performed. SSCHA was used only for phonon frequencies with fixed centroids and cell.",False),
 ("quasi_harmonic","DFT structural relaxation was performed. The quasiharmonic model was used for zero-point energies only.",False),
])
def test_geometry_objective_requires_actual_geometry_workflow(objective,text,success):
    state={"material":"CaH2","state_kind":"theoretical","structure_optimization":"unknown","property_modules":[]}
    response={"workflows":[{"id":"w","material":"CaH2","optimization":objective,"evidences":[{"workflow_source_id":"workflow-source-0"}]}],
      "assignments":[{"target":"0/0","optimization":objective,"workflow_id":"w",
        "structure_optimization_details":{"method":"reported","temperature_k":0,"volume":"fixed","centroids":"optimized"},
        "evidences":[{"source_index":0,"quote":text}]}]}
    result,issues=resolve_candidates([{"material_states":[state]}],[{"file_id":"main","content":text}],lambda *a:deepcopy(response))
    assert not issues if success else issues
    assert result[0]["material_states"][0]["structure_optimization"]==(objective if success else "unknown")


def test_electronic_value_and_bad_legacy_label_have_separate_reviews():
    from backend.ingest import property_evidence as evidence
    r=record(electronic_method="DFT")
    r.update(record_key="r",module_code="electronic_properties",name_raw="Electronic gap",value_kind="number",value_raw="3.05")
    r["payload"]["approximation"]="harmonic"
    d={"paper":{},"material_states":[{"state_key":"s","material":"CaH2","state_kind":"theoretical",
       "property_modules":[{"module_key":"m","module_code":"electronic_properties","records":[r]}]}]}
    snap=evidence.complete_snapshot("upload","isolated",evidence.draft_records(d,{}),
        [{"file_id":"main","content":"The electronic band gap is 3.05 eV."}],{})
    number=next(row for row in snap["records"] if row.get("record_field")=="value_number")
    label=next(row for row in snap["records"] if row.get("record_field")=="payload.approximation")
    from backend.ingest.calculation_methods import review_method_issue
    assert review_method_issue(number) is None
    assert review_method_issue(label)
    assert number["current_value"]==3.05
    assert "payload.approximation" not in number["record_dependencies"]
    assert "payload.calculation_conditions.electronic_method" in number["record_dependencies"]


def test_claiming_electron_phonon_relation_with_unlocated_quote_cannot_bypass_scope():
    r=record(vibrational_treatment="harmonic",method_scope={"relation":"electron_phonon_renormalization",
      "relation_evidences":[{"quote":"Electronic band gap is renormalized by phonons."}]})
    r["evidences"]=[{"quote":"The EPC calculation uses the harmonic approximation."}]
    assert record_method_issue(r)


def test_changing_bad_legacy_label_does_not_invalidate_the_electronic_number():
    from backend.ingest import property_evidence as evidence
    def snapshot(legacy,theory):
        r=record(electronic_method=theory)
        r.update(record_key="r",module_code="electronic_properties",name_raw="Gap",value_kind="number",value_raw="3.05")
        r["payload"]["approximation"]=legacy
        d={"material_states":[{"state_key":"s","material":"CaH2","state_kind":"theoretical",
            "property_modules":[{"module_key":"m","module_code":"electronic_properties","records":[r]}]}]}
        snap=evidence.complete_snapshot("upload","test",evidence.draft_records(d,{}),[],{})
        return {x["record_field"]:x for x in snap["records"] if x.get("record_field")}
    first=snapshot("harmonic","DFT");label_changed=snapshot("anharmonic","DFT");theory_changed=snapshot("harmonic","HF")
    assert first["value_number"]["content_hash"]==label_changed["value_number"]["content_hash"]
    assert first["payload.approximation"]["content_hash"]!=label_changed["payload.approximation"]["content_hash"]
    assert first["value_number"]["content_hash"]!=theory_changed["value_number"]["content_hash"]


def test_fixed_centroid_sscha_does_not_imply_geometry_optimization():
    text="CaH2 SSCHA phonon calculations used fixed centroids, volume and cell shape."
    state={"material":"CaH2","state_kind":"theoretical","structure_optimization":"unknown","property_modules":[]}
    response={"assignments":[{"target":"0/0","optimization":"unknown",
       "structure_optimization_details":{"method":"SSCHA","centroids":"fixed","volume":"fixed","cell_shape":"fixed"},
       "evidences":[{"source_index":0,"quote":text}]}]}
    result,issues=resolve_candidates([{"material_states":[state]}],[{"file_id":"main","content":text}],lambda *a:response)
    assert not issues
    assert result[0]["material_states"][0]["structure_optimization"]=="unknown"
    assert "structure_optimization_details" not in result[0]["material_states"][0]


def test_epc_setting_cannot_be_attached_to_electronic_result_by_same_card():
    from backend.ingest.scientific_context import build_context, apply_associations, scientific_fingerprint
    r=record(electronic_method="HF")
    r.update(record_key="r",module_code="electronic_properties",value_kind="number",value_raw="3.05")
    d={"material_states":[{"state_key":"s","material":"CaH2","pressure_value_gpa":150,
      "property_modules":[{"module_key":"m","module_code":"electronic_properties","records":[r]}]}]}
    before=deepcopy(d)
    ctx=build_context([{"file_id":"main","content":"The CaH2 EPC calculation uses DFT at 150 GPa."}])
    c={"target":"s/m/r","expected_fingerprint":scientific_fingerprint(r),
       "target_path":"/payload/calculation_conditions/extensions/-",
       "value":{"key":"electron_phonon.electronic_method","value_kind":"text","value_raw":"DFT"},
       "stage":"electron_phonon","basis_kind":"paper_quote","scope":{"material":"CaH2"},
       "reported_value_raw":"DFT","explanation":"This quote refers only to EPC.",
       "fact_evidences":[{"source_id":"source-0"}],"scope_evidences":[{"source_id":"source-0"}]}
    applied,gaps=apply_associations(d,[c],ctx)
    assert not applied and gaps[0]["reason"]=="scope_ambiguous"
    assert d==before


def test_known_workflow_software_pressure_and_phase_are_real_scope_dependencies():
    from backend.ingest.scientific_context import _scope_matches
    r=record(electronic_method="HF",calculation_code="VASP",
             method_scope={"stage":"electronic_structure","workflow_id":"electronic-v1"})
    state={"material":"CaH2","pressure_value_gpa":150,"reported_space_group_symbol":"Pnma"}
    for difference in [{"pressure_value_gpa":0},{"reported_space_group_symbol":"Im-3m"},
                       {"software":"Quantum ESPRESSO"},{"workflow_id":"phonons-v1"}]:
        assert not _scope_matches({"material":"CaH2",**difference},state,r,"electronic_structure")


def test_sscha_full_method_name_is_not_confused_with_harmonic_treatment():
    r=record("tc",phonon_method="stochastic self-consistent harmonic approximation",
             vibrational_treatment="anharmonic_quantum")
    assert record_method_issue(r) is None


def test_new_tc_value_depends_on_its_actual_vibration_layer():
    from backend.ingest.review_dependencies import record_inputs
    r=record("tc",vibrational_treatment="harmonic",electronic_method="DFT")
    assert "payload.calculation_conditions.vibrational_treatment" in record_inputs(r,"value_number")
    # 同一变化不成为普通电子数值的依赖。
    r["property_code"]="band_gap";r["record_type"]="property"
    assert "payload.calculation_conditions.vibrational_treatment" not in record_inputs(r,"value_number")


def test_saving_unrelated_condition_does_not_force_repair_of_legacy_method_labels():
    from backend.ingest.field_drafts import apply_changes
    r=record(electronic_method="DFPT")
    r.update(record_key="r")
    r["payload"]["calculation_conditions"]["extensions"]=[{"field_key":"grid","key":"electronic_structure.k_grid","value_kind":"text","value_raw":"2x2x2"}]
    d={"material_states":[{"state_key":"s","property_modules":[{"module_key":"m","records":[r]}]}]}
    prefix=["material_states",{"key":"state_key","value":"s"},"property_modules",{"key":"module_key","value":"m"},"records",{"key":"record_key","value":"r"},"payload","calculation_conditions"]
    changed=apply_changes(d,[{"path":prefix+["extensions",{"key":"field_key","value":"grid"},"value_raw"],"before":"2x2x2","value":"3x3x3"}])
    condition=changed["material_states"][0]["property_modules"][0]["records"][0]["payload"]["calculation_conditions"]
    assert condition["electronic_method"]=="DFPT"
    assert condition["extensions"][0]["value_raw"]=="3x3x3"


def test_generic_dos_name_cannot_override_explicit_phonon_source():
    from test_issue114_domain_extraction import extraction
    from backend.ingest.domain_extraction import normalize_extraction
    raw=extraction()
    module=raw["material_states"][0]["property_modules"][0]
    module["module_code"]="electronic_properties"
    r=module["records"][0]
    r.update(module_code="electronic_properties",record_type="property",property_code="dos_fermi",
       name_raw="DOS",value_kind="number",value_number=1.2,value_raw="1.2",unit_raw="states/eV/f.u.",
       canonical_unit="states/eV/f.u.",method_code=None,payload={})
    quote="The phonon density of states has a peak of 1.2 in arbitrary units."
    r["evidences"][0]["quote"]=quote
    with pytest.raises(ValueError,match="声子"):
        normalize_extraction(raw,allowed_blocks={("main",1,"b1")})


@pytest.mark.parametrize("text",["The phonons are anharmonic.","A quasi-harmonic treatment was used.",
    "The stochastic self-consistent harmonic approximation was used."])
def test_harmonic_layer_cannot_be_supported_by_substring_in_another_concept(text):
    from backend.ingest.condition_rules import value_matches
    assert not value_matches("harmonic","vibrational_treatment",[{"quote":text}])


@pytest.mark.parametrize("value,text",[
 ("harmonic","Phonons use the harmonic approximation."),
 ("quasi_harmonic","The quasi-harmonic free energy was minimized."),
 ("anharmonic_quantum","Quantum anharmonic vibrations were included."),
 ("anharmonic_classical","Classical anharmonic dynamics were considered."),
])
def test_explicitly_reported_vibration_layer_remains_matchable(value,text):
    from backend.ingest.condition_rules import value_matches
    assert value_matches(value,"vibrational_treatment",[{"quote":text}])


def test_general_anharmonic_scope_can_apply_to_explicit_quantum_anharmonic_workflow():
    from test_issue139_scientific_context import draft
    from backend.ingest.scientific_context import build_context,apply_associations,scientific_fingerprint
    d=draft();r=d["material_states"][0]["property_modules"][0]["records"][0]
    r["payload"]["calculation_conditions"]["vibrational_treatment"]="anharmonic_quantum"
    ctx=build_context([{"file_id":"main","content":"For LaSc2H24, the SSCHA anharmonic workflow uses a 2x2x2 k grid."}])
    candidate={"target":"s/m/r","expected_fingerprint":scientific_fingerprint(r),
      "target_path":"/payload/calculation_conditions/extensions/-",
      "value":{"key":"sscha.k_grid","value_kind":"text","value_raw":"2x2x2"},
      "stage":"sscha","basis_kind":"paper_quote","scope":{"material":"LaSc2H24","approximation":"anharmonic"},
      "reported_value_raw":"2x2x2","explanation":"The general anharmonic scope includes this explicitly quantum-anharmonic target.",
      "fact_evidences":[{"source_id":"source-0"}],"scope_evidences":[{"source_id":"source-0"}]}
    applied,gaps=apply_associations(d,[candidate],ctx)
    assert len(applied)==1 and not gaps
    from backend.ingest.scientific_context import association_issues
    from backend.ingest.property_modules import validate_record
    restored=d["material_states"][0]["property_modules"][0]["records"][0]
    assert not association_issues(restored)
    validate_record(restored)
    bad=deepcopy(restored)
    bad["payload"]["source_associations"][0]["field_binding"]["version"]=99
    assert association_issues(bad)
