"""#185：实际修改项、双页覆盖和稳定结构变化。"""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from sqlalchemy.orm import sessionmaker
from backend import database
from backend.ingest import upload_tasks as tasks
from backend.ingest.field_drafts import apply_changes, draft_version, save_fields
from test_upload_extraction_timing import MemoryRedis


def draft():
    return {"_field_edit_format":1,"paper":{"title":"Fixture","year":2026},
      "material_states":[{"state_key":"s","property_modules":[{"module_key":"m","module_code":"superconductive_properties","records":[
        {"record_key":"r1","record_type":"predicted_tc","property_code":"tc","value_kind":"number","value_number":230,"payload":{"parameters":{"lambda_ep":2.69}}},
        {"record_key":"r2","record_type":"predicted_tc","property_code":"tc","value_kind":"number","value_number":220,"payload":{"parameters":{"lambda_ep":2.69}}},
      ]}]}]}


def path(key="r1"):
    return ["material_states",{"key":"state_key","value":"s"},"property_modules",{"key":"module_key","value":"m"},
            "records",{"key":"record_key","value":key}]


@pytest.fixture
def target(sqlite_engine,monkeypatch):
    factory=sessionmaker(sqlite_engine)
    client=MemoryRedis();task="185"+"a"*29
    monkeypatch.setattr(database,"SessionLocal",factory)
    monkeypatch.setattr(tasks,"redis_client",lambda:client)
    client.set(tasks.task_key(task),json.dumps({"task_id":task,"user_id":7,"status":"ready"}))
    client.set(tasks.draft_key(task),json.dumps(draft()))
    return factory,task,SimpleNamespace(id=7,username="fixture",role="user")


def test_two_pages_different_values_both_survive_old_page_version(target):
    factory,task,user=target
    from backend.services.workdrafts import open_draft
    with factory.begin() as session:
        lease=open_draft(session,'upload',task,user);version=lease.write_epoch+':'+draft_version(draft())
    with factory.begin() as session:
        save_fields(session,"upload",task,user,version,[{"path":path()+["payload","parameters","lambda_ep"],"before":2.69,"value":3.0}])
    with factory.begin() as session:
        save_fields(session,"upload",task,user,version,[{"path":path()+["value_number"],"before":230,"value":240}])
    saved=tasks.get_draft(task)["material_states"][0]["property_modules"][0]["records"][0]
    assert saved["value_number"]==240 and saved["payload"]["parameters"]["lambda_ep"]==3.0


def test_last_successful_same_field_write_wins(target):
    factory,task,user=target
    from backend.services.workdrafts import open_draft
    with factory.begin() as session:
        lease=open_draft(session,'upload',task,user);version=lease.write_epoch+':'+draft_version(draft())
    for value in [240,250]:
        with factory.begin() as session:
            save_fields(session,"upload",task,user,version,[{"path":path()+["value_number"],"before":230,"value":value}])
    assert tasks.get_draft(task)["material_states"][0]["property_modules"][0]["records"][0]["value_number"]==250


def test_stable_removal_does_not_replace_other_pages_unmodified_values():
    value=draft()
    value["material_states"][0]["property_modules"][0]["records"][1]["value_number"]=225
    changes=[{"op":"remove_item","path":path()[:-1],"identity":{"key":"record_key","value":"r1"}}]
    updated=apply_changes(value,changes)
    assert updated["material_states"][0]["property_modules"][0]["records"]==[value["material_states"][0]["property_modules"][0]["records"][1]]


def test_reorder_keeps_new_unseen_points_and_targets():
    value=draft();records=value["material_states"][0]["property_modules"][0]["records"]
    records.insert(1,{"record_key":"new","value_number":215})
    updated=apply_changes(value,[{"op":"reorder","path":path()[:-1],"key":"record_key","order":["r2","r1"]}])
    assert [r["record_key"] for r in updated["material_states"][0]["property_modules"][0]["records"]]==["r2","new","r1"]


def test_changed_value_does_not_clear_current_reason_or_evidence(sqlite_engine):
    from backend.manual_evidence_models import ScientificManualEvidence
    ScientificManualEvidence.__table__.create(sqlite_engine, checkfirst=True)
    from backend.ingest import manual_evidence as manual
    factory=sessionmaker(sqlite_engine)
    key="f"*64
    record={"key":key,"item_key":key,"content_hash":"c"*64,"source_hash":"b"*64,"field":"paper.title","current_value":"New","kind":"field"}
    snapshot={"target":"upload","target_id":"fixture","records":[record]}
    with factory.begin() as session:
        session.add(ScientificManualEvidence(id="a"*32,target="upload",target_id="fixture",item_key=key,
          baseline_hash="a"*64,value_hash="a"*64,source_hash="b"*64,before_value="Original",after_value="Old",
          actor_user_id=7,status="draft",reason="Keep this reason",no_evidence_reason="",items=[{"id":"text","kind":"text","text":"Keep this evidence"}]))
    with factory.begin() as session:
        row,_=manual._ensure(session,snapshot,{"records":[]} ,key,7)
        assert row.reason=="Keep this reason" and row.items[0]["text"]=="Keep this evidence"

