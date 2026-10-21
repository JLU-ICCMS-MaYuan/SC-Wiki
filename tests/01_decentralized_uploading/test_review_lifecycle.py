"""保存合同与共用条件生命周期：真实类型和反例，不调用模型。"""
from copy import deepcopy
import pytest
from fastapi import HTTPException
from backend.ingest import evidence_proposals as proposals, condition_rules as rules


def property_row(kind="text"):
    values = {"number": {"value_number": 17.27}, "text": {"value_text": "17.27"},
              "range": {"value_min": 17., "value_max": 19.}, "boolean": {"value_boolean": True}}
    record = dict(name_raw="N(Ef)", value_kind=kind, value_raw="17.27", unit_raw="states/spin/Ry/f.u.",
                  value_number=None, value_min=None, value_max=None, value_text=None, value_boolean=None,
                  uncertainty=None, canonical_unit=None, method_code=None, payload={})
    record.update(values[kind])
    return {"kind":"property", "claim":{"record":record}, "field":"material_states[0].property_modules[0].records[0]"}


@pytest.mark.parametrize("kind", ["text", "number", "range", "boolean"])
def test_property_roundtrip_all_value_kinds(kind):
    row=property_row(kind)
    values={f["path"]:f["value"] for f in proposals.editable_fields(row)}
    assert proposals.validate_values(row, values)==values


@pytest.mark.parametrize("value", [None, "17.27", True, float("nan")])
def test_active_number_slot_stays_strict(value):
    with pytest.raises(HTTPException): proposals.validate_values(property_row("number"), {"value_number":value})


def test_unused_slot_must_stay_empty_and_name_can_change():
    row=property_row()
    with pytest.raises(HTTPException): proposals.validate_values(row, {"value_number":3})
    proposals.validate_values(row, {"name_raw":"N(EF)", "value_number":None})


def test_sscha_extension_roundtrip_and_identity_protection():
    value={"key":"sscha.calculation_code", "name":"SSCHA软件", "value_kind":"text", "value_raw":"SSCHA", "unit_raw":None}
    row={"kind":"field", "record_field":"payload.calculation_conditions.extensions.0", "current_value":value,
         "label":"SSCHA软件", "claim":{"value":value}, "field_schema":{"type":"object","nullable":True}}
    proposals.validate_values(row, {"":deepcopy(value)})
    with pytest.raises(HTTPException): proposals.validate_values(row, {"":{**value,"key":"other"}})
    with pytest.raises(HTTPException): proposals.validate_values(row, {"":{**value,"unit_raw":3}})


def test_sscha_condition_identity_independent_of_tc():
    value={"key":"sscha.calculation_code","value_kind":"text","value_raw":"SSCHA"}
    row={"record_field":"payload.calculation_conditions.extensions.0", "current_value":value,
         "claim":{"context":{"material":"LaSc2H24","reported_space_group_symbol":"P6/mmm","pressure_value_gpa":250}},
         "validation_record":{"value_number":331,"payload":{"calculation_conditions":{"extensions":[value]},"parameters":{"lambda_ep":2.89,"omega_log":1075}}}}
    before=rules.descriptor(row)
    row["validation_record"]["value_number"]=296
    assert rules.descriptor(row)==before
    assert "result_numbers" not in before


def legacy_review(monkeypatch):
    from test_condition_auto_review import snapshot, evaluate
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    snap, row = snapshot()
    _, saved = evaluate(monkeypatch, snap, row)
    previous = {**deepcopy(row), **saved[row['key']]}
    previous['claim']['context']['condition_policy']['version'] = 'condition-rules-v1'
    previous['claim']['context']['condition_policy']['result_numbers'] = [331]
    previous['condition_context'] = deepcopy(previous['claim']['context']['condition_policy'])
    previous['content_hash'] = ev.digest(science.canonical(previous['claim']))
    previous['rule_review'].update(version='condition-rules-v1', content_hash=previous['content_hash'])
    return snap, row, previous


def test_known_legacy_evidence_revalidated_without_mutating_original(monkeypatch):
    from backend.ingest.condition_lifecycle import recover
    from backend.ingest import property_evidence as ev
    snap, row, old = legacy_review(monkeypatch)
    before=deepcopy(old)
    result=recover(row, old, snap['chunks'])
    assert result and result['review_revalidation']
    assert ev.checked_result(row,result,snap['chunks'])['status']=='supported'
    assert old==before


@pytest.mark.parametrize('change', ['value', 'source', 'stage', 'rule', 'evidence', 'coverage', 'hash'])
def test_revalidation_never_relabels_invalid_old_evidence(monkeypatch, change):
    from backend.ingest.condition_lifecycle import recover
    snap,row,old=legacy_review(monkeypatch)
    if change=='value': row['claim']['value']='12×12×12'
    if change=='source': row['source_hash']='different'
    if change=='stage': row['claim']['context']['condition_policy']['stage']='sscha'
    if change=='rule': old['rule_review']['version']='unknown'
    if change=='evidence': old['rule_review']['assessments'][0]['fact_evidences'][0]['quote']='invented'
    if change=='coverage': old['rule_review']['coverage']=[]
    if change=='hash': old['claim']['value']='tampered'
    assert recover(row,old,snap['chunks']) is None


def test_attempt_failure_and_real_conflict_have_distinct_effects(monkeypatch):
    from backend.ingest.condition_lifecycle import effective_result
    snap,row,old=legacy_review(monkeypatch)
    failed={**deepcopy(row),'status':'uncertain','reason':'软件证据遗漏','rule_review':None}
    result=effective_result(row,failed,[old,failed],snap['chunks'])
    assert result['rule_review'] and result['review_attempt']['reason']=='软件证据遗漏'
    conflict={**failed,'condition_conflict':True}
    assert not effective_result(row,conflict,[old,conflict],snap['chunks']).get('rule_review')
    # 后续同版本失败不能越过此前明确冲突恢复更旧的支持。
    assert not effective_result(row,failed,[old,conflict,failed],snap['chunks']).get('rule_review')


def test_new_result_scope_is_checked_without_revoking_conditions():
    from backend.ingest.condition_lifecycle import result_scope_issue
    row={'record_field':'value_number','required':True,'claim':{'context':{'pressure_value_gpa':250}},
         'validation_record':{'value_number':296,'payload':{'calculation_conditions':{'extensions':[{'key':'sscha.calculation_code'}]},
                              'parameters':{'lambda_ep':2.89,'omega_log':1075}}}}
    chunks=[{'content':'Anharmonic 250 2.89 1075 331 296'}]
    assert result_scope_issue(row,chunks) is None
    row['validation_record']['value_number']=999
    assert result_scope_issue(row,chunks)
    row['record_field']='payload.calculation_conditions.extensions.0'
    assert result_scope_issue(row,chunks) is None


def test_same_group_condition_survives_new_carrier_without_old_association(monkeypatch):
    from backend.ingest.condition_lifecycle import recover
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    snap,row,old=legacy_review(monkeypatch)
    old['claim']['context'].setdefault('direct_inputs', {})
    old['content_hash']=ev.digest(science.canonical(old['claim']))
    old['rule_review']['content_hash']=old['content_hash']
    row=deepcopy(row)
    row['record_group_key']='same-group'
    row['source_associations']=[]
    row['claim']['context'].pop('association_dependencies',None)
    row['content_hash']=ev.digest(science.canonical(row['claim']))
    assert recover(row,old,snap['chunks'])
    row['item_key']='different-group'
    assert recover(row,old,snap['chunks']) is None
