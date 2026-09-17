"""直接在当前 sc-wiki MySQL 运行；所有写入均由外层事务回滚。"""
import asyncio
import copy
import json
import os
import uuid

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend import models
from backend.database import SessionLocal
from backend.ingest import property_evidence as ev

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需要显式选择现有 sc-wiki MySQL')


def test_real_paper29_sources_and_stale_guard():
    with SessionLocal() as s:
        assert s.bind.dialect.name == 'mysql'
        before = ev.paper_snapshot(s,29,0,'',check_access=False)
        records={r['record_id']:r for r in before['records'] if r.get('record_id')}
        assert records
        assert any(r['field'] == 'paper.summary' for r in before['records'])
        assert any('0.12' in c['content'] and '4°' in c['content'] for c in before['chunks'])
        record=s.get(models.PropertyRecord,next(iter(records)))
        record_id=record.id
        old=record.value_raw
        record.value_raw='modified during check'
        s.flush()
        after=ev.paper_snapshot(s,29,0,'',check_access=False)
        assert before['version']!=after['version']
        s.rollback()
        assert s.get(models.PropertyRecord,record_id).value_raw==old


def test_upload_submission_preserves_multievidence_and_local_keys(monkeypatch,tmp_path):
    from backend.api import rag
    from backend.rag import database as asyncdb
    from backend.ingest import upload_tasks
    async def run():
        async with asyncdb.engine.connect() as conn:
            outer=await conn.begin()
            monkeypatch.setattr(asyncdb,'async_session_factory',lambda:AsyncSession(bind=conn,expire_on_commit=False,join_transaction_mode='create_savepoint'))
            try:
                async with AsyncSession(bind=conn,expire_on_commit=False,join_transaction_mode='create_savepoint') as s:
                    p=await s.get(models.Paper,29)
                    before_count=await s.scalar(select(func.count()).select_from(models.Paper))
                    original=rag._artifact_by_paper_id(29,p.upload_task_id)[2]
                    draft=copy.deepcopy(original['user_values'])
                    file=await s.scalar(select(models.PaperFile).where(models.PaperFile.paper_id==29,models.PaperFile.role=='main'))
                    chunks=(await s.scalars(select(models.PaperChunk).where(models.PaperChunk.paper_file_id==file.id).order_by(models.PaperChunk.chunk_index))).all()
                    markdown='\n\n'.join(c.content for c in chunks)
                    task_id=uuid.uuid4().hex
                    path=tmp_path/f'{task_id}.md';path.write_text(markdown)
                    monkeypatch.setattr(upload_tasks,'markdown_path',lambda _:path)
                    draft['paper']['doi']='10.9999/evidence-'+task_id
                    # Sn 与 Pb 同一个局部 record_key；Sn 关联同页多个片段的两条原文。
                    draft['material_states']=draft['material_states'][:2]
                    sources=ev.source_chunks(markdown,'main')
                    checks=[]
                    for si,state in enumerate(draft['material_states']):
                        module=state['property_modules'][0]
                        record=module['records'][0]
                        record['record_key']='same-local-key'
                        old=ev.evidence_list(record)
                        assert old
                        quote=old[0]['quote']
                        located=ev.locate({'quote':quote},sources)
                        assert located,quote
                        record.pop('evidence',None)
                        record['evidences']=[located]
                        if si==0:
                            other=next(c for c in sources if c['chunk_index']!=located['chunk_index'] and len(c['content'])>80)
                            record['evidences'].append(ev.locate({'file_id':'main','chunk_index':other['chunk_index'],'quote':other['content']},sources))
                        from backend.ingest import scientific_evidence as science
                        r = dict(key=f'{si}/{module["module_key"]}/{record["record_key"]}',
                            item_key=science.record_identity(state.get('state_key') or f'state-{si+1}', module['module_key'], record['record_key']),
                            field=f'material_states[{si}].property_modules[0].records[0]', claim=science.record_claim(record,state), evidences=record['evidences'])
                        r = ev.complete_snapshot('upload',task_id,[r],sources,{})['records'][0]
                        checks.append({**r,'status':'uncertain','reason':'持久化回归使用真实原文，未声明科学正确','model':'persistence-test'})
                    state={'user_id':p.uploaded_by_user_id,'files':[{'file_id':'main','role':'main','source_file_path':file.stored_path,'sha256':file.sha256,'size':file.size,'original_filename':file.original_filename}]}
                new_id=await rag._create_pending_paper(task_id,state,draft,evidence_checks=checks)
                async with AsyncSession(bind=conn,expire_on_commit=False,join_transaction_mode='create_savepoint') as s:
                    records=(await s.scalars(select(models.PropertyRecord).where(models.PropertyRecord.paper_id==new_id).order_by(models.PropertyRecord.id))).all()
                    assert len(records)==2
                    assert records[0].record_key==records[1].record_key=='same-local-key'
                    counts=[await s.scalar(select(func.count()).select_from(models.PropertyRecordEvidence).where(models.PropertyRecordEvidence.record_id==r.id)) for r in records]
                    assert counts==[2,1]
                    snapshot=await s.run_sync(lambda sync:ev.paper_snapshot(sync,new_id,0,'',check_access=False))
                    cached=await s.run_sync(lambda sync:ev.cached_results(sync,snapshot))
                    assert len(cached)==2
                    assert all(r['status']=='uncertain' for r in cached.values())
                    assert await s.scalar(select(func.count()).select_from(models.Paper))==before_count+1
            finally:
                await outer.rollback()
        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(models.Paper).where(models.Paper.upload_task_id==task_id))==0
        await asyncdb.engine.dispose()
    asyncio.run(run())
