"""仅在显式隔离MySQL验证子项身份、旧结论不授信与事件幂等。"""
import os
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy.engine import make_url
from backend import models
from backend.database import SessionLocal
from backend.ingest import property_evidence as ev, scientific_evidence as science
from test_issue139_scientific_context import draft
from backend.tests.test_paper_revisions import workflow

pytestmark = pytest.mark.skipif(not os.environ.get('SCWIKI_ISSUE139_TEST_DATABASE_URL'), reason='需要显式隔离MySQL')


def test_field_cache_legacy_history_audit_idempotency_and_dependency():
    assert (make_url(os.environ['SCWIKI_ISSUE139_TEST_DATABASE_URL']).database or '').startswith('scwiki_issue139_test_')
    task = uuid4().hex
    d = draft()
    chunks = [{'file_id':'main','chunk_index':0,'page_start':1,'content':'lambda 3.94; Tc is 281 to 311 K at 150 GPa.'}]
    def snap(value):return ev.complete_snapshot('upload',task,ev.draft_records(value,{}),chunks,value)
    current = snap(d)
    leaf = next(r for r in current['records']if r.get('record_field')=='payload.parameters.lambda_ep')
    with SessionLocal.begin() as db:
        owner = models.User(username='audit'+task[:12],real_name='审计姓名快照',email=task+'@field-review.invalid',password_hash='isolated-only',role='user',is_approved=True)
        db.add(owner);db.flush();uid=owner.id
        db.add(models.ScientificUploadDraft(task_id=task,owner_id=uid,draft=d,state={}))
        legacy = next(r for r in ev.draft_records(d,{})if r['kind']=='property')
        legacy.update(content_hash=ev.digest(science.canonical(legacy['claim'])),source_hash=leaf['source_hash'],current_value=legacy['claim'])
        old = {**current,'records':[legacy]}
        science.save_results(db,old,{legacy['key']:{'status':'supported','model':'old-model','reason':'旧整条已核对','evidences':[]}},uid)
    with SessionLocal.begin() as db:
        found = science.load_results(db,current,uid)
        assert found[leaf['key']]['status']=='unchecked'
        assert found[leaf['key']]['history'][0]['legacy_scope']=='record'
        assert not found[leaf['key']].get('audit_events')
        response={'status':'supported','model':'actual-review-test-model','reason':'对照lambda原句','evidences':[{'file_id':'main','chunk_index':0,'quote':'lambda 3.94'}],
                  '_audit_action':'ai_review','_audit_event_id':'job-1'}
        for _ in range(2):science.save_results(db,current,{leaf['key']:deepcopy(response)},uid)
    with SessionLocal.begin() as db:
        first=science.load_results(db,current,uid)[leaf['key']]
        assert len(first['audit_events'])==1
        assert first['audit_events'][0]['actor']['kind']=='ai'
        assert first['audit_events'][0]['occurred_at'].endswith('+00:00')
        response['_audit_event_id']='job-2'
        science.save_results(db,current,{leaf['key']:response},uid)
    with SessionLocal() as db:
        original=science.load_results(db,current,uid)[leaf['key']]
        assert len(original['audit_events'])==2
        changed=deepcopy(d);changed['material_states'][0]['property_modules'][0]['records'][0]['payload']['parameters']['mu_star']=.16
        after=snap(changed)
        intact=next(r for r in after['records']if r.get('record_field')=='payload.parameters.lambda_ep')
        assert intact['content_hash']==leaf['content_hash']
        assert science.load_results(db,after,uid)[intact['key']]['status']=='supported'
        target=next(r for r in after['records']if r.get('record_field')=='value_min')
        assert science.load_results(db,after,uid)[target['key']]['status']=='unchecked'
        moved=science.transfer_result(leaf,original,chunks)
        assert moved['audit_events']==original['audit_events']
        from backend.ingest.evidence_audit import draft_change_events
        events=draft_change_events(d,changed,db.get(models.User,uid))
        after['_field_change_events']=events
        public=ev.public_snapshot(after,science.load_results(db,after,uid))
        mu=next(x for x in public['records']if 'mu_star' in x.get('record_field','') and x['audit_events'])
        assert mu['status']=='unchecked'
        assert mu['audit_events'][0]['actor']['user_id']==uid
        assert mu['audit_events'][0]['after_value']==.16
        assert not any(e['kind']=='field_change'for e in science.load_results(db,after,uid)[intact['key']]['audit_events'])


