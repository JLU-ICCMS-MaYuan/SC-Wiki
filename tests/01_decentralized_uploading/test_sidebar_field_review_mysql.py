"""＃177：真实 MySQL 外层回滚，保存当前字段并验证背景变化与真实依据冲突。"""
from contextlib import nullcontext
from copy import deepcopy
import json
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from backend import models
from backend.api import evidence as api
from backend.ingest import property_evidence as ev, scientific_evidence as science, field_drafts, field_review
from backend.ingest import manual_evidence as manual, field_input, field_source_metadata as meta, upload_tasks
from test_scientific_evidence_mysql import current_mysql
from test_evidence_progress import progress_redis

pytestmark=pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL')!='1',reason='需要显式本机回滚测试')


@pytest.fixture(params=['upload','revision','admin','superadmin'])
def context(request,current_mysql,monkeypatch):
    role=request.param
    with current_mysql.begin() as db:
        owner=models.User(username='f177'+uuid4().hex[:12],email=uuid4().hex+'@field177.invalid',
                          password_hash='isolated',real_name='隔离验证',role='user',is_approved=True)
        db.add(owner);db.flush()
        actor=owner
        if role in {'admin','superadmin'}:
            actor=models.User(username='a177'+uuid4().hex[:12],email=uuid4().hex+'@field177.invalid',
                              password_hash='isolated',real_name='隔离验证',role=role,is_approved=True)
            db.add(actor);db.flush()
        paper=models.Paper(title='Field isolation',year=2026,uploaded_by_user_id=owner.id,
                           review_status='rejected' if role=='revision' else 'pending',content_revision=1)
        db.add(paper);db.flush()
        target='upload' if role=='upload' else 'revision' if role=='revision' else 'paper'
        target_id=str(paper.id) if target=='paper' else uuid4().hex
        draft={'paper':{'title':'Field isolation','year':2026},'material_states':[{
            'state_key':'s','material':'CaH6','state_kind':'theoretical','pressure_value_gpa':150,
            'structure_optimization':'classical_static','property_modules':[{'module_key':'m',
            'module_code':'superconductive_properties','definition_key':'module.superconductive_properties','definition_version':1,
            'records':[{'record_key':'r','module_code':'superconductive_properties','record_type':'predicted_tc',
                'property_code':'tc','definition_key':'record.superconductive_properties.predicted_tc.isotropic_eliashberg',
                'definition_version':1,'method_code':'isotropic_eliashberg','name_raw':'Tc',
                'value_kind':'number','value_number':220,'value_raw':'220 K',
                'payload':{'parameters':{'mu_star':.12},'calculation_conditions':{}}}]}]}]}
        task_state={'user_id':actor.id,'stage':'ready','status':'ready','files':[]}
        if target=='upload':
            db.add(models.ScientificUploadDraft(task_id=target_id,owner_id=actor.id,state=task_state,draft=draft))
        elif target=='revision':
            db.add(models.PaperRevisionDraft(paper_id=paper.id,owner_id=actor.id,revision_id=target_id,
                base_revision=1,base_fingerprint='a'*64,draft_version=1,draft=draft))
        else:
            db.add(models.ScientificReviewDraft(paper_id=paper.id,owner_id=actor.id,base_revision=1,base_fingerprint='a'*64,draft=draft))
        db.flush()
    monkeypatch.setattr('backend.database.SessionLocal',current_mysql)
    monkeypatch.setattr(api,'SessionLocal',current_mysql)
    monkeypatch.setattr(field_drafts,'target_lock',lambda *a:nullcontext())
    monkeypatch.setattr(upload_tasks,'get_state',lambda _:deepcopy(task_state))
    monkeypatch.setattr(upload_tasks,'get_draft',lambda _:deepcopy(draft))
    monkeypatch.setattr(api,'get_state',lambda _:deepcopy(task_state))
    def mutate(fn):
        fn(draft)
        with current_mysql.begin() as db:
            if target=='upload':
                row=db.get(models.ScientificUploadDraft,target_id)
            elif target=='revision':
                row=db.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id==target_id))
                row.draft_version+=1
            else:row=db.get(models.ScientificReviewDraft,int(target_id))
            row.draft=deepcopy(draft)
    def snapshot(*args):
        with current_mysql() as db:
            current,_=field_drafts.authorized_draft(db,target,target_id,actor)
            snap=ev.complete_snapshot(target,target_id,ev.draft_records(current,{}),
                [{'file_id':'main','chunk_index':0,'content':'The authors use mu = 0.12 at 150 GPa.'}],current)
            if target=='paper':snap['review_state']=[paper.review_status,str(paper.reviewed_at),paper.content_revision]
            field_review.bind_support_versions(snap,db)
            return snap,science.load_results(db,snap,actor.id,include_stale=True)
    monkeypatch.setattr(api,'snapshot_for',snapshot)
    snap,_=snapshot()
    record=next(r for r in snap['records'] if r.get('record_field')=='payload.parameters.mu_star')
    narrow=field_input.select_field(snap,record['item_key'])
    with current_mysql.begin() as db:
        meta.remember(db,snap,actor.id)
        manual.save_explanation(db,narrow,{'records':[]},record['item_key'],actor.id,
            reason='最新理由',no_evidence_reason='沿用原文',text_items=[])
    snap,_=snapshot();narrow=field_input.select_field(snap,record['item_key'])
    narrow['field_review_input']=field_input.binding(narrow)
    return actor,target,target_id,draft,narrow,snapshot,mutate,current_mysql


