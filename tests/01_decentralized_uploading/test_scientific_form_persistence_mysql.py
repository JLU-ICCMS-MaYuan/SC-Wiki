"""＃176 真实 MySQL 外层回滚：整理后的多方法及自定义名称通过正式持久化重读。"""
import asyncio
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from backend import models
from backend.database import engine as sync_engine
from backend.ingest.property_modules import persist_property_modules
from backend.api.material_state_export import build_material_state_export
from backend.services.paper_revisions import current_draft
from backend.ingest.scientific_form_filling import apply_plan
from test_scientific_form_filling import fixture, response

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需要显式启用本机回滚验证')


def test_model_groups_other_name_sources_revision_and_export_roundtrip():
    state, sources = fixture()
    plan = response(sources)
    extra = deepcopy(plan['records'][0])
    extra.update(method='custom')
    extra['values'].update(method_code='other', method_raw='User named theory', value_number=240)
    extra['values']['calculation_conditions'] = deepcopy(state['property_modules'][0]['records'][2]['payload']['calculation_conditions'])
    # 此额外点来自原方法说明候选，测试自定义方法保存，不冒充论文提取值。
    extra['candidate_ids']=['s0:m0:r0']
    plan['excluded']=[]
    plan['records'].append(extra)
    filled, _ = apply_plan([state], sources, plan)
    modules = filled[0]['property_modules']
    async def run():
        url = make_url(str(sync_engine.url.render_as_string(hide_password=False))).set(drivername='mysql+asyncmy')
        assert url.host in {'127.0.0.1','localhost','::1'}
        engine = create_async_engine(url)
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint') as db:
                    owner = await db.scalar(select(models.User).limit(1))
                    paper = models.Paper(title='隔离科学表单验证 '+uuid4().hex, year=2026,
                        uploaded_by_user_id=owner.id, review_status='pending', content_revision=1)
                    db.add(paper); await db.flush()
                    material = models.MaterialState(state_key='isolated176', material_name='CaH6',
                        paper_id=paper.id, paper_revision=1, state_kind='theoretical',
                        structure_optimization='classical_static', crystal_system='cubic',
                        material_dimensionality='three_dimensional', pressure_value_gpa=150)
                    db.add(material)
                    file = models.PaperFile(paper_id=paper.id,paper_revision=1,role='main',original_filename='fixture.txt',
                        stored_path='isolated176/'+uuid4().hex,sha256='0'*64,size=0,sort_order=0)
                    db.add(file); await db.flush()
                    chunk = models.PaperChunk(paper_id=paper.id,paper_revision=1,paper_file_id=file.id,
                        chunk_index=0,content=sources[0]['content'])
                    db.add(chunk); await db.flush()
                    evidence = models.PaperEvidence(paper_id=paper.id,paper_revision=1,paper_chunk_id=chunk.id,
                        field_path='value_number',quote=sources[0]['content'])
                    db.add(evidence); await db.flush()
                    incoming = deepcopy(modules)
                    for module in incoming:
                        for record in module['records']:
                            record['evidences']=[{'paper_evidence_id':evidence.id,'field_path':'value_number'}]
                    await persist_property_modules(db,paper_id=paper.id,paper_revision=1,
                        material_state_id=material.id,modules=incoming)
                    await db.flush()
                    exported = await db.run_sync(lambda s: build_material_state_export(
                        s,paper_id=paper.id,state_key=material.state_key,user=SimpleNamespace(id=owner.id,role='user')))
                    actual = exported['property_modules'][0]['records']
                    assert len(actual)==3
                    custom = next(r for r in actual if r['method_code']=='other')
                    assert custom['method_raw']=='User named theory' and custom['evidences']
                    assert len({r['payload']['tc_group']['group_key'] for r in actual})==1
                    reopened = await db.run_sync(lambda s:current_draft(s,s.get(models.Paper,paper.id)))
                    again = reopened['material_states'][0]['property_modules'][0]['records']
                    assert {r['record_key']:r['payload'] for r in again}=={r['record_key']:r['payload'] for r in actual}
                    assert next(r for r in again if r['method_code']=='other')['method_raw']=='User named theory'
            finally:
                await outer.rollback()
        await engine.dispose()
    asyncio.run(run())