def test_database_rollback_does_not_publish_failed_draft_or_reason_baseline(target):
    factory,task,user=target
    from backend.services.workdrafts import open_draft
    with factory.begin() as session:
        lease=open_draft(session,'upload',task,user);version=lease.write_epoch+':initial'
    client=tasks.redis_client()
    before=[client.get(key) for key in [tasks.task_key(task),tasks.draft_key(task)]]
    with pytest.raises(RuntimeError):
        with factory.begin() as session:
            save_fields(session,'upload',task,user,version,[{'path':['paper','title'],'before':'Fixture','value':'Failed write'}])
            raise RuntimeError('隔离事务失败')
    assert before==[client.get(key) for key in [tasks.task_key(task),tasks.draft_key(task)]]
    assert tasks.get_draft(task)['paper']['title']=='Fixture'

def test_first_changed_save_keeps_authoritative_body_and_edit_baseline(target):
    factory,task,user=target
    from backend import models
    with factory.begin() as session:
        save_fields(session,'upload',task,user,draft_version(draft()),[
            {'path':['paper','title'],'before':'Fixture','value':'First changed save'}])
    with factory() as session:
        saved=session.get(models.ScientificUploadDraft,task)
        assert saved.draft['paper']['title']=='First changed save'
        assert any(change['after_value']=='First changed save' for change in saved.state['_field_baselines'].values())
    assert tasks.get_state(task)['_field_baselines']


@pytest.fixture
def nullable_structure_merge():
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures/nullable_structure_merge.json").read_text())


def test_real_browser_nullable_structure_merge_preserves_identity_and_neighbours(nullable_structure_merge):
    case = nullable_structure_merge
    original = deepcopy(case["draft"])
    neighbour = deepcopy(draft()["material_states"][0])
    original["material_states"].append(neighbour)
    before = deepcopy(original)
    updated = apply_changes(original, case["changes"])
    assert original == before
    assert len(updated["material_states"]) == 2
    merged = updated["material_states"][0]
    assert merged["state_key"] == before["material_states"][0]["state_key"]
    assert merged["reported_space_group_symbol"] == "Cc"
    assert merged["structure"] == case["changes"][1]["value"]
    assert merged["property_modules"] == before["material_states"][0]["property_modules"]
    assert updated["material_states"][1] == neighbour


def test_nullable_structure_real_save_and_reread(target, nullable_structure_merge):
    from backend.services.workdrafts import open_draft, row
    factory, task, user = target
    value = {**draft(), **deepcopy(nullable_structure_merge["draft"])}
    tasks.redis_client().set(tasks.draft_key(task), json.dumps(value))
    with factory.begin() as session:
        lease = open_draft(session, "upload", task, user)
        version = lease.write_epoch + ":" + draft_version(value)
    with factory.begin() as session:
        result = save_fields(session, "upload", task, user, version, nullable_structure_merge["changes"])
        assert result["changed"]
    with factory() as session:
        body = row(session, "upload", task).body
        assert len(body["material_states"]) == 1
        assert body["material_states"][0]["structure"] == nullable_structure_merge["changes"][1]["value"]
    assert tasks.get_draft(task)["material_states"][0]["reported_space_group_symbol"] == "Cc"


@pytest.mark.parametrize("field", ["pressure_value_gpa", "material", "structure_optimization"])
def test_null_scalar_is_not_promoted_to_object(field):
    from fastapi import HTTPException
    value = {"material_states": [{"state_key": "s", field: None}]}
    with pytest.raises(HTTPException):
        apply_changes(value, [{"path": ["material_states", {"key": "state_key", "value": "s"}, field, "unregistered"], "value": 1}])


@pytest.mark.parametrize("field", ["evidence", "source_associations", "constructor", "unregistered"])
def test_nullable_structure_still_rejects_forbidden_or_unregistered_fields(field):
    from fastapi import HTTPException
    value = {"material_states": [{"state_key": "s", "structure": None}]}
    with pytest.raises(HTTPException):
        apply_changes(value, [{"path": ["material_states", {"key": "state_key", "value": "s"}, "structure", field], "value": "bad"}])
    assert value["material_states"][0]["structure"] is None