@pytest.mark.parametrize('status',['supported','unsupported'])
def test_field_result_roundtrip_ignores_background_only_and_rejects_real_changes(context,status,monkeypatch):
    actor,target,tid,draft,snap,snapshot,mutate,factory=context
    record=snap['records'][0]
    results={record['key']:{'status':status,'reason':'针对本次字段的模型判断','model':'isolated',
                            'review_started_at':'2026-10-29T11:00:00+00:00','evidences':[]}}
    with factory() as db:
        assert manual.review_context(db,snap)[record['item_key']]['decisions'][0]['reason']=='最新理由'
    old_background=deepcopy(snap['field_review_input']['background'])
    mutate(lambda d:d['material_states'][0].update(pressure_value_gpa=175))
    ev.persist_completed_results(snap,results,actor.id)
    current,cached=snapshot()
    r=next(r for r in current['records'] if r['item_key']==record['item_key'])
    assert cached[r['key']]['status']==status and not cached[r['key']]['stale']
    assert field_review.reusable(r,cached[r['key']])
    assert field_review.blocking(r,cached[r['key']])==(status!='supported')
    assert cached[r['key']]['field_review_binding']['background']==old_background
    monkeypatch.setattr(ev,'read_job_status',lambda *a:{'id':'job','status':'completed'})
    monkeypatch.setattr(ev,'read_job',lambda *a:{'snapshot':snap,'results':results})
    response=api.get_job('job',actor)
    assert len(response['records'])==1
    assert response['records'][0]['item_key']==record['item_key']
    assert response['records'][0]['status']==status
    summary=api.field_summary(api.Target(target=target,target_id=tid),actor)
    shown=next(r for r in summary['records'] if r['item_key']==record['item_key'])
    assert shown['status']==status and not shown['pending_review']
    with monkeypatch.context() as missing_metadata:
        missing_metadata.setattr(meta,'read',lambda *a:None)
        unavailable=api.field_summary(api.Target(target=target,target_id=tid),actor)
        assert next(r for r in unavailable['records'] if r['item_key']==record['item_key'])['pending_review']
    detail=api.field_detail(target,tid,record['item_key'],user=actor)
    assert detail['record']['status']==status and not detail['record']['stale']
    if status=='supported':
        result=api.enqueue_review(api.Target(target=target,target_id=tid,purpose='submit',
            expected_version=current['version']),actor,{**current,'records':[r]},cached)
        assert result['status']=='completed'
    with factory() as db:
        rows=list(db.scalars(select(models.ScientificEvidenceCheck).where(models.ScientificEvidenceCheck.target==target,
                  models.ScientificEvidenceCheck.target_id==tid,models.ScientificEvidenceCheck.item_key!=meta.KEY)))
        assert len(rows)==1 and rows[0].item_key==record['item_key']
        assert rows[0].result['field_review_binding']['background']==old_background
    # 无关修改没有写科学值；真正当前字段变化仍拒绝迟到回答。
    assert draft['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters']['mu_star']==.12
    mutate(lambda d:d['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters'].update(mu_star=.14))
    with pytest.raises(HTTPException):
        ev.persist_completed_results(snap,results,actor.id)
    with pytest.raises(HTTPException):
        api.get_job('job',actor)


