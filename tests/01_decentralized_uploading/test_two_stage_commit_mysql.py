"""真实MySQL事务：批准与暂存值应用必须一起成功或一起回滚。"""
import os
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend import models
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest.field_drafts import authorized_draft, draft_version, save_fields

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式启用MySQL回滚测试')


@pytest.mark.parametrize('passed', [True, False])
def test_admin_review_atomic_application_and_blocking(passed):
    asyncio.run(review_case(passed))


async def review_case(passed):
    from backend.rag.database import engine
    from backend.services.field_review_commit import commit_review
    from backend.api.evidence import FieldReviewCommit
    from backend.ingest.field_review import bind_support_versions
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint') as db:
                users = list((await db.scalars(select(models.User).where(models.User.account_status == 'active').limit(2))).all())
                family = await db.scalar(select(models.MaterialFamily).limit(1))
                assert family is not None and len(users) == 2
                actor = SimpleNamespace(id=users[1].id, username=users[1].username, role='admin')
                paper = models.Paper(title='Before review', year=2026, paper_type='review', superconductor_kind='unknown',
                    review_status='pending', content_revision=1, uploaded_by_user_id=users[0].id)
                db.add(paper); await db.flush()
                db.add(models.PaperMaterialFamily(paper_id=paper.id, paper_revision=1, material_family_id=family.id))
                await db.flush()
                target_id = str(paper.id)
                draft, _ = await db.run_sync(lambda s: authorized_draft(s, 'paper', target_id, actor))
                await db.run_sync(lambda s: save_fields(s, 'paper', target_id, actor, draft_version(draft), [
                    {'path': ['paper', 'title'], 'before': 'Before review', 'value': 'After review'}]))
                staged = await db.get(models.ScientificReviewDraft, paper.id)
                formal = await db.run_sync(lambda s: ev.paper_snapshot(s, paper.id, actor.id, actor.role))
                snap = {**formal, **ev.complete_snapshot('paper', target_id,
                    ev.draft_records(staged.draft, {}), formal['chunks'], staged.draft)}
                snap['_field_change_events'] = staged.draft.get('_field_change_events') or []
                await db.run_sync(lambda s: bind_support_versions(snap, s))
                checks = {r['key']: {'status': 'unsupported' if not passed and r['field'] == 'paper.title' else 'supported',
                                    'reason': '隔离测试预置的核对结果', 'source_kind': 'paper_quote'} for r in snap['records']}
                await db.run_sync(lambda s: science.save_results(s, snap, checks, actor.id))
                request = FieldReviewCommit(paper_id=paper.id, expected_evidence_version=snap['version'])
                if not passed:
                    with pytest.raises(Exception) as failure:
                        await commit_review(db, request, actor)
                    assert failure.value.detail['code'] == 'evidence_review_required'
                    await db.refresh(paper)
                    assert paper.title == 'Before review' and paper.review_status == 'pending'
                    assert (await db.get(models.ScientificReviewDraft, paper.id)).draft['paper']['title'] == 'After review'
                else:
                    result = await commit_review(db, request, actor)
                    assert result['review_status'] == 'approved'
                    await db.refresh(paper)
                    assert paper.title == 'After review' and paper.approved_revision == paper.content_revision
                    assert await db.get(models.ScientificReviewDraft, paper.id) is None
                    assert await db.scalar(select(models.ScientificEvidenceSource.id).where(models.ScientificEvidenceSource.paper_id == paper.id))
        finally:
            await transaction.rollback()
    await engine.dispose()
