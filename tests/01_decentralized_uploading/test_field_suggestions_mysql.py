"""在本地 MySQL 外层回滚事务中验证采用、复核、批准来源重读，不写真实论文。"""
import copy
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.database import engine
from backend.ingest import property_evidence as ev, evidence_proposals as p, scientific_evidence as science

pytestmark = pytest.mark.skipif(os.getenv('SCWIKI_CURRENT_MYSQL') != '1', reason='显式启用本地 MySQL 回滚验证')


@pytest.fixture
def sessions():
    with engine.connect() as connection:
        assert connection.dialect.name == 'mysql'
        outer = connection.begin()
        try:
            yield sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
        finally:
            outer.rollback()


def make_snapshot(target_id, value=None):
    row = science.field_records('paper', 'paper', {'summary': value}, {'summary': '论文总结'})[0]
    return ev.complete_snapshot('upload', target_id, [row], [], {})


def test_guess_adoption_reload_review_and_formal_source(sessions):
    target = uuid.uuid4().hex
    snap = make_snapshot(target)
    key = snap['records'][0]['key']
    candidate = dict(values={'': 'Electron-phonon coupling is plausible.'}, basis_kind='general_knowledge',
                     explanation='依据一般金属知识推测，本文没有报告。', supported=False, evidences=[])
    with sessions.begin() as session:
        science.save_results(session, snap, {key: dict(status='missing', reason='无直接来源', evidences=[], proposal=candidate)}, 7)
    with sessions.begin() as session:
        assert science.load_results(session, snap, 7)[key]['proposal']['basis_kind'] == 'general_knowledge'
        accepted = p.save_draft(session, snap, 7, key, candidate['values'], True, '')
        assert accepted['accepted'] and not accepted['human_confirmed']
        session.flush()
        prepared = p.prepare(session, snap, 7)
    after = make_snapshot(target, candidate['values'][''])
    with sessions.begin() as session:
        p.finalize(session, after, 7, prepared['preparation_id'])
    with sessions.begin() as session:
        cached = science.load_results(session, after, 7)
        approved_upload = ev.resolve_results(after, cached, 7, None, after['version'])
        assert approved_upload[0]['adopted_basis'] == 'general_knowledge'
        # 同一字段身份转接到正式论文，候选和采用记录必须保留。
        user = session.scalar(select(models.User).where(models.User.account_status == 'active').limit(1))
        paper = models.Paper(title='109 transaction rollback', year=2026, summary=candidate['values'][''], uploaded_by_user_id=user.id, review_status='pending', content_revision=1)
        session.add(paper); session.flush()
        paper_id = paper.id
        paper_snap = ev.paper_snapshot(session, paper_id, user.id + 100000, 'admin')
        record = next(r for r in paper_snap['records'] if r['field'] == 'paper.summary')
        transferred = science.transfer_result(record, approved_upload[0], paper_snap['chunks'])
        science.save_results(session, paper_snap, {record['key']: transferred}, 7)
    with sessions.begin() as session:
        cached = science.load_results(session, paper_snap, 8)
        with pytest.raises(HTTPException): ev.resolve_results(paper_snap, cached, 8, None, paper_snap['version'])
        with pytest.raises(HTTPException): p.save_draft(session, paper_snap, 8, record['key'], {}, True, '')
        p.save_draft(session, paper_snap, 8, record['key'], {}, True, '人工确认这是通用知识推测，并非论文测量结论')
        session.flush()
        prepared = p.prepare(session, paper_snap, 8)
        session.flush()
        p.finalize(session, paper_snap, 8, prepared['preparation_id'])
    with sessions.begin() as session:
        cached = science.load_results(session, paper_snap, 8)
        results = ev.resolve_results(paper_snap, cached, 8, None, paper_snap['version'])
        checked = next(r for r in results if r['key'] == record['key'])
        assert checked['human_confirmed'] and checked['adopted_basis'] == 'general_knowledge'
        if os.getenv('SCWIKI_EVIDENCE_CONTRACT'):
            import json
            from pathlib import Path
            Path(os.environ['SCWIKI_EVIDENCE_CONTRACT']).write_text(json.dumps(results, ensure_ascii=False, default=str))
        # 存储并重读正式 JSON 与 Go 事务使用同一形状；Go 的实际事务另行验证。
        session.add(models.ScientificEvidenceSource(paper_id=paper_id, paper_revision=1, item_key=record['item_key'],
            field_path=record['field'], content_hash=record['content_hash'], source_hash=record['source_hash'],
            rule_version=ev.RULE_VERSION, result=copy.deepcopy(checked)))
    with sessions.begin() as session:
        source = session.scalar(select(models.ScientificEvidenceSource).where(models.ScientificEvidenceSource.paper_id == paper_id))
        from backend.rag.scientific_sources import source_chunk
        assert '通用知识推测' in source_chunk(source)['attribution']
        changed = copy.deepcopy(paper_snap)
        changed['records'] = [dict(record, content_hash='changed')]
        history = science.load_results(session, changed, 8, include_stale=True)[record['key']]
        assert history['stale'] and not history.get('decision')
        assert any((entry.get('decision') or {}).get('reason', '').startswith('人工确认') for entry in history['history'])
        # 清空可选字段时仍随正式归档保留旧来源，但不给当前空值授予确认。
        changed['records'][0]['required'] = False
        current = science.load_results(session, changed, 8)[record['key']]
        assert current['status'] == 'unchecked' and current['history']
        assert not current.get('decision')


