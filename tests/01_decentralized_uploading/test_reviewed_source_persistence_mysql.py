"""真实返修持久化验证，所有新记录均在外层MySQL事务回滚。"""
import asyncio
import hashlib
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式选择本机回滚测试')


def test_revision_keeps_reviewed_reference_without_matching_text(tmp_path, monkeypatch):
    from backend.rag import llm
    monkeypatch.setattr(llm, 'complete_json', lambda *a, **kw: pytest.fail('返修提交不能新增模型调用'))
    asyncio.run(revision_roundtrip(tmp_path))


async def revision_roundtrip(tmp_path):
    from backend import models
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    from backend.ingest.scientific_drafts import persist_scientific_draft
    from backend.rag.database import database_url
    from backend.services import paper_revisions as revisions
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            try:
                async with factory() as db:
                    owner = await db.scalar(select(models.User).where(models.User.account_status == 'active'))
                    actor = SimpleNamespace(id=owner.id, username=owner.username, role='user')
                    family = await db.scalar(select(models.MaterialFamily))
                    paper = models.Paper(title='Isolated reviewed source', year=2026, paper_type='experimental',
                        superconductor_kind='unknown', review_status='rejected', content_revision=1, uploaded_by_user_id=actor.id)
                    db.add(paper); await db.flush()
                    paper_id = paper.id
                    db.add(models.PaperMaterialFamily(paper_id=paper.id, paper_revision=1, material_family_id=family.id))
                    raw = 'The critical temperature is 10 <!-- block: source --> K.'
                    path = tmp_path / 'source.md'; path.write_text(raw)
                    file = models.PaperFile(paper_id=paper.id, paper_revision=1, role='main', original_filename='source.md',
                        stored_path=str(path), size=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    db.add(file); await db.flush()
                    chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=file.id,
                        chunk_index=0, content=raw)
                    db.add(chunk); await db.flush()
                    quote = {'file_id': str(file.id), 'chunk_id': chunk.id, 'chunk_index': 0,
                             'quote': 'The critical temperature is 10 K.'}
                    draft = {'paper': {'superconductor_kind': 'unknown'}, 'material_states': [{
                        'state_key': 'isolated-state', 'material': 'Si', 'material_name': 'Silicon',
                        'state_kind': 'experimental', 'structure_optimization': 'unknown', 'element_count': 1,
                        'property_modules': [{'module_key': 'tc-module', 'module_code': 'superconductive_properties',
                            'records': [{'record_key': 'tc-1', 'record_type': 'measured_tc', 'property_code': 'tc',
                                'definition_key': 'record.superconductive_properties.measured_tc.resistivity', 'definition_version': 1,
                                'name_raw': 'Tc', 'value_kind': 'number', 'value_raw': '10 K', 'value_number': 10,
                                'canonical_unit': 'K', 'method_code': 'resistivity',
                                'payload': {'experimental_conditions': {'applied_field_t': 0}}, 'evidences': [quote]}]}]}]}
                    targets = await persist_scientific_draft(db, paper, draft)
                    await ev.persist_existing_paper_targets(db, paper, targets, reviewed=True)
                    assert await db.scalar(select(models.PaperEvidence.quote).where(models.PaperEvidence.paper_id == paper.id)) == quote['quote']
                    opened = await revisions.open_draft(db, paper.id, actor, create=True)
                    saved = await db.get(models.PaperRevisionDraft, paper.id)
                    snapshot = await db.run_sync(lambda s: revisions.revision_snapshot(s, saved.revision_id, actor.id))
                    # 只预置当前版本的科学结果，真实来源解析和全部持久化仍走生产路径。
                    await db.run_sync(lambda s: science.save_results(s, snapshot, {r['key']: {
                        'status': 'supported', 'reason': '隔离测试预置已完成审核', 'evidences': [quote]}
                        for r in snapshot['records']}, actor.id))
                    result = await revisions.submit_draft(db, paper.id, actor, SimpleNamespace(
                        revision_id=opened['revision_id'], draft_version=opened['draft_version'],
                        evidence_job_id=None, expected_evidence_version=snapshot['version']))
                    assert result['review_status'] == 'pending' and result['content_revision'] == 2
                    await db.commit()
                async with factory() as reader:
                    paper = await reader.get(models.Paper, paper_id)
                    assert paper.content_revision == 2 and paper.review_status == 'pending'
                    quotes = (await reader.scalars(select(models.PaperEvidence.quote).where(models.PaperEvidence.paper_id == paper_id))).all()
                    assert quote['quote'] in quotes
                    assert await reader.scalar(select(models.PropertyRecordEvidence.paper_evidence_id).where(
                        models.PropertyRecordEvidence.paper_id == paper_id)) is not None
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()
