"""真实MySQL回滚，四宿主通过正式字段决定接口确认空值、重读及再次修改失效。"""
import os
from copy import deepcopy
import pytest
from fastapi import HTTPException
from backend.api import evidence as api
from backend.ingest import manual_evidence as manual,field_source_metadata as meta,scientific_evidence as science
from test_sidebar_field_review_mysql import context
from test_scientific_evidence_mysql import current_mysql

pytestmark=pytest.mark.skipif(os.environ.get("SCWIKI_CURRENT_MYSQL")!="1",reason="显式MySQL回滚")


def test_empty_confirmation_api_reopen_and_material_change(context,monkeypatch):
    actor,target,tid,draft,narrow,snapshot,mutate,factory=context
    current,_=snapshot()
    row=next(r for r in current["records"] if r["field"]=="material_states[0].structure_families")
    one={**current,"records":[row]}
    monkeypatch.setattr("backend.rag.llm.complete_json",lambda *a,**k:(_ for _ in ()).throw(AssertionError("不应调用模型")))
    with factory.begin() as db:
        manual.save_explanation(db,one,{"records":[]},row["item_key"],actor.id,reason="暂不分类",
            no_evidence_reason="无合适分类依据",text_items=[])
    view=api.field_detail(target,tid,row["item_key"],user=actor)
    assert view["can_confirm_empty"]
    result=api.save_field_decision(api.FieldDecision(target=target,target_id=tid,item_key=row["item_key"],
        action="approve_without_evidence",review_token=view["review_token"]),actor)
    assert result["record"]["field_decision"]["mode"]=="without_evidence"
    assert result["record"]["human_confirmed"] and result["record"]["status"]=="supported"
    reopened=api.field_detail(target,tid,row["item_key"],user=actor)
    assert reopened["record"]["human_confirmed"] and reopened["approval_state"]=="human_approved"
    current,cached=snapshot()
    r=next(r for r in current["records"] if r["item_key"]==row["item_key"])
    from backend.ingest.field_review import blocking
    assert not blocking(r,cached[r["key"]])
    with factory.begin() as db:
        manual.save_explanation(db,{**current,"records":[r]},{"records":[]},r["item_key"],actor.id,
            reason="新的留空说明",no_evidence_reason="",text_items=[{"text":"保留可选空值的原文依据","source_description":"隔离资料"}])
    invalid=api.field_detail(target,tid,row["item_key"],user=actor)
    assert not invalid["record"]["human_confirmed"]
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target=target,target_id=tid,item_key=row["item_key"],
            action="approve_without_evidence",review_token=reopened["review_token"]),actor)


def test_empty_confirmation_does_not_expand_actor_permissions(context):
    from types import SimpleNamespace
    actor,target,tid,draft,narrow,snapshot,mutate,factory=context
    current,_=snapshot()
    row=next(r for r in current["records"] if r["field"]=="material_states[0].structure_families")
    view=api.field_detail(target,tid,row["item_key"],user=actor)
    other=SimpleNamespace(id=actor.id+999999,role=actor.role,username="unrelated")
    with pytest.raises(HTTPException):
        api.save_field_decision(api.FieldDecision(target=target,target_id=tid,item_key=row["item_key"],
            action="approve_without_evidence",review_token=view["review_token"]),other)