def test_background_result_preserves_latest_human_decision(sessions):
    snap = make_snapshot(uuid.uuid4().hex, 'Tin'); row = snap['records'][0]; key = row['key']
    def result(reason):
        return dict(status='uncertain', decision=dict(accepted=True, human_confirmed=True, actor_user_id=8,
            reason=reason, final_content_hash=row['content_hash'], source_hash=row['source_hash']), adopted_basis='general_knowledge')
    with sessions.begin() as session:
        science.save_results(session, snap, {key: result('最初理由')}, 8, update_decision=True)
    with sessions.begin() as session:
        science.save_results(session, snap, {key: result('新的人工理由')}, 8, update_decision=True)
    with sessions.begin() as session:
        science.save_results(session, snap, {key: result('最初理由')}, 8)
    with sessions.begin() as session:
        assert science.load_results(session, snap, 8)[key]['decision']['reason'] == '新的人工理由'


def test_new_review_revokes_unsubmitted_old_supported_acceptance(sessions):
    snap = make_snapshot(uuid.uuid4().hex, 'Old summary')
    snap['chunks'] = [dict(file_id='main', chunk_index=0, content='Tin is metallic.')]
    row = snap['records'][0]; key = row['key']
    candidate = dict(values={'': 'Tin is metallic.'}, supported=True, basis_kind='paper_quote',
                     evidences=[dict(file_id='main', chunk_index=0, quote='Tin is metallic.')])
    with sessions.begin() as session:
        science.save_results(session, snap, {key: dict(status='unsupported', proposal=candidate, evidences=[])}, 8)
        p.save_draft(session, snap, 8, key, candidate['values'], True, '')
    candidate['supported'] = False
    with sessions.begin() as session:
        science.save_results(session, snap, {key: dict(status='unsupported', proposal=candidate, evidences=[],
            proposal_review={'status': 'questionable', 'explanation': '新复核不能支持旧候选'})}, 8)
    with sessions.begin() as session:
        result = science.load_results(session, snap, 8)[key]
        assert not result['proposal_draft']['accepted'] and result['proposal_draft']['values'] == candidate['values']
        assert p.prepare(session, snap, 8)['patches'] == []


def test_failed_finalize_cannot_overwrite_new_review_on_saved_value(sessions):
    target = uuid.uuid4().hex
    chunks = [dict(file_id='main', chunk_index=0, content='Tin is metallic.')]
    def with_source(value):
        return ev.complete_snapshot('upload', target, science.field_records('paper', 'paper', {'summary': value}, {'summary': '总结'}), chunks, {})
    before = with_source('Old summary'); row = before['records'][0]; key = row['key']
    proposal = dict(values={'': 'Tin is metallic.'}, supported=True, basis_kind='paper_quote',
                    evidences=[dict(file_id='main', chunk_index=0, quote='Tin is metallic.')])
    with sessions.begin() as session:
        science.save_results(session, before, {key: dict(status='unsupported', proposal=proposal, evidences=[])}, 8)
        p.save_draft(session, before, 8, key, proposal['values'], True, '')
        prepared = p.prepare(session, before, 8)
    after = with_source('Tin is metallic.')
    # 数据保存已成功，模拟 finalize 网络失败，此后对新值重新复核。
    with sessions.begin() as session:
        science.save_results(session, after, {key: dict(status='unsupported', reason='新复核反对', evidences=proposal['evidences'])}, 8)
    with sessions.begin() as session:
        for operation in (lambda: p.prepare(session, after, 8), lambda: p.finalize(session, after, 8, prepared['preparation_id'])):
            with pytest.raises(HTTPException) as error:
                operation()
            assert error.value.detail['code'] == 'evidence_review_required'
        assert science.load_results(session, after, 8)[key]['status'] == 'unsupported'