@pytest.mark.parametrize('change',['reason','absence','attachment'])
def test_changed_manual_reason_and_deleted_target_reject_old_result(context,change):
    actor,target,tid,draft,snap,snapshot,mutate,factory=context
    record=snap['records'][0]
    with factory.begin() as db:
        row=manual._current(db,snap,record,for_update=True)
        if change=='reason':row.reason='更新后的理由'
        elif change=='absence':row.no_evidence_reason='更新后的缺证原因'
        else:row.items=[{'id':'new-file','kind':'text','text':'new','sha256':'b'*64,'source_description':'新增依据'}]
    with pytest.raises(HTTPException):
        ev.persist_completed_results(snap,{record['key']:{'status':'supported'}},actor.id)
    mutate(lambda d:d['material_states'][0]['property_modules'][0].update(records=[]))
    with pytest.raises(HTTPException):
        ev.persist_completed_results(snap,{record['key']:{'status':'supported'}},actor.id)


def test_newer_field_result_and_cancellation_are_not_overwritten(context,monkeypatch):
    actor,target,tid,draft,old,snapshot,mutate,factory=context
    record=old['records'][0]
    mutate(lambda d:d['material_states'][0].update(pressure_value_gpa=175))
    current,_=snapshot();current=field_input.select_field(current,record['item_key'])
    current['field_review_input']=field_input.binding(current)
    newest={record['key']:{'status':'unsupported','reason':'较新结果','model':'isolated','review_started_at':'2026-10-29T12:00:00+00:00'}}
    ev.persist_completed_results(current,newest,actor.id)
    late={record['key']:{'status':'supported','reason':'迟到结果','model':'isolated','review_started_at':'2026-10-29T11:00:00+00:00'}}
    ev.persist_completed_results(old,late,actor.id)
    assert late[record['key']]['reason']=='较新结果'
    old['field_review_job_id']='cancelled-job'
    monkeypatch.setattr(ev,'read_job_status',lambda *a:{'status':'cancelled'})
    with pytest.raises(InterruptedError):
        ev.persist_completed_results(old,late,actor.id)


def test_scoped_manual_file_save_survives_unrelated_background(context,monkeypatch,tmp_path):
    import asyncio
    from io import BytesIO
    from types import SimpleNamespace
    from starlette.datastructures import UploadFile
    actor,target,tid,draft,snap,snapshot,mutate,factory=context
    record=snap['records'][0]
    # 仅本测试的临时文件存储，数据库仍由外层事务回滚。
    monkeypatch.setenv('FILE_STORAGE_BACKEND','local')
    monkeypatch.setattr(manual,'settings',SimpleNamespace(sc_wiki_data_dir=tmp_path))
    prepared=api.manual_context(target,tid,record['item_key'],actor,field_scope=True)
    mutate(lambda d:d['material_states'][0].update(pressure_value_gpa=175))
    upload=UploadFile(filename='evidence.txt',file=BytesIO(b'Additional source explanation.'))
    result=asyncio.run(api.post_manual_evidence_file(target,tid,record['item_key'],
        expected_version=prepared['version'],source_description='原文说明',file=upload,user=actor))
    assert result['data']['items'][0]['kind']=='text_file'
    reopened=api.get_manual_evidence(target,tid,record['item_key'],actor,field_scope=True)
    assert reopened['data']['items'][0]['id']==result['data']['items'][0]['id']
    # 新附件是当前字段依据的真实变化，旧核对不能借背景隔离继续通过。
    with pytest.raises(HTTPException):
        ev.persist_completed_results(snap,{record['key']:{'status':'supported'}},actor.id)


