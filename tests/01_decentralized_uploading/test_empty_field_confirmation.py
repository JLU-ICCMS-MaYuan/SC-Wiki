"""#221/#220：合法空值人工确认是版本化决定，不能授予普通修改或必填项通过。"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend import models,manual_evidence_models
from backend.ingest import property_evidence as ev,scientific_evidence as science,field_decisions as decisions,manual_evidence as manual
from backend.ingest.field_input import bind
from backend.ingest.field_review import valid_field_decision,reusable


@pytest.fixture
def context(sqlite_engine):
    state={"state_key":"cah4","material":"CaH4","material_name":"tI10-CaH4",
           "pressure_value_gpa":50,"state_kind":"theoretical","structure_families":[]}
    ctx={"paper":{"title":"Test","year":2026,"paper_type":"theoretical"},"material_states":[state]}
    def build(value):
        s={**state,"structure_families":value}
        snap=ev.complete_snapshot("upload","e"*32,science.state_records(s,0),
            [{"file_id":"main","chunk_index":0,"content":"CaH4 is tetragonal. CaH6 forms sodalite-like clathrates."}],
            {**ctx,"material_states":[s]})
        snap["records"]=[r for r in snap["records"] if r["field"].endswith(".structure_families")]
        return snap
    before=build(["Sodalite"]);current=build([])
    row=current["records"][0];current["_field_change_events"]=[{"kind":"field_change","item_key":row["item_key"],"before_value":["Sodalite"],"after_value":[]}]
    with Session(sqlite_engine) as db:
        yield db,current,before,SimpleNamespace(id=7,role="user",username="reviewer")


def explanation(db,snap,before,reason="此状态不采用结构家族分类",absence="暂无合适分类，不提供额外证据"):
    key=snap["records"][0]["item_key"]
    manual.save_explanation(db,snap,before,key,7,reason=reason,no_evidence_reason=absence,text_items=[])
    bind(snap,db)


def test_manual_empty_has_no_ai_claim_keeps_original_sources_and_passes(context):
    db,snap,before,actor=context;explanation(db,snap,before);r=snap["records"][0]
    old={"current_value":["Sodalite"],"status":"unsupported","reason":"旧值的AI判断","ai_reason":"旧值的AI判断",
         "review_error":"旧核对错误","evidences":[{"file_id":"main","chunk_index":0,"quote":"CaH4 is tetragonal."}],
         "content_hash":"old","source_hash":r["source_hash"],"stale":True}
    cached={r["key"]:old};original=deepcopy(old);view=decisions.detail(snap,cached)
    assert view["can_confirm_empty"]
    result=decisions.decide(db,snap,cached,actor,"confirm_empty",view["review_token"])
    row=result["record"]
    assert row["current_value"]==[] and row["status"]=="supported"
    assert row["field_decision"]["mode"]=="empty" and row["human_confirmed"]
    assert not row.get("review_error") and row["ai_reason"]==""
    assert row["evidences"]==[] and old==original  # #226：旧值依据不再展示为当前空值依据，原对象保留。
    assert "人工" in row["reason"] and "旧值的AI判断" not in row["reason"]
    assert valid_field_decision(r,row,"approve") and reusable(r,row)


@pytest.mark.parametrize("reason,absence",[("","完整缺证原因"),("完整人工理由","")])
def test_empty_requires_saved_complete_manual_materials(context,reason,absence):
    db,snap,before,actor=context;explanation(db,snap,before,reason,absence);r=snap["records"][0]
    view=decisions.detail(snap,{})
    assert not view["can_confirm_empty"]
    with pytest.raises(HTTPException):decisions.decide(db,snap,{},actor,"confirm_empty",view["review_token"])


@pytest.mark.parametrize("value",[0,False,"unknown","kept",["kept"]])
def test_nonempty_and_false_zero_are_not_omissions(context,value):
    db,snap,before,actor=context;explanation(db,snap,before)
    snap["records"][0]["current_value"]=value
    view=decisions.detail(snap,{})
    assert not view["can_confirm_empty"]
    with pytest.raises(HTTPException):decisions.decide(db,snap,{},actor,"confirm_empty",view["review_token"])


def test_manual_material_changes_invalidate_confirmation_and_token(context):
    db,snap,before,actor=context;explanation(db,snap,before);r=snap["records"][0]
    view=decisions.detail(snap,{})
    accepted=decisions.decide(db,snap,{},actor,"confirm_empty",view["review_token"])["record"]
    assert valid_field_decision(r,accepted)
    token=decisions.detail(snap,{r["key"]:accepted})["review_token"]
    explanation(db,snap,before,reason="新的人工留空理由")
    assert not valid_field_decision(r,accepted)
    assert not reusable(r,accepted)
    with pytest.raises(HTTPException):
        decisions.decide(db,snap,{r["key"]:accepted},actor,"confirm_empty",token)


@pytest.mark.parametrize("field,value",[("paper.title",""),("paper.year",None),("paper.material_families",[])])
def test_required_fields_cannot_use_empty_exception(context,field,value):
    db,snap,before,actor=context
    row=snap["records"][0];row.update(field=field,current_value=value)
    row["editable_fields"]=[{"path":"","value":value,"schema":{"type":"string","nullable":True}}]
    # 资格必须由程序按当前字段规则计算，不接受客户端/旧结果声明。
    from backend.ingest.empty_field_review import allowed
    assert not allowed(row,{"paper":{"paper_type":"theoretical"}})


def test_model_must_return_consistent_status_for_reasonable_omission(context):
    db,snap,before,actor=context;explanation(db,snap,before)
    from backend.ingest.model_review import review_fields
    row=snap["records"][0];calls=[]
    def model(_,payload,**kwargs):
        import json
        request=json.loads(payload);calls.append(request)
        result={"key":row["key"],"status":"missing" if len(calls)==1 else "supported",
            "reason":"不进行家族分类合理","source_ids":[],"not_reported":True,
            "manual_reason_review":{"status":"reasonable","explanation":"此分类可不填写，人工说明合理"}}
        return {"results":[result]}
    human=manual.review_context(db,snap)
    result=review_fields(snap["records"],snap["chunks"],model=model,human_context=human)
    assert len(calls)==2 and "不能与认可留空矛盾" in calls[1]["previous_error"]
    assert result[row["key"]]["status"]=="supported"
    assert not result[row["key"]].get("human_confirmed")


def test_omission_basis_is_independent_of_target_namespace(context):
    db,snap,before,actor=context;explanation(db,snap,before);r=snap["records"][0]
    confirmed=decisions.decide(db,snap,{},actor,"confirm_empty",decisions.detail(snap,{})["review_token"])["record"]
    m=manual.current_ids(db,snap,before)[r["key"]]
    stored=db.get(manual.ScientificManualEvidence,m["id"])
    stored.target="paper";stored.target_id="42";stored.paper_id=42;stored.paper_revision=1
    stored.status="submitted";db.flush()
    moved={**snap,"target":"paper","target_id":"42","review_state":["pending",None,1],
           "records":[deepcopy(r)]}
    bind(moved,db)
    assert moved["records"][0]["manual_evidence_hash"]==r["manual_evidence_hash"]
    assert valid_field_decision(moved["records"][0],confirmed)


@pytest.mark.parametrize("other,expected",[("CaH4",True),("",False)])
def test_clearing_material_name_keeps_identity_requirement(context,other,expected):
    from backend.ingest.empty_field_review import allowed
    db,snap,before,actor=context
    r={**snap["records"][0],"field":"material_states[0].material_name",
       "editable_fields":[{"path":"","schema":{"type":"string"}}]}
    assert allowed(r,{"material_states":[{"material":other}]}) is expected


def test_empty_capability_metadata_does_not_create_a_new_content_snapshot():
    from backend.services.manuscript_handoffs import content_hash
    plain={"records":[{"key":"field","current_value":[],"status":"uncertain"}]}
    decorated=deepcopy(plain)
    decorated["records"][0].update(empty_allowed=True,manual_evidence_complete=False,manual_evidence_hash="derived-hash")
    assert content_hash(plain)==content_hash(decorated)


def test_changing_evidence_invalidates_empty_confirmation(context,tmp_path,monkeypatch):
    from backend.ingest import manual_evidence as manual_module
    monkeypatch.setenv("FILE_STORAGE_BACKEND","local")
    monkeypatch.setenv("FILE_STORAGE_LOCAL_ROOT",str(tmp_path))
    monkeypatch.setattr(manual_module,"settings",SimpleNamespace(sc_wiki_data_dir=tmp_path))
    db,snap,before,actor=context;explanation(db,snap,before);row=snap["records"][0]
    result=decisions.decide(db,snap,{},actor,"confirm_empty",decisions.detail(snap,{})["review_token"])["record"]
    manual.add_file(db,snap,before,row["item_key"],actor.id,filename="note.txt",raw=b"new evidence",source_description="")
    bind(snap,db)
    assert not valid_field_decision(row,result)
    assert not reusable(row,result)


def test_required_tc_slot_cannot_be_confirmed_empty(context):
    from backend.ingest.empty_field_review import allowed
    db,snap,before,actor=context
    row={**snap["records"][0],"field":"material_states[0].property_modules[0].records[0].value_number",
         "record_field":"value_number","current_value":None,"scientific_record":{"record_type":"predicted_tc","value_kind":"number"},
         "editable_fields":[{"path":"","schema":{"type":"number","nullable":True}}]}
    assert not allowed(row,{"material_states":[]})


def test_saved_material_change_stays_pending_in_summary_not_only_detail(context):
    from backend.ingest.field_review import blocking,needs_review
    db,snap,before,actor=context;explanation(db,snap,before);r=snap["records"][0]
    accepted=decisions.decide(db,snap,{},actor,"confirm_empty",decisions.detail(snap,{})["review_token"])["record"]
    explanation(db,snap,before,reason="已经保存的新理由")
    incoming={**accepted,"stored_result":True,"stale":False}
    public=ev.checked_result(r,incoming,snap["chunks"])
    assert public["status"]=="unchecked" and public["stale"] and public["pending_review"]
    assert not public["human_confirmed"]
    assert blocking(r,public) and needs_review(r,public)


def test_older_submitted_materials_do_not_invalidate_current_confirmation(context):
    from datetime import datetime
    db,snap,before,actor=context;explanation(db,snap,before);r=snap["records"][0]
    from backend.ingest.field_input import current_manual
    current=current_manual(db,snap,r)
    values={c.name:deepcopy(getattr(current,c.name)) for c in current.__table__.columns}
    values.update(id="old-material",status="submitted",reason="旧已交出说明",
                  created_at=datetime(2020,1,1),updated_at=datetime(2020,1,1))
    db.add(manual.ScientificManualEvidence(**values));db.flush()
    bind(snap,db)
    confirmed=decisions.decide(db,snap,{},actor,"confirm_empty",decisions.detail(snap,{})["review_token"])["record"]
    current.status="submitted";db.flush()
    bind(snap,db)
    assert valid_field_decision(r,confirmed)
