"""只允许隔离 MySQL：正式提交、返修读取、证据与导出均走实际服务。"""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select,func

from backend import models
from backend.database import SessionLocal
from backend.rag.database import async_session_factory
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.scientific_context import apply_associations,scientific_fingerprint
from backend.ingest.form_definitions import definition_checksum
from test_issue139_scientific_context import draft,context,candidate

pytestmark=pytest.mark.skipif(not os.environ.get('SCWIKI_ISSUE139_TEST_DATABASE_URL'),reason='需要显式隔离 MySQL')


def ensure_isolated():
    from sqlalchemy.engine import make_url
    urls=[SessionLocal.kw['bind'].url,async_session_factory.kw['bind'].url]
    assert all('mysql' in u.drivername and (u.database or '').startswith('scwiki_issue139_test_') for u in urls)
    assert urls[0].database==urls[1].database and urls[0].host==urls[1].host
    assert make_url(os.environ['SCWIKI_ISSUE139_TEST_DATABASE_URL']).database==urls[0].database


def test_mysql_draft_submission_revision_evidence_export_and_permission(tmp_path,monkeypatch):
    ensure_isolated()
    from backend.api import rag
    from backend.api.material_state_export import build_material_state_export
    from backend.ingest import upload_tasks
    from backend.services import paper_revisions as revisions
    from backend.services.scientific_draft_rewrite import bump_paper_revision,delete_scientific_entities
    from backend.ingest.scientific_drafts import persist_scientific_draft
    suffix=uuid.uuid4().hex
    d=draft()
    r=d['material_states'][0]['property_modules'][0]['records'][0]
    r.update(definition_key='record.superconductive_properties.predicted_tc.isotropic_eliashberg',definition_version=1)
    m=d['material_states'][0]['property_modules'][0]
    m.update(definition_key='module.superconductive_properties',definition_version=1)
    d['material_states'][0].update(state_kind='theoretical',material_dimensionality='unknown',crystal_system='unknown')
    d['paper']={'title':'Issue139 隔离持久化 '+suffix,'year':2026,'paper_type':'theoretical','superconductor_kind':'conventional',
                'doi':'10.9999/issue139-'+suffix,'authors':['Test Author'],'theoretical_subtype':'calculation',
                'material_families':[{'name':'隔离家族'+suffix[:8],'status':'pending'}]}
    sources=context()
    sources['sources'][0]['source_sha256']='0'*64
    applied,gaps=apply_associations(d,[candidate(d)],sources)
    assert len(applied)==1 and not gaps
    text=sources['sources'][0]['content']+' Tc is 281 to 311 K at 150 GPa.'
    path=tmp_path/'paper.md';path.write_text(text)
    r['evidences']=[{'file_id':'main','chunk_index':0,'quote':'Tc is 281 to 311 K at 150 GPa.'}]
    monkeypatch.setattr(upload_tasks,'markdown_path',lambda _:path)
    with SessionLocal.begin() as db:
        user=models.User(username='i139'+suffix[:12],email=suffix+'@issue139.invalid',real_name='隔离验收',
                         password_hash='test-only',role='user',is_approved=True)
        db.add(user);db.flush();uid=user.id
        seeds=json.loads((Path(__file__).parents[2]/'backend/data/form_definitions.v1.json').read_text())
        prediction=deepcopy(next(s for s in seeds if s.get('method_code')=='allen_dynes'))
        prediction.update(definition_key=r['definition_key'],method_code='isotropic_eliashberg')
        for seed in [*seeds,prediction]:
            if not db.scalar(select(models.FormDefinition.id).where(models.FormDefinition.definition_key==seed['definition_key'],models.FormDefinition.version==seed['version'])):
                db.add(models.FormDefinition(**seed,checksum=definition_checksum(seed)))
        state={'task_id':suffix,'user_id':uid,'parser_profile':'legacy','files':[{'file_id':'main','role':'main',
            'source_file_path':str(path),'original_filename':'paper.md','sha256':'0'*64,'size':len(text)}]}
        science.persist_upload(db,suffix,state,d)
    with SessionLocal() as db:
        saved=db.get(models.ScientificUploadDraft,suffix)
        assert saved.draft['material_states'][0]['property_modules'][0]['records'][0]['payload']==r['payload']
    async def exercise():
        pid=await rag._create_pending_paper(suffix,state,d)
        with SessionLocal() as db:
            paper=db.get(models.Paper,pid)
            owner=db.get(models.User,uid)
            result=build_material_state_export(db,paper_id=pid,state_key='s',user=owner)
            exported=result['property_modules'][0]['records'][0]
            assert exported['payload']['parameters']['lambda_ep']==3.94
            assert exported['payload']['calculation_conditions']['k_grid']=='24×24×24'
            file_id=str(db.scalar(select(models.PaperFile.id).where(models.PaperFile.paper_id==pid)))
            association=exported['payload']['source_associations'][0]
            assert association['fact_evidences'][0]['file_id']==file_id
            assert association['target_fingerprint']==scientific_fingerprint(exported)
            snap=ev.paper_snapshot(db,pid,uid,'user',check_access=False)
            prop=next(row for row in snap['records'] if row.get('kind')=='property')
            assert not prop['source_associations'][0]['stale']
            checked=ev.checked_result(prop,{'status':'supported','evidences':prop['evidences']},snap['chunks'])
            assert checked['status']=='uncertain'
            science.save_results(db,snap,{prop['key']:checked},uid);db.commit()
            assert science.load_results(db,snap,uid)[prop['key']]['status']=='uncertain'
            with pytest.raises(Exception) as forbidden:
                build_material_state_export(db,paper_id=pid,state_key='s',user=None)
            assert forbidden.value.status_code==403
            revision=revisions.current_draft(db,paper)
            rr=revision['material_states'][0]['property_modules'][0]['records'][0]
            assert rr['payload']==exported['payload']
            assert db.scalar(select(func.count()).select_from(models.PropertyRecord).where(models.PropertyRecord.paper_id==pid))==1
        # 真实并发修订条件：旧 ORM 版本不能再次递增当前论文。
        async with async_session_factory() as session:
            async with session.begin():
                current=await session.get(models.Paper,pid)
                stale=models.Paper(id=pid,content_revision=current.content_revision)
                # 遵循真实返修顺序：先删除旧科学图，再升版并重建；不能绕过复合外键。
                await delete_scientific_entities(session,pid)
                await bump_paper_revision(session,current)
                targets=await persist_scientific_draft(session,current,revision)
                await ev.persist_existing_paper_targets(session,current,targets)
                with pytest.raises(RuntimeError,match='版本'):
                    await bump_paper_revision(session,stale)
        with SessionLocal() as db:
            paper=db.get(models.Paper,pid)
            assert paper.content_revision==2
            result=build_material_state_export(db,paper_id=pid,state_key='s',user=db.get(models.User,uid))
            assert result['property_modules'][0]['records'][0]['payload']==exported['payload']
        await async_session_factory.kw['bind'].dispose()
    asyncio.run(exercise())


