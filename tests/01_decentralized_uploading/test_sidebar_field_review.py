"""＃177 复用真实摘要／任务构造，验证字段范围与全局版本分离。"""
import json
from copy import deepcopy
import pytest
from fastapi import HTTPException
from backend.api import evidence as api
from backend.ingest import field_drafts
from test_field_review_start import review_api


def test_field_start_ignores_unrelated_draft_change_but_rejects_current_change(review_api):
    draft,user,queued,snapshot=review_api
    record=next(r for r in snapshot()[0]['records'] if r['field']=='paper.title')
    prepared=api.field_input_context('upload','task',record['item_key'],user)
    draft['paper']['year']=2027
    body=api.Target(target='upload',target_id='task',purpose='field',
                    retry_keys=[record['key']],expected_field_token=prepared['field_token'])
    api.create_job(body,user)
    job=json.loads(queued[0][2])
    assert len(job['snapshot']['records'])==1
    assert job['snapshot']['field_review_input']['token']==prepared['field_token']
    assert 'draft_version_token' not in job['snapshot']
    draft['paper']['title']='new value'
    with pytest.raises(HTTPException):
        api.create_job(body,user)
    assert len(queued)==1


def test_field_save_uses_before_value_without_relaxing_normal_save(review_api,monkeypatch):
    draft,user,_,_=review_api
    saved=[]
    from backend.ingest import upload_tasks
    monkeypatch.setattr(upload_tasks,'save_draft',lambda _,value,**kw:saved.append(value))
    version=field_drafts.draft_version(draft)
    draft['paper']['year']=2027
    changes=[{'path':['paper','title'],'before':'LaScH','value':'new'}]
    with api.SessionLocal() as session:
        with pytest.raises(HTTPException):
            field_drafts.save_fields(session,'upload','task',user,version,changes)
        field_drafts.save_fields(session,'upload','task',user,version,changes,field_scope=True)
        assert saved[0]['paper']=={'title':'new','year':2027}
        with pytest.raises(HTTPException):
            field_drafts.save_fields(session,'upload','task',user,version,
                [{'path':['paper','title'],'before':'wrong','value':'x'}],field_scope=True)


def test_new_token_cannot_change_other_entry_contract_or_select_multiple_fields(review_api):
    draft,user,queued,snapshot=review_api
    record=next(r for r in snapshot()[0]['records'] if r['field']=='paper.title')
    prepared=api.field_input_context('upload','task',record['item_key'],user)
    for purpose,keys in [('submit',[record['key']]),('field',[]),('field',[record['key'],'other'])]:
        with pytest.raises(HTTPException):
            api.create_job(api.Target(target='upload',target_id='task',purpose=purpose,retry_keys=keys,
                expected_field_token=prepared['field_token']),user)
    assert not queued
