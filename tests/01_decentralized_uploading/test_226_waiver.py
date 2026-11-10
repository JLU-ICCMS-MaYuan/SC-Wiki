"""#226 正常改值与当前版本无证人工决定，旧来源不能给新值背书。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from test_empty_field_confirmation import context,explanation
from backend.ingest import field_decisions as decisions,scientific_evidence as science,manual_evidence as manual
from backend.ingest.field_input import bind
from backend.ingest.field_review import valid_field_decision,blocking
from backend.ingest import property_evidence as ev

def test_current_value_can_be_waived_without_materials_and_reopened(context):
    db,snap,before,actor=context
    r=snap["records"][0]
    view=decisions.detail(snap,{})
    result=decisions.decide(db,snap,{},actor,"approve_without_evidence",view["review_token"])
    db.commit()
    row=result["record"]
    assert row["field_decision"]["mode"]=="without_evidence"
    assert row["human_confirmed"] and row["status"]=="supported"
    assert row["evidences"]==[] and row["ai_reason"]==""
    assert row["machine_status"]=="unchecked" and not row.get("model_review")
    cached=science.load_results(db,snap,actor.id,include_stale=True)
    reopened=decisions.detail(snap,cached)
    assert reopened["record"]["field_decision"]["mode"]=="without_evidence"
    assert not blocking(r,cached[r["key"]])
    assert manual.validate_submission(db,snap,before)==[]

def test_complete_materials_revoke_waiver_partial_does_not(context):
    db,snap,before,actor=context;r=snap["records"][0]
    row=decisions.decide(db,snap,{},actor,"approve_without_evidence",decisions.detail(snap,{})["review_token"])["record"]
    explanation(db,snap,before,reason="新的判断理由",absence="暂不提供")
    assert valid_field_decision(r,row,"approve")
    manual.save_explanation(db,snap,before,r["item_key"],actor.id,reason="原文允许不额外分类",
        no_evidence_reason="",text_items=[{"text":"CaH4 has tetragonal symmetry.","source_description":"SI"}])
    bind(snap,db)
    assert not valid_field_decision(r,row,"approve") and blocking(r,row)
    checked=ev.checked_result(r,row,snap["chunks"])
    assert checked["pending_review"] and checked["status"]=="unchecked"

def test_new_value_does_not_display_old_ai_claim_or_evidence(context):
    db,snap,before,actor=context;r=snap["records"][0]
    old={"current_value":["Sodalite"],"status":"supported","reason":"旧值确定正确","ai_reason":"旧值确定正确",
         "evidences":[{"file_id":"main","quote":"Old assertion"}],"content_hash":"old","source_hash":r["source_hash"],"stale":True}
    view=decisions.detail(snap,{r["key"]:old})
    assert not view["record"]["ai_reason"] and not view["record"]["evidences"]
    assert "旧值确定正确" not in view["record"]["reason"]

def test_required_title_cannot_be_waived_as_empty(context):
    db,snap,before,actor=context;r=snap["records"][0]
    r.update(field="paper.title",current_value="",empty_allowed=False,editable_fields=[{"path":"","schema":{"type":"string"}}])
    with pytest.raises(HTTPException):
        decisions.decide(db,snap,{},actor,"approve_without_evidence",decisions.detail(snap,{})["review_token"])


def test_partial_material_version_is_projected_without_losing_yellow(context):
    db,snap,before,actor=context;r=snap['records'][0]
    decisions.decide(db,snap,{},actor,'approve_without_evidence',decisions.detail(snap,{})['review_token'])
    db.commit()
    explanation(db,snap,before,reason='只补了理由',absence='')
    from backend.ingest.field_review import bind_support_versions
    bind_support_versions(snap,db)
    loaded=science.load_results(db,snap,actor.id,include_stale=True)
    assert valid_field_decision(r,loaded[r['key']],'approve')
    assert decisions.detail(snap,loaded)['record']['human_confirmed']


def test_changed_value_does_not_reuse_old_manual_materials(context):
    db,snap,before,actor=context;explanation(db,snap,before)
    from backend.ingest.field_input import current_manual
    original=snap['records'][0]
    changed={**snap,'records':[{**original,'current_value':['New family'],'content_hash':'new-value'}]}
    assert current_manual(db,changed,changed['records'][0]) is None
    row=manual.save_explanation(db,changed,before,original['item_key'],actor.id,
        reason='当前值的新理由',no_evidence_reason='',text_items=[])
    assert row['reason']=='当前值的新理由' and row['items']==[]