def test_mysql_large_source_metadata_reads_latest_checks_without_sorting_json():
    ensure_isolated()
    from sqlalchemy import text
    from backend.ingest import evidence_proposals
    task=uuid.uuid4().hex
    def snapshot(version):
        records=[{'key':str(i),'item_key':science.item_identity('large',str(i)),
            'field':'paper.summary','claim':{'value':version},'current_value':version,'label':'large sources'} for i in range(8)]
        return ev.complete_snapshot('upload',task,records,[{'file_id':'main','chunk_index':0,'content':'original source'}],{})
    bulky={'source_associations':[{'fact_evidences':[{'quote':'original Methods source '*1000}]} for _ in range(12)]}
    with SessionLocal.begin() as db:
        original=db.scalar(text('SELECT @@SESSION.sort_buffer_size'))
        try:
            db.execute(text('SET SESSION sort_buffer_size=32768'))
            for version in (1,2):
                snap=snapshot(version)
                science.save_results(db,snap,{r['key']:{'status':'uncertain','reason':'存储压力测试，不作为科学判断',
                    'current_value':bulky} for r in snap['records']},1)
                db.flush()
            loaded=science.load_results(db,snap,1)
            assert len(loaded)==8 and all(not r.get('stale') for r in loaded.values())
            ordered=evidence_proposals.rows_for(db,snap,lock=True)
            assert len(ordered)==16 and [r.id for r in ordered]==sorted(r.id for r in ordered)
        finally:
            db.execute(text('SET SESSION sort_buffer_size='+str(int(original))))
