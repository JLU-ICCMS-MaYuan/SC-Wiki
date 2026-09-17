"""现有 MySQL 上验证持久核对；所有测试写入由外层事务回滚。"""
import copy
import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend import models
from backend.database import engine
from backend.ingest import property_evidence as ev, scientific_evidence as science

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需要显式选择当前 MySQL')


@pytest.fixture
def current_mysql():
    with engine.connect() as connection:
        assert connection.dialect.name == 'mysql'
        outer = connection.begin()
        try:
            yield sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
        finally:
            outer.rollback()


def snapshot():
    records = [dict(key=key, item_key=science.item_identity(key), field=f'paper.{key}', label=key,
                    claim={'value': value}, evidences=[]) for key, value in [('summary', 'Tc 10 K'), ('key_finding', 'Tc 20 K')]]
    return ev.complete_snapshot('upload', uuid.uuid4().hex, records,
        [dict(file_id='main', chunk_index=0, content='The critical temperature is 10 K.')], {})


def test_unchecked_draft_and_human_confirmation_without_quote(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    snap = snapshot()
    snap['target'] = 'paper'
    snap['target_id'] = str(uuid.uuid4().int % 1000000000 + 1000000000)
    record = snap['records'][0]
    with current_mysql.begin() as session:
        proposals.save_draft(session, snap, 7, record['key'], {}, False, '专业判断的草稿')
    with current_mysql.begin() as session:
        cached = science.load_results(session, snap, 7)
        assert ev.public_snapshot(snap, cached)['records'][0]['status'] == 'unchecked'
        assert cached[record['key']]['proposal_draft']['reason'] == '专业判断的草稿'
        with pytest.raises(HTTPException):
            proposals.save_draft(session, snap, 7, record['key'], {}, True, '')
        proposals.save_draft(session, snap, 7, record['key'], {}, True, '根据明确的物理定义人工确认；论文未直接表述')
        prepared = proposals.prepare(session, snap, 7)
        proposals.finalize(session, snap, 7, prepared['preparation_id'])
        result = ev.public_snapshot(snap, science.load_results(session, snap, 7))['records'][0]
        assert result['human_confirmed'] is True
        assert result['source_kind'] == 'human_review'
        assert result['status'] == 'unchecked'
        assert result['evidences'] == []
        assert result['decision']['ai_status'] == 'unchecked'
        from backend.rag.scientific_sources import source_chunk
        chunk = source_chunk(SimpleNamespace(id=123, paper_id=123, paper_revision=1, field_path=record['field'], result=result))
        assert chunk['source_kind'] == 'human_review'
        assert '论文未直接支持' in chunk['attribution']
        assert '根据明确的物理定义' in chunk['attribution']
        changed = copy.deepcopy(record)
        changed['content_hash'] = 'concurrent-change'
        assert not ev.checked_result(changed, result, snap['chunks'])['human_confirmed']


def test_uploader_cannot_confirm_unchecked_without_source(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    snap = snapshot()
    with current_mysql.begin() as session:
        proposals.save_draft(session, snap, 7, snap['records'][0]['key'], {}, False, '')
        with pytest.raises(HTTPException):
            proposals.save_draft(session, snap, 7, snap['records'][0]['key'], {}, True, '上传者坚持是正确的')


def test_decimal_manual_confirmation_preserves_exact_claim_after_reload(current_mysql):
    from decimal import Decimal
    from backend.ingest import evidence_proposals as proposals
    snap = snapshot(); snap['target'] = 'paper'; snap['target_id'] = str(uuid.uuid4().int % 1000000000 + 1000000000)
    record = snap['records'][0]
    record.update(kind='field', current_value=Decimal('0.0001010000'), claim={'value':Decimal('0.0001010000')})
    snap = ev.complete_snapshot(snap['target'], snap['target_id'], snap['records'], snap['chunks'], {})
    with current_mysql.begin() as session:
        proposals.save_draft(session, snap, 7, record['key'], {}, True, '根据压力条件人工确认')
        prepared = proposals.prepare(session, snap, 7)
    with current_mysql.begin() as session:
        proposals.finalize(session, snap, 7, prepared['preparation_id'])
        assert ev.public_snapshot(snap, science.load_results(session, snap, 7))['records'][0]['human_confirmed']


def test_human_confirmation_real_endpoints_permissions_and_prepare(current_mysql, monkeypatch):
    from backend.api import evidence
    from backend.ingest import evidence_proposals as proposals
    with current_mysql.begin() as session:
        users = list(session.scalars(select(models.User).where(models.User.account_status == 'active').limit(2)))
        uploader, reviewer = users
        paper = models.Paper(title='人工确认回滚验收', year=2026, review_status='pending', content_revision=1,
                             uploaded_by_user_id=uploader.id, summary='根据专业定义可推得的结论')
        session.add(paper); session.flush()
        paper_id = paper.id
        snap = ev.paper_snapshot(session, paper_id, reviewer.id, 'admin')
    monkeypatch.setattr(evidence, 'SessionLocal', current_mysql)
    actor = SimpleNamespace(id=reviewer.id, role='admin')
    request = evidence.ProposalDraft(target='paper', target_id=str(paper_id), expected_version=snap['version'],
                                    key=snap['records'][0]['key'], accepted=True, reason='按定义和适用条件人工确认')
    for forbidden in [SimpleNamespace(id=uploader.id, role='admin'), SimpleNamespace(id=reviewer.id, role='user')]:
        with pytest.raises(HTTPException) as error:
            evidence.save_proposal(request, forbidden)
        assert error.value.status_code == 403
    evidence.save_proposal(request, actor)
    prepared = evidence.prepare_proposals(request, actor)
    evidence.finalize_proposals(evidence.ProposalFinalization(target='paper', target_id=str(paper_id), preparation_id=prepared['preparation_id']), actor)
    reviewed = evidence.prepare_review(evidence.PrepareReview(paper_id=paper_id, expected_version=snap['version']), actor)
    result = reviewed['records'][0]
    assert result['human_confirmed'] and result['source_kind'] == 'human_review'
    assert result['resolution'] == request.reason
    assert result['evidences'] == []
    request.expected_version = 'old'
    with pytest.raises(HTTPException): evidence.save_proposal(request, actor)


def test_missing_and_reasons_survive_new_session_and_local_invalidation(current_mysql):
    snap = snapshot()
    results = {r['key']: dict(status='missing', reason='论文没有支持', suggestion='检查温度含义', evidences=[]) for r in snap['records']}
    with current_mysql() as session, session.begin():
        science.save_results(session, snap, results, 1)
        science.save_resolutions(session, snap, 7, {'summary':'审核员独立草稿'})
    with current_mysql() as session:
        restored = science.load_results(session, snap, 7)
        assert len(restored) == 2
        assert restored['summary']['resolution'] == '审核员独立草稿'
        assert restored['summary']['suggestion'] == '检查温度含义'
        assert science.load_results(session, snap, 8)['summary']['resolution'] == ''
        changed = copy.deepcopy(snap['records'])
        changed[0]['claim']['value'] = 'Tc 11 K'
        newer = ev.complete_snapshot('upload', snap['target_id'], changed, snap['chunks'], {})
        assert set(science.load_results(session, newer)) == {'key_finding'}
        assert science.load_results(session, newer, include_stale=True)['summary']['stale']
        with pytest.raises(HTTPException) as error:
            science.save_resolutions(session, newer, 7, {'summary':'不能裁决旧数据'})
        assert error.value.detail['code'] == 'evidence_stale'


def test_upload_snapshot_is_durable_and_explicit_delete_cleans_it(current_mysql):
    snap = snapshot()
    with current_mysql() as session, session.begin():
        science.save_results(session, snap, {'summary':dict(status='missing',reason='未找到',evidences=[])}, 1)
        science.persist_upload(session, snap['target_id'], {'user_id':1, 'cleanup_at':123}, {'paper':{'summary':'Tc 10 K'}})
    with current_mysql() as session, session.begin():
        saved = session.get(models.ScientificUploadDraft, snap['target_id'])
        assert saved.state['cleanup_at'] is None
        assert saved.draft['paper']['summary'] == 'Tc 10 K'
        assert science.has_upload_checks(session, snap['target_id'])
        science.delete_target(session, 'upload', snap['target_id'])
    with current_mysql() as session:
        assert session.get(models.ScientificUploadDraft, snap['target_id']) is None
        assert not science.has_upload_checks(session, snap['target_id'])


def test_real_prepare_without_properties_checks_summary_permissions_and_reasons(current_mysql, monkeypatch):
    from backend.api import evidence
    identifier = uuid.uuid4().hex
    with current_mysql() as session, session.begin():
        users = list(session.scalars(select(models.User).where(models.User.account_status == 'active').limit(3)))
        uploader, reviewer = users[:2]
        paper = models.Paper(title='来源审核事务回归', year=2026, review_status='pending',
                             content_revision=1, uploaded_by_user_id=uploader.id, summary='Tc is 10 K')
        session.add(paper); session.flush()
        file = models.PaperFile(paper_id=paper.id,paper_revision=1,role='main',original_filename=identifier+'.txt',stored_path='test/'+identifier,sha256='a'*64,size=30,sort_order=0)
        session.add(file); session.flush()
        chunk = models.PaperChunk(paper_id=paper.id,paper_revision=1,paper_file_id=file.id,chunk_index=0,content='The critical temperature is 10 K.',token_count=9)
        session.add(chunk); session.flush()
        snap = ev.paper_snapshot(session,paper.id,reviewer.id,'admin')
        assert len(snap['records']) == 1
        row = snap['records'][0]
        result = dict(status='uncertain',reason='需要确认温度定义',suggestion='核对转变判据',evidences=[{'file_id':str(file.id),'chunk_index':0,'quote':chunk.content}])
        science.save_results(session,snap,{row['key']:result},reviewer.id)
        paper_id=paper.id
        actor=SimpleNamespace(id=reviewer.id,role='admin')
    monkeypatch.setattr(evidence, 'SessionLocal', current_mysql)
    request=evidence.PrepareReview(paper_id=paper_id,expected_version=snap['version'])
    with pytest.raises(HTTPException) as error:
        evidence.prepare_review(request, actor)
    assert error.value.detail['code']=='evidence_review_required'
    request.resolutions={row['key']:'已检查原文的转变定义'}
    prepared=evidence.prepare_review(request,actor)
    assert prepared['records'][0]['resolution']=='已检查原文的转变定义'
    assert prepared['records'][0]['evidences'][0]['chunk_id']==chunk.id
    request.expected_version='old'
    with pytest.raises(HTTPException) as error:
        evidence.prepare_review(request,actor)
    assert error.value.detail['code']=='evidence_stale'
    with current_mysql() as session:
        with pytest.raises(HTTPException) as error:
            ev.paper_snapshot(session,paper_id,uploader.id,'admin')
        assert error.value.status_code==403
        with pytest.raises(HTTPException):
            ev.paper_snapshot(session,paper_id,reviewer.id,'user')


def test_permanent_rag_source_preserves_contributor_attribution(current_mysql):
    from backend.rag.scientific_sources import source_chunk, citation
    with current_mysql() as session, session.begin():
        paper = session.scalar(select(models.Paper).limit(1))
        source = models.ScientificEvidenceSource(paper_id=paper.id,paper_revision=paper.content_revision,
            item_key=uuid.uuid4().hex,field_path='structure',content_hash='a'*64,source_hash='b'*64,rule_version=ev.RULE_VERSION,
            result={'label':'晶格参数','current_value':{'a':3},'evidences':[], 'resolution':'确认附件来源',
                    'provenance':{'kind':'contributor_structure','submitted_by_name':'实际提供者','filename':'sample.cif'}})
        session.add(source); session.flush()
        chunk=source_chunk(source)
        assert chunk['source_kind']=='contributor_structure'
        assert '论文中未提供明确支持' in chunk['content']
        assert '实际提供者' in chunk['content']
        assert citation(chunk)['attribution']==chunk['attribution']


def test_real_redis_loss_restores_latest_lifecycle_from_mysql(current_mysql, monkeypatch):
    from backend import database
    from backend.ingest import upload_tasks
    monkeypatch.setattr(database, "SessionLocal", current_mysql)
    task_id = uuid.uuid4().hex
    client = upload_tasks.redis_client()
    state = {"task_id": task_id, "user_id": 1, "status": "ready", "updated_at": 1}
    try:
        with current_mysql.begin() as session:
            science.persist_upload(session, task_id, state, {"paper": {"summary": "可恢复草稿"}})
        science.persist_upload_state(task_id, {**state, "status": "cancelled", "updated_at": 2})
        assert upload_tasks.get_state(task_id)["status"] == "cancelled"
        assert upload_tasks.get_draft(task_id)["paper"]["summary"] == "可恢复草稿"
        client.delete(upload_tasks.task_key(task_id), upload_tasks.draft_key(task_id))
        science.restore_user_uploads(1)
        assert upload_tasks.get_state(task_id)["updated_at"] == 2
    finally:
        client.delete(upload_tasks.task_key(task_id), upload_tasks.draft_key(task_id))
        client.zrem(upload_tasks.user_tasks_key(1), task_id)


def test_worker_failure_keeps_completed_group_in_mysql(current_mysql, monkeypatch):
    import json
    from backend import database
    from backend.ingest import upload_tasks
    from backend.rag import llm
    monkeypatch.setattr(database, "SessionLocal", current_mysql)
    records = [dict(key=f"checkpoint-{uuid.uuid4().hex}", field=f"paper.test{i}", label=f"测试项{i}", claim={"value":i}, evidences=[]) for i in range(9)]
    snap = ev.complete_snapshot("paper", "29", records, [{"file_id":"test", "chunk_index":0,"content":"测试来源"}], {})
    with current_mysql() as session:
        paper = session.get(models.Paper, 29)
        snap["review_state"] = [paper.review_status, str(paper.reviewed_at), paper.content_revision]
    job = dict(id="checkpoint", owner=1, status="queued", cached={}, snapshot=snap)
    class RedisStub:
        def get(self, _key): return json.dumps(job)
        def setex(self, *_args): pass
    monkeypatch.setattr(upload_tasks, "redis_client", RedisStub)
    monkeypatch.setattr(upload_tasks, "load_llm_config", lambda _id: SimpleNamespace(model="test"))
    monkeypatch.setattr(upload_tasks, "delete_llm_config", lambda _id: None)
    monkeypatch.setattr(ev, "read_job", lambda *_args: job)
    monkeypatch.setattr(ev, "update_job", lambda _id, **changes: job.update(changes))
    calls = []
    def model(_system, prompt, **kwargs):
        batch = json.loads(prompt)["records"]
        calls.append(batch)
        if len(calls) == 2:
            raise ValueError("第二组模拟失败")
        return {"results":[{"key":r["key"],"status":"missing","reason":"找不到出处","suggestion":"补充原始数据","evidences":[]} for r in batch]}
    monkeypatch.setattr(llm, "complete_json", model)
    ev.run_evidence_job("checkpoint")
    assert job["status"] == "failed"
    with current_mysql() as session:
        saved = science.load_results(session, snap)
    assert len(saved) == 8
    assert all(r["status"] == "missing" and r["suggestion"] == "补充原始数据" for r in saved.values())


def test_structure_origin_uses_real_file_and_keeps_first_submitter(current_mysql):
    from backend.services.structure_candidates import build_structure_candidate
    with current_mysql() as session:
        structure = session.scalar(select(models.StructureModel).where(models.StructureModel.paper_id == 29))
        users = list(session.scalars(select(models.User).where(models.User.account_status == "active").limit(2)))
        raw = structure.structure_text.encode("utf-8")
        candidate = build_structure_candidate(structure_format=structure.structure_format, structure_text=structure.structure_text,
            source={"file_id":"original","filename":"original.cif","role":"attachment"}, material_state_ref="material_states[0]")
    target = uuid.uuid4().hex
    with current_mysql.begin() as session:
        science.register_structure_origin(session,"upload",target,candidate,users[0].id,users[0].username,"original.cif",raw)
        science.register_structure_origin(session,"upload",target,candidate,users[1].id,users[1].username,"later.cif",raw)
    with current_mysql() as session:
        origins = science.origins_for(session,"upload",target)
        assert len(origins) == 1
        origin = next(iter(origins.values()))
        assert origin["submitted_by_user_id"] == users[0].id
        assert origin["filename"] == "original.cif"
        assert origin["original_text"] == raw.decode()
        assert origin["paper_supported"] is False
        text, _ = __import__("backend.ingest.scientific_drafts", fromlist=["_candidate_conventional_representation"])._candidate_conventional_representation(candidate)
        row = science.structure_record({"structure_format":"cif","structure_text":text}, "Sn", "structure", origin)
        checked = ev.checked_result(row, {"status":"missing"}, [])
        assert checked["status"] == "uncertain"
        assert checked["source_kind"] == "contributor_structure"
        unknown = science.structure_record({"structure_format":"cif","structure_text":text}, "Sn", "structure")
        assert ev.checked_result(unknown,{"status":"supported"},[])["status"] == "missing"


def test_proposal_draft_restore_bind_and_retry_without_model(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    snap = snapshot(); snap['target'] = 'paper'; snap['target_id'] = str(uuid.uuid4().int % 1000000000 + 1000000000)
    row = snap['records'][0]; row.update(kind='field', current_value='Tc 10 K')
    source = {'file_id':'main','chunk_index':0,'quote':'The critical temperature is 10 K.'}
    result = {'status':'unsupported','reason':'原值措辞不准确','evidences':[source],
              'proposal':{'values':{'':'临界温度为 10 K'},'supported':True,'evidences':[source]}}
    with current_mysql.begin() as session:
        science.save_results(session,snap,{row['key']:result},1)
        draft = proposals.save_draft(session,snap,7,row['key'],{'':'临界温度为 10 K'},True,'')
        assert draft['accepted'] and draft['supported']
    with current_mysql.begin() as session:
        assert science.load_results(session,snap,7)[row['key']]['proposal_draft']['accepted']
        assert science.load_results(session,snap,8)[row['key']]['proposal_draft'] is None
        prepared = proposals.prepare(session,snap,7)
        assert len(prepared['patches']) == 1
        proposals.validate_save(session,snap,7,prepared['preparation_id'],'paper')
        with pytest.raises(HTTPException): proposals.validate_save(session,snap,8,prepared['preparation_id'],'paper')
        # 未保存不能绑定，失败保留完整接受草稿。
        with pytest.raises(HTTPException): proposals.finalize(session,snap,7,prepared['preparation_id'])
        assert science.load_results(session,snap,7)[row['key']]['proposal_draft']['accepted']
    changed = copy.deepcopy(snap)
    changed['records'][0]['claim'] = proposals.expected_claim(row,{'':'临界温度为 10 K'})
    changed['records'][0]['current_value'] = '临界温度为 10 K'
    changed = ev.complete_snapshot(snap['target'],snap['target_id'],changed['records'],snap['chunks'],{})
    with current_mysql.begin() as session:
        proposals.finalize(session,changed,7,prepared['preparation_id'])
        proposals.finalize(session,changed,7,prepared['preparation_id'])
        bound = science.load_results(session,changed,7)[row['key']]
        assert bound['status'] == 'supported'
        assert bound['decision']['ai_status'] == 'unsupported'
        assert bound['decision']['final_value'] == '临界温度为 10 K'
        # 迟到模型任务不能抹掉人工决定。
        science.save_results(session,changed,{row['key']:{'status':'missing','evidences':[]}},1)
        assert science.load_results(session,changed,7)[row['key']]['decision']


def test_proposal_missing_manual_reason_revoke_and_concurrent_source(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    snap = snapshot(); snap['target']='paper'; snap['target_id']=str(uuid.uuid4().int % 1000000000 + 1000000000); row=snap['records'][0];row.update(kind='field',current_value='Tc 10 K')
    source={'file_id':'main','chunk_index':0,'quote':'The critical temperature is 10 K.'}
    with current_mysql.begin() as session:
        science.save_results(session,snap,{row['key']:{'status':'missing','evidences':[]}},1)
        with pytest.raises(HTTPException) as error: proposals.save_draft(session,snap,7,row['key'],{},True,'')
        assert error.value.detail['code']=='evidence_review_required'
        # 编辑草稿允许缺证保存，接受时才检查门禁。
        proposals.save_draft(session,snap,7,row['key'],{'':'修改草稿'},False,'')
        # 重查替身只改变测试持久结果，保留草稿。
        saved = proposals.rows_for(session,snap)[0]
        saved.result={**saved.result,'status':'uncertain','evidences':[source]};session.flush()
        with pytest.raises(HTTPException) as error: proposals.save_draft(session,snap,7,row['key'],{'':'人工改写'},True,'')
        assert error.value.detail['code']=='evidence_review_required'
        proposals.save_draft(session,snap,7,row['key'],{'':'人工改写'},True,'对照原文确认')
        prepared=proposals.prepare(session,snap,7)
        newer=copy.deepcopy(snap);newer['records'][0]['source_hash']='changed-source'
        with pytest.raises(HTTPException): proposals.validate_save(session,newer,7,prepared['preparation_id'],'paper')
        proposals.save_draft(session,snap,7,row['key'],{'':'人工改写'},False,'对照原文确认')
        assert not proposals.prepare(session,snap,7)['patches']
        with pytest.raises(HTTPException): proposals.finalize(session,snap,7,prepared['preparation_id'])


def test_proposal_two_phase_failure_resumes_without_overwriting_metadata(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    snap=snapshot();snap['target']='paper';snap['target_id']=str(uuid.uuid4().int % 1000000000 + 1000000000)
    for index, row in enumerate(snap['records']):
        row.update(kind='field',current_value=row['claim']['value'])
        if index: row.update(field='material_states[0].note',state_key='sample')
    source={'file_id':'main','chunk_index':0,'quote':'The critical temperature is 10 K.'}
    with current_mysql.begin() as session:
        science.save_results(session,snap,{r['key']:{'status':'uncertain','evidences':[source]} for r in snap['records']},1)
        for row in snap['records']: proposals.save_draft(session,snap,7,row['key'],{'':'人工确认 10 K'},True,'核对原文测量条件')
        prepared=proposals.prepare(session,snap,7)
    middle=copy.deepcopy(snap)
    middle['records'][0]['claim']['value']='人工确认 10 K'
    middle['records'][0]['current_value']='人工确认 10 K'
    middle=ev.complete_snapshot(snap['target'],snap['target_id'],middle['records'],snap['chunks'],{})
    with current_mysql.begin() as session:
        resumed=proposals.prepare(session,middle,7)
        assert resumed['preparation_id']==prepared['preparation_id']
        assert resumed['resume_stage']=='scientific'
        proposals.validate_save(session,middle,7,resumed['preparation_id'],'scientific')
        with pytest.raises(HTTPException): proposals.validate_save(session,middle,7,resumed['preparation_id'],'paper')
        with pytest.raises(HTTPException): proposals.finalize(session,middle,7,resumed['preparation_id'])
    final=copy.deepcopy(middle)
    final['records'][1]['claim']['value']='人工确认 10 K';final['records'][1]['current_value']='人工确认 10 K'
    final=ev.complete_snapshot(snap['target'],snap['target_id'],final['records'],snap['chunks'],{})
    with current_mysql.begin() as session:
        assert proposals.prepare(session,final,7)['resume_stage']=='finalize'
        proposals.finalize(session,final,7,prepared['preparation_id'])
    with current_mysql() as session:
        assert all(r['resolution']=='核对原文测量条件' for r in science.load_results(session,final,7).values())
        assert all(not r['resolution'] for r in science.load_results(session,final,8).values())


def test_proposal_reuses_current_record_definition_validation(current_mysql):
    from backend.ingest import evidence_proposals as proposals
    with current_mysql() as session:
        snap = ev.paper_snapshot(session,29,0,'',check_access=False)
        record = next(r for r in snap['records'] if r.get('kind')=='property' and r['claim']['record']['value_kind']=='number')
        proposals.validate_domain_values(session,record,{'value_raw':record['claim']['record']['value_raw']})
        with pytest.raises(HTTPException) as error:
            proposals.validate_domain_values(session,record,{'value_min':100,'value_max':1})
        assert error.value.detail['code']=='evidence_proposal_invalid'