def test_native_scalar_proposal_rejects_unapplied_change_and_records_human_review():
    assert (make_url(os.environ['SCWIKI_ISSUE139_TEST_DATABASE_URL']).database or '').startswith('scwiki_issue139_test_')
    import json
    from pathlib import Path
    from backend.ingest import evidence_proposals as proposals
    from backend.ingest.form_definitions import definition_checksum
    from backend.ingest.property_field_review import write_path
    task=uuid4().hex;d=draft();r=d['material_states'][0]['property_modules'][0]['records'][0]
    r.update(definition_key='record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version=1)
    chunks=[{'file_id':'main','chunk_index':0,'content':'lambda 3.94; another phase lambda 3.95.'}]
    def snap(value):return ev.complete_snapshot('upload',task,ev.draft_records(value,{}),chunks,value)
    current=snap(d);field=next(x for x in current['records']if x.get('record_field')=='payload.parameters.lambda_ep')
    with SessionLocal.begin()as db:
        owner=models.User(username='prepare'+task[:10],real_name='实际保存人',email=task+'@field-review.invalid',password_hash='isolated-only',role='user',is_approved=True)
        db.add(owner);db.flush();uid=owner.id
        db.add(models.ScientificUploadDraft(task_id=task,owner_id=uid,draft=d,state={}))
        seed=next(s for s in json.loads((Path(__file__).parents[2]/'backend/data/form_definitions.v1.json').read_text())if s.get('record_type')=='predicted_tc')
        seed={**seed,'definition_key':r['definition_key'],'method_code':'isotropic_eliashberg'}
        if not db.query(models.FormDefinition).filter_by(definition_key=r['definition_key'],version=1).first():db.add(models.FormDefinition(**seed,checksum=definition_checksum(seed)))
        evidence=[{'file_id':'main','chunk_index':0,'quote':'lambda 3.94'}]
        result={'status':'uncertain','reason':'修正行需要核对适用范围','evidences':evidence,'proposal':{'values':{'':3.94},'basis_kind':'paper_inference','explanation':'修正行与当前材料同属一个表格，适用范围待人工核对','evidences':evidence,'supported':False}}
        science.save_results(db,current,{field['key']:result},uid)
    with SessionLocal.begin()as db:
        proposals.save_draft(db,current,uid,field['key'],{'':3.95},True,'按修正行采用，保留推断来源')
        with pytest.raises(Exception) as blocked:
            proposals.prepare(db,current,uid)
        assert blocked.value.status_code == 409
        proposals.save_draft(db,current,uid,field['key'],{'':3.94},True,'按当前字段核对，保留推断来源')
        prepared=proposals.prepare(db,current,uid)
        assert prepared['patches'][0]['record_field']=='payload.parameters.lambda_ep'
        modified=deepcopy(d);write_path(modified['material_states'][0]['property_modules'][0]['records'][0],'payload.parameters.lambda_ep',3.94)
        updated=snap(modified)
        proposals.finalize(db,updated,uid,prepared['preparation_id'])
    with SessionLocal()as db:
        checked=next(x for x in updated['records']if x.get('record_field')=='payload.parameters.lambda_ep')
        saved=science.load_results(db,updated,uid)[checked['key']]
        assert saved['status']=='uncertain' and saved['adopted_basis']=='paper_inference'
        event=saved['audit_events'][0]
        assert event['actor']['name']=='实际保存人'
        assert event['occurred_at'].endswith('+00:00')
        assert event['kind']=='human_review'
        assert 'before_value' not in event


def test_logged_in_revision_saves_server_audit_and_rejects_forged_events(workflow):
    w=workflow
    opened=w.client.post(w.base).json()
    value=deepcopy(opened['data']);value['paper']['title']='真实返修保存'
    value['_field_change_events']=[{'id':'forged','actor':{'name':'冒名'}}]
    response=w.client.put(w.base,json={'revision_id':opened['revision_id'],'draft_version':opened['draft_version'],'draft':value})
    assert response.status_code==200,response.text
    saved=response.json();events=saved['data']['_field_change_events']
    event=next(e for e in events if e['field']=='paper.title')
    assert event['actor']=={'kind':'human','user_id':w.owner.id,'name':w.owner.username}
    assert (event['before_value'],event['after_value'])==('Rejected paper','真实返修保存')
    assert not any(e['id']=='forged'for e in events)
    preflight=w.client.post('/api/rag/evidence/preflight',json={'target':'revision','target_id':saved['revision_id']})
    assert preflight.status_code==200,preflight.text
    title=next(r for r in preflight.json()['records']if r['field']=='paper.title')
    assert title['audit_events']==[event] and title['status']=='unchecked'
    again=w.client.put(w.base,json={'revision_id':saved['revision_id'],'draft_version':saved['draft_version'],'draft':saved['data']})
    assert again.status_code==200 and again.json()['draft_version']==saved['draft_version']
    stale=w.client.put(w.base,json={'revision_id':opened['revision_id'],'draft_version':opened['draft_version'],'draft':value})
    assert stale.status_code==409


def test_admin_saved_field_history_uses_authenticated_editor(workflow):
    w=workflow
    with w.factory.begin()as session:
        session.get(models.Paper,w.paper.id).review_status='pending'
    w.client.headers['Authorization']='Bearer '+w.other_token
    value={'paper_type':'review','material_families':[{'name':'历史验收'+uuid4().hex,'status':'pending'}],
           'material_states':[{'state_key':'s','material':'LaSc2H24','pressure_value_gpa':150,'property_modules':[]}],
           'structure_candidates':[]}
    url=f'/api/rag/papers/{w.paper.id}/scientific-draft'
    first=w.client.put(url,json=value)
    assert first.status_code==200,first.text
    value['material_states'][0]['pressure_value_gpa']=2
    response=w.client.put(url,json=value)
    assert response.status_code==200,response.text
    with w.factory()as session:
        snap=ev.paper_snapshot(session,w.paper.id,w.other.id,'superadmin',check_access=False)
        result=ev.public_snapshot(snap,science.load_results(session,snap,w.other.id))
        pressure=next(r for r in result['records']if r['field'].endswith('.pressure_value_gpa'))
        event=next(e for e in pressure['audit_events']if e['kind']=='field_change'and str(e['before_value'])=='150')
        assert event['actor']=={'kind':'human','user_id':w.other.id,'name':w.other.username}
        assert str(event['before_value'])=='150' and str(event['after_value'])=='2'
        assert event['occurred_at'].endswith('+00:00')