@pytest.mark.parametrize('outcome',['supported','unsupported','timeout'])
def test_worker_result_is_persisted_and_returned_for_only_one_field(context,progress_redis,monkeypatch,outcome):
    from types import SimpleNamespace
    from backend.rag.llm_context import LlmConfig
    actor,target,tid,draft,snap,snapshot,mutate,factory=context
    record=snap['records'][0]
    config=LlmConfig('openai','https://model.invalid','isolated','not-a-real-key',True)
    monkeypatch.setattr(api,'redis_client',lambda:progress_redis)
    monkeypatch.setattr(upload_tasks,'redis_client',lambda:progress_redis)
    monkeypatch.setattr(api,'get_llm_config',lambda:config)
    monkeypatch.setattr(api,'save_llm_config',lambda *a:None)
    monkeypatch.setattr(api,'upload_queue',lambda:SimpleNamespace(enqueue=lambda *a,**kw:None))
    monkeypatch.setattr(upload_tasks,'load_llm_config',lambda *a:config)
    monkeypatch.setattr(upload_tasks,'delete_llm_config',lambda *a:None)
    def evaluate(records,chunks,*args,**kwargs):
        assert len(records)==1 and records[0]['item_key']==record['item_key']
        if outcome=='timeout':raise TimeoutError('isolated timeout')
        return [ev.checked_result(records[0],{'status':outcome,'reason':'固定模型结果',
            'evidences':[{'file_id':'main','chunk_index':0,'quote':chunks[0]['content']}]},chunks)]
    monkeypatch.setattr(ev,'evaluate_batch',evaluate)
    result=api.create_job(api.Target(target=target,target_id=tid,purpose='field',
        expected_field_token=snap['field_review_input']['token'],retry_keys=[record['key']]),actor)
    ev.run_evidence_job(result['id'])
    job=ev.read_job(result['id'],actor.id)
    if outcome=='timeout':
        assert job['status']=='failed' and job['error']['code']=='evidence_model_timeout'
    else:
        assert job['status']=='completed',job.get('error')
        response=api.get_job(result['id'],actor)
        assert len(response['records'])==1
        assert response['records'][0]['item_key']==record['item_key']
        assert response['records'][0]['status']==outcome
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(models.ScientificEvidenceCheck).where(
            models.ScientificEvidenceCheck.target==target,models.ScientificEvidenceCheck.target_id==tid,
            models.ScientificEvidenceCheck.item_key==record['item_key']))==(0 if outcome=='timeout' else 1)


def test_revoked_permission_does_not_save_result(context,monkeypatch):
    actor,target,tid,draft,snap,snapshot,mutate,factory=context
    record=snap['records'][0]
    if target=='upload':
        monkeypatch.setattr(upload_tasks,'get_state',lambda _: {'user_id':actor.id+99999,'stage':'ready'})
    else:
        with factory.begin() as db:
            if target=='paper':
                db.get(models.User,actor.id).role='user'
            else:
                row=db.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id==tid))
                db.get(models.Paper,row.paper_id).review_status='approved'
    with pytest.raises(HTTPException):
        ev.persist_completed_results(snap,{record['key']:{'status':'supported'}},actor.id)
