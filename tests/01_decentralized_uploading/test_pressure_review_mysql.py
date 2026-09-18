"""压强修改、清空、重载与人工确认；现有 MySQL 外层事务全部回滚。"""
import asyncio
import copy
import os
import uuid

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend import models
from backend.database import DATABASE_URL
from backend.ingest import property_evidence as ev, scientific_evidence as science, evidence_proposals as proposals

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需显式选择当前 MySQL 回滚验证')


def test_pressure_rewrite_confirm_and_clear_are_versioned_and_reloadable():
    from backend.api.rag import _rewrite_paper_scientific_draft_in_tx

    async def run():
        engine = create_async_engine(DATABASE_URL.replace('mysql+pymysql://', 'mysql+asyncmy://'))
        try:
            async with engine.connect() as connection:
                outer = await connection.begin()
                try:
                    async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint') as session:
                        users = list((await session.scalars(select(models.User).where(models.User.account_status == 'active').limit(2))).all())
                        uploader, reviewer = users
                        family = await session.scalar(select(models.MaterialFamily).limit(1))
                        paper = models.Paper(title='压强回滚验收 ' + uuid.uuid4().hex, year=2026, paper_type='experimental',
                                             review_status='pending', content_revision=1, uploaded_by_user_id=uploader.id,
                                             authors=['test'], journal='test', abstract='test', summary='test', superconductor_kind='conventional')
                        session.add(paper)
                        await session.flush()
                        pid = paper.id
                        pressure_fields = ('pressure_value_gpa', 'pressure_raw', 'pressure_unit_raw', 'pressure_min_gpa', 'pressure_max_gpa')
                        state = dict(state_key='tin', material='Sn', element_count=1, material_dimensionality='three_dimensional',
                                     crystal_system='tetragonal', state_kind='experimental', property_modules=[], structure_families=[],
                                     pressure_value_gpa=0.000101, pressure_raw='0.000101', pressure_unit_raw='GPa', pressure_min_gpa=0.0001, pressure_max_gpa=0.0002)
                        payload = dict(paper_type='experimental', superconductor_kind='conventional',
                                       material_families=[dict(id=family.id, name=family.name_zh, status='confirmed')],
                                       material_states=[state], structure_candidates=[])
                        await _rewrite_paper_scientific_draft_in_tx(session, pid, copy.deepcopy(payload), reviewer)
                        snap = await session.run_sync(lambda s: ev.paper_snapshot(s, pid, reviewer.id, 'admin'))
                        pressure = next(r for r in snap['records'] if r['field'].endswith('.pressure_value_gpa'))
                        await session.run_sync(lambda s: science.save_results(s, snap, {pressure['key']:{'status':'unsupported', 'reason':'旧值没有原文支持', 'evidences':[]}}, reviewer.id))
                        await session.run_sync(lambda s: proposals.save_draft(s, snap, reviewer.id, pressure['key'], {}, True, '旧压力理由'))

                        state['pressure_value_gpa'] = 0.002
                        await _rewrite_paper_scientific_draft_in_tx(session, pid, copy.deepcopy(payload), reviewer)
                        newer = await session.run_sync(lambda s: ev.paper_snapshot(s, pid, reviewer.id, 'admin'))
                        assert newer['version'] != snap['version']
                        current_pressure = next(r for r in newer['records'] if r['field'].endswith('.pressure_value_gpa'))
                        assert not current_pressure['provenance']['verified']
                        cached = await session.run_sync(lambda s: science.load_results(s, newer, reviewer.id, include_stale=True))
                        public = ev.public_snapshot(newer, cached)
                        stale = next(r for r in public['records'] if r['key'] == pressure['key'])
                        assert stale['stale'] and not stale.get('proposal_draft') and not stale.get('proposal')
                        assert not (await session.run_sync(lambda s: proposals.prepare(s, newer, reviewer.id)))['patches']
                        draft = await session.run_sync(lambda s: proposals.save_draft(s, newer, reviewer.id, pressure['key'], {}, True, '对照实验记录更正压力，保留原始记录'))
                        assert draft['previous_review']['reason'] == '旧值没有原文支持'
                        prepared = await session.run_sync(lambda s: proposals.prepare(s, newer, reviewer.id))
                        await session.run_sync(lambda s: proposals.finalize(s, newer, reviewer.id, prepared['preparation_id']))
                        final = ev.public_snapshot(newer, await session.run_sync(lambda s: science.load_results(s, newer, reviewer.id)))
                        confirmed = next(r for r in final['records'] if r['key'] == pressure['key'])
                        assert confirmed['human_confirmed'] and confirmed['source_kind'] == 'human_review'
                        assert float(confirmed['decision']['final_value']) == 0.002
                        assert not confirmed['provenance']['verified']

                        state.update({field:None for field in pressure_fields})
                        await _rewrite_paper_scientific_draft_in_tx(session, pid, copy.deepcopy(payload), reviewer)
                        await session.commit()
                    # 新会话读取经过生产保存路径写入的数据，而非复用内存状态。
                    async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint') as session:
                        saved = await session.scalar(select(models.MaterialState).where(models.MaterialState.paper_id == pid))
                        assert all(getattr(saved, field) is None for field in pressure_fields)
                        cleared = await session.run_sync(lambda s: ev.paper_snapshot(s, pid, reviewer.id, 'admin'))
                        assert not any('pressure' in r['field'] for r in cleared['records'])
                        assert not (await session.run_sync(lambda s: proposals.prepare(s, cleared, reviewer.id)))['patches']
                        assert await session.scalar(select(func.count()).select_from(models.PaperHistoryEvent).where(models.PaperHistoryEvent.paper_id == pid)) >= 3
                        assert (await session.get(models.Paper, pid)).review_status == 'pending'
                finally:
                    await outer.rollback()
        finally:
            await engine.dispose()
    asyncio.run(run())
