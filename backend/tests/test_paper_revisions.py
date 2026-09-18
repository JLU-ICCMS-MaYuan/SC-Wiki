"""#108：返修草稿权限及独立持久化，集成测试只使用隔离测试库。"""
import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('JWT_SECRET_KEY', 'revision-test-only')

import pytest
from fastapi import HTTPException

from backend.models import Paper, User
from backend.services.paper_revisions import require_owner, require_rejected


@pytest.mark.parametrize('role', ['user', 'admin', 'superadmin'])
def test_revision_belongs_to_original_uploader(role):
    paper = Paper(id=12, uploaded_by_user_id=7, review_status='rejected')
    require_owner(paper, User(id=7, role=role))
    with pytest.raises(HTTPException) as error:
        require_owner(paper, User(id=8, role=role))
    assert error.value.status_code == 403


@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_only_rejected_papers_can_start_revision(status):
    with pytest.raises(HTTPException) as error:
        require_rejected(Paper(review_status=status))
    assert error.value.status_code == 409


def test_missing_paper_is_not_a_permission_failure():
    with pytest.raises(HTTPException) as error:
        require_owner(None, User(id=7))
    assert error.value.status_code == 404


@pytest.fixture
def workflow(monkeypatch):
    """真实 MySQL + HTTP + JWT；只注入模型结果，不模拟持久层或来源校验。"""
    url = os.environ.get('FRESH_MYSQL_DATABASE_URL')
    if not url:
        pytest.skip('需要已迁移到 #108 的隔离 MySQL 库')
    monkeypatch.setenv('DEBUG', 'false')
    import json
    import uuid
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from backend import database, models
    from backend.api import paper_revisions, evidence, rag
    from backend.security import create_access_token
    from backend.rag import database as async_db
    from backend.ingest import scientific_evidence as science
    from backend.services.paper_revisions import revision_snapshot

    parsed = make_url(url)
    assert parsed.host in {'localhost', '127.0.0.1'} and 'test' in parsed.database.lower()
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    async_engine = create_async_engine(url.replace('mysql+pymysql', 'mysql+asyncmy'), poolclass=NullPool)
    monkeypatch.setattr(async_db, 'async_session_factory', async_sessionmaker(async_engine, expire_on_commit=False))
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setattr(evidence, 'SessionLocal', factory)
    key = uuid.uuid4().hex[:12]
    with factory.begin() as session:
        owner = models.User(email=f'{key}@example.test', username='u'+key, real_name='返修测试',
            password_hash='unused', role='user', account_status='active', is_approved=True, is_email_verified=True, session_version=0)
        other = models.User(email=f'other-{key}@example.test', username='o'+key, real_name='另一用户',
            password_hash='unused', role='admin', account_status='active', is_approved=True, is_email_verified=True, session_version=0)
        session.add_all([owner, other]); session.flush()
        paper = models.Paper(title='Rejected paper', year=2026, authors=['A'], paper_type='review',
            uploaded_by_user_id=owner.id, review_status='rejected', content_revision=1,
            review_comment='请核对压强', superconductor_kind='unknown')
        session.add(paper); session.flush()
        source = models.PaperFile(paper_id=paper.id, paper_revision=1, role='main', original_filename='paper.md',
            stored_path='/private/revision-test.md', sha256=key.ljust(64, '0'), media_type='text/markdown', size=100)
        session.add(source); session.flush()
        chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=source.id, chunk_index=0,
            content='This review describes superconductivity. The critical temperature is 10 K.')
        session.add(chunk)
        session.add(models.PaperHistoryEvent(paper_id=paper.id, paper_revision=1, event_type='reviewed',
            actor_user_id=other.id, actor_username_snapshot=other.username, review_status='rejected', review_comment='请核对压强'))
    app = FastAPI()
    app.include_router(paper_revisions.router); app.include_router(evidence.router); app.include_router(rag.router)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[database.get_db] = db
    owner_token = create_access_token({'sub': owner.email, 'sv': 0})
    other_token = create_access_token({'sub': other.email, 'sv': 0})
    client = TestClient(app)
    client.headers['Authorization'] = 'Bearer '+owner_token
    base = f'/api/rag/papers/{paper.id}/revision-draft'

    def check_all(revision_id):
        with factory.begin() as session:
            snapshot = revision_snapshot(session, revision_id, owner.id)
            # 模型替身提供真实片段内的引句；共享 checked_result 仍验证来源。
            results = {r['key']: {'status': 'supported', 'reason': '测试模型核对', 'evidences': [
                {**snapshot['chunks'][0], 'quote': 'This review describes superconductivity.'}]} for r in snapshot['records']}
            science.save_results(session, snapshot, results, owner.id)
            return snapshot['version']
    yield SimpleNamespace(client=client, base=base, factory=factory, paper=paper, owner=owner, other=other,
        owner_token=owner_token, other_token=other_token, check_all=check_all, models=models, select=select,
        async_factory=async_sessionmaker(async_engine, expire_on_commit=False))
    client.close(); engine.dispose()


def begin(workflow):
    result = workflow.client.post(workflow.base)
    assert result.status_code == 200, result.text
    return result.json()


def save(workflow, opened, title='Revised paper'):
    import copy
    draft = copy.deepcopy(opened['data'])
    draft['paper']['title'] = title
    draft['paper']['material_families'] = [{'name': '返修待确认家族', 'status': 'pending'}]
    result = workflow.client.put(workflow.base, json={
        'revision_id': opened['revision_id'], 'draft_version': opened['draft_version'], 'draft': draft})
    assert result.status_code == 200, result.text
    return result.json()


def submission(saved, version=None):
    return dict(revision_id=saved['revision_id'], draft_version=saved['draft_version'], expected_evidence_version=version)


def test_http_save_restores_after_24_hours_without_changing_paper(workflow):
    from datetime import datetime, timedelta
    w = workflow
    opened = begin(w)
    assert opened['review_comment'] == '请核对压强'
    assert opened['warnings']
    assert '/private/' not in str(opened)
    saved = save(w, opened)
    with w.factory.begin() as session:
        paper = session.get(w.models.Paper, w.paper.id)
        assert (paper.title, paper.review_status, paper.content_revision) == ('Rejected paper', 'rejected', 1)
        row = session.get(w.models.PaperRevisionDraft, paper.id)
        row.updated_at = datetime.utcnow()-timedelta(days=3)
    assert w.client.get(w.base).json()['data']['paper']['title'] == 'Revised paper'
    assert begin(w)['revision_id'] == saved['revision_id']


def test_http_revision_permissions_and_old_window_conflict(workflow):
    w = workflow
    opened = begin(w)
    assert w.client.put(f'/api/rag/papers/{w.paper.id}/scientific-draft', json=opened['data']).status_code == 403
    save(w, opened)
    old = w.client.put(w.base, json={**submission(opened), 'draft': opened['data']})
    assert old.status_code == 409 and old.json()['detail']['code'] == 'revision_draft_conflict'
    w.client.headers['Authorization'] = 'Bearer '+w.other_token
    assert w.client.put(f'/api/rag/papers/{w.paper.id}/scientific-draft',
        json={'paper_type': 'review', 'material_states': []}).status_code == 409
    for method in ('get', 'post'):
        assert getattr(w.client, method)(w.base).status_code == 403
    assert w.client.put(w.base, json={**submission(opened), 'draft': opened['data']}).status_code == 403
    assert w.client.post(w.base+'/submit', json=submission(opened)).status_code == 403
    assert w.client.post('/api/rag/evidence/preflight', json={'target': 'revision', 'target_id': opened['revision_id']}).status_code == 403
    w.client.headers.pop('Authorization')
    assert w.client.post(w.base).status_code in {401, 403}


def test_admin_same_revision_change_blocks_save_and_submit(workflow):
    w = workflow
    opened = begin(w)
    with w.factory.begin() as session:
        session.get(w.models.Paper, w.paper.id).title = 'Admin edit'
    assert begin(w)['conflict'] is True
    response = w.client.put(w.base, json={**submission(opened), 'draft': opened['data']})
    assert response.status_code == 409
    assert w.client.post(w.base+'/submit', json=submission(opened)).status_code == 409
    with w.factory() as session:
        assert session.get(w.models.Paper, w.paper.id).title == 'Admin edit'


def test_resubmit_is_atomic_idempotent_and_can_start_next_round(workflow):
    w = workflow
    saved = save(w, begin(w))
    version = w.check_all(saved['revision_id'])
    first = w.client.post(w.base+'/submit', json=submission(saved, version))
    assert first.status_code == 200, first.text
    assert first.json()['content_revision'] == 2
    assert w.client.post(w.base+'/submit', json=submission(saved, version)).json()['content_revision'] == 2
    with w.factory() as session:
        paper = session.get(w.models.Paper, w.paper.id)
        assert (paper.title, paper.review_status, paper.content_revision) == ('Revised paper', 'pending', 2)
        assert paper.review_comment is None
        events = list(session.scalars(w.select(w.models.PaperHistoryEvent).where(w.models.PaperHistoryEvent.paper_id == paper.id)))
        assert len(events) == 2 and events[0].review_comment == '请核对压强'
        assert session.get(w.models.PaperRevisionDraft, paper.id).draft is None
        files = list(session.scalars(w.select(w.models.PaperFile).where(w.models.PaperFile.paper_id == paper.id)))
        chunks = list(session.scalars(w.select(w.models.PaperChunk).where(w.models.PaperChunk.paper_id == paper.id)))
        assert len(files) == len(chunks) == 1
        assert files[0].paper_revision == chunks[0].paper_revision == 2
    assert w.client.post(w.base).status_code == 409
    w.client.headers['Authorization'] = 'Bearer '+w.other_token
    artifact = w.client.get(f'/api/rag/papers/{w.paper.id}/review-artifact')
    assert artifact.status_code == 200, artifact.text
    assert artifact.json()['data']['user_values']['paper']['material_families'][0]['name'] == '返修待确认家族'
    with w.factory.begin() as session:
        session.get(w.models.Paper, w.paper.id).review_status = 'rejected'
    w.client.headers['Authorization'] = 'Bearer '+w.owner_token
    second = begin(w)
    assert second['revision_id'] != saved['revision_id']
    # 即使开始下一轮，上一轮响应丢失后的重试仍只返回旧回执。
    assert w.client.post(w.base+'/submit', json=submission(saved, version)).json()['content_revision'] == 2


def test_failure_after_revision_bump_rolls_back_everything(workflow, monkeypatch):
    from backend.ingest import scientific_drafts
    w = workflow
    structure_ids, _ = seed_scientific_graph(w)
    saved = save(w, begin(w))
    version = w.check_all(saved['revision_id'])
    async def fail(*args):
        raise RuntimeError('模拟重建失败')
    monkeypatch.setattr(scientific_drafts, 'persist_scientific_draft', fail)
    with pytest.raises(RuntimeError, match='模拟重建失败'):
        w.client.post(w.base+'/submit', json=submission(saved, version))
    with w.factory() as session:
        paper = session.get(w.models.Paper, w.paper.id)
        assert (paper.title, paper.content_revision, paper.review_status) == ('Rejected paper', 1, 'rejected')
        assert session.get(w.models.PaperRevisionDraft, paper.id).draft['paper']['title'] == 'Revised paper'
        assert all(session.get(w.models.StructureModel, sid).paper_revision == 1 for sid in structure_ids)


def test_concurrent_retries_only_increment_once(workflow):
    from concurrent.futures import ThreadPoolExecutor
    w = workflow
    saved = save(w, begin(w))
    version = w.check_all(saved['revision_id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: w.client.post(w.base+'/submit', json=submission(saved, version)), range(2)))
    assert [r.status_code for r in replies] == [200, 200]
    assert [r.json()['content_revision'] for r in replies] == [2, 2]
    with w.factory() as session:
        assert len(list(session.scalars(w.select(w.models.PaperHistoryEvent).where(
            w.models.PaperHistoryEvent.operation_id == 'revision:'+saved['revision_id'])))) == 1


def test_changed_scientific_content_requires_new_evidence(workflow):
    w = workflow
    saved = save(w, begin(w))
    version = w.check_all(saved['revision_id'])
    saved['data']['paper']['summary'] = 'New scientific conclusion'
    changed = save(w, saved)
    result = w.client.post(w.base+'/submit', json=submission(changed, version))
    assert result.status_code == 409 and result.json()['detail']['code'] == 'evidence_stale'


def seed_scientific_graph(w):
    import asyncio
    from backend.tests.test_structure_candidates import CIF, POSCAR
    from backend.ingest.scientific_drafts import persist_scientific_draft
    from backend.ingest.property_evidence import persist_existing_paper_targets
    async def seed():
        async with w.async_factory.begin() as session:
            paper = await session.get(w.models.Paper, w.paper.id)
            paper.paper_type = 'experimental'
            chunk = await session.scalar(w.select(w.models.PaperChunk).where(w.models.PaperChunk.paper_id == paper.id))
            quote = dict(chunk_id=chunk.id, file_id=str(chunk.paper_file_id), chunk_index=0,
                         quote='The critical temperature is 10 K.')
            record = dict(record_key='tc-1', record_type='measured_tc', property_code='tc', name_raw='Tc',
                definition_key='record.superconductive_properties.measured_tc.resistivity', definition_version=1,
                value_kind='number', value_raw='10 K', value_number=10, canonical_unit='K',
                method_code='resistivity', payload={'experimental_conditions': {'applied_field_t': 0}}, evidences=[quote])
            draft = dict(paper={'superconductor_kind': 'unknown'}, material_states=[dict(
                state_key='sample-a', material='Si', material_name='硅样品', pressure_value_gpa=0,
                schema_version=2, property_modules=[dict(module_key='tc-module', module_code='superconductive_properties',
                    records=[record, {**record, 'record_key': 'tc-2', 'value_raw': '11 K', 'value_number': 11}])],
                structure=dict(structure_format='cif', structure_text=CIF, nuclear_treatment='experimental'))])
            targets = await persist_scientific_draft(session, paper, draft)
            await persist_existing_paper_targets(session, paper, targets)
            first = await session.scalar(w.select(w.models.StructureModel).where(w.models.StructureModel.paper_id == paper.id))
            first.exchange_correlation = 'PBE'
            first.method_parameters = {'cutoff': 500}
            second = w.models.StructureModel(paper_id=paper.id, paper_revision=1, material_state_id=first.material_state_id,
                parent_structure_id=first.id, structure_format='poscar', structure_text=POSCAR, structure_hash='a'*64,
                nuclear_treatment='experimental', geometry_method='refined', source_locator='Table 2')
            session.add(second)
            await session.flush()
            records = (await session.scalars(w.select(w.models.PropertyRecord).where(w.models.PropertyRecord.paper_id == paper.id)
                .order_by(w.models.PropertyRecord.record_key))).all()
            records[0].structure_key = f'structure-{second.id}'
            evidence = await session.scalar(w.select(w.models.PaperEvidence).where(w.models.PaperEvidence.paper_id == paper.id))
            session.add(w.models.StructureModelEvidence(structure_id=second.id, paper_evidence_id=evidence.id,
                paper_id=paper.id, paper_revision=1, evidence_role='primary'))
            session.add(w.models.PropertyRecordDefinitionEvent(record_id=records[0].id, paper_id=paper.id,
                paper_revision=1, record_key=records[0].record_key, operation='upgrade', actor_user_id=w.other.id,
                from_definition_key=records[0].definition_key, from_definition_version=1,
                to_definition_key=records[0].definition_key, to_definition_version=1,
                before_snapshot={'value_raw': '9 K'}, after_snapshot={'value_raw': '10 K'}, request_checksum='b'*64))
            return [first.id, second.id], evidence.id
    return asyncio.run(seed())


def test_full_graph_roundtrip_preserves_structures_sources_and_history(workflow):
    from backend.tests.test_structure_candidates import POSCAR
    w = workflow
    original_ids, evidence_id = seed_scientific_graph(w)
    opened = begin(w)
    assert len(opened['data']['structure_candidates']) == 2
    records = opened['data']['material_states'][0]['property_modules'][0]['records']
    assert len(records) == 2 and records[0]['evidences'][0]['quote'] == 'The critical temperature is 10 K.'
    opened['data']['paper'].update(corresponding_authors=['A'], uploaded_by_user_id=w.other.id,
        review_status='approved', admin_internal_note='禁止写入')
    records[0].update(value_raw='12 K', value_number=12)
    saved = save(w, opened)
    version = w.check_all(saved['revision_id'])
    result = w.client.post(w.base+'/submit', json=submission(saved, version))
    assert result.status_code == 200, result.text
    with w.factory() as session:
        states = list(session.scalars(w.select(w.models.MaterialState).where(w.models.MaterialState.paper_id == w.paper.id)))
        structures = list(session.scalars(w.select(w.models.StructureModel).where(w.models.StructureModel.paper_id == w.paper.id).order_by(w.models.StructureModel.id)))
        assert len(states) == 1 and len(structures) == 2
        assert structures[0].id not in original_ids
        assert structures[0].exchange_correlation == 'PBE' and structures[0].method_parameters == {'cutoff': 500}
        assert structures[1].parent_structure_id == structures[0].id
        assert structures[1].structure_text == POSCAR and structures[1].structure_format == 'poscar'
        assert structures[1].source_locator == 'Table 2'
        assert session.get(w.models.StructureModelEvidence, (structures[1].id, evidence_id)).paper_revision == 2
        records = list(session.scalars(w.select(w.models.PropertyRecord).where(w.models.PropertyRecord.paper_id == w.paper.id).order_by(w.models.PropertyRecord.record_key)))
        assert [r.value_number for r in records] == [12, 11]
        assert records[0].structure_key == f'structure-{structures[1].id}'
        for record in records:
            assert list(session.scalars(w.select(w.models.PropertyRecordEvidence).where(w.models.PropertyRecordEvidence.record_id == record.id)))
        history = session.scalar(w.select(w.models.PaperHistoryEvent).where(w.models.PaperHistoryEvent.operation_id == 'revision:'+saved['revision_id']))
        assert history.classification_snapshot['previous_definition_events'][0]['before_snapshot'] == {'value_raw': '9 K'}
        assert history.classification_snapshot['revision_submission']['paper']['corresponding_authors'] == ['A']
        paper = session.get(w.models.Paper, w.paper.id)
        assert paper.uploaded_by_user_id == w.owner.id and paper.review_status == 'pending' and paper.admin_internal_note is None


def test_structure_metadata_change_conflicts_even_without_paper_revision_change(workflow):
    w = workflow
    ids, _ = seed_scientific_graph(w)
    opened = begin(w)
    with w.factory.begin() as session:
        session.get(w.models.StructureModel, ids[0]).exchange_correlation = 'LDA'
    assert w.client.post(w.base+'/submit', json=submission(opened)).status_code == 409


def test_late_evidence_cannot_overwrite_changed_draft(workflow):
    from backend.ingest import property_evidence as ev
    from backend.services.paper_revisions import revision_snapshot
    w = workflow
    opened = begin(w)
    with w.factory() as session:
        snapshot = revision_snapshot(session, opened['revision_id'], w.owner.id)
    save(w, opened)
    with pytest.raises(HTTPException) as error:
        ev.persist_completed_results(snapshot, {}, w.owner.id)
    assert error.value.detail['code'] == 'evidence_stale'


@pytest.mark.parametrize('status', ['pending', 'approved'])
def test_http_state_change_preserves_draft_and_forbids_writes(workflow, status):
    w = workflow
    saved = save(w, begin(w))
    with w.factory.begin() as session:
        paper = session.get(w.models.Paper, w.paper.id)
        paper.review_status = status
        paper.approved_revision = 1 if status == 'approved' else None
    assert w.client.post(w.base).status_code == 409
    assert w.client.put(w.base, json={**submission(saved), 'draft': saved['data']}).status_code == 409
    assert w.client.post(w.base+'/submit', json=submission(saved)).status_code == 409
    with w.factory() as session:
        assert session.get(w.models.PaperRevisionDraft, w.paper.id).draft == saved['data']


def test_revision_returns_to_real_go_review_and_next_round(workflow):
    """Python 暂存/送审→Go JWT/审核事务→Python 再次返修；不调用生产服务。"""
    import shutil
    import subprocess
    from pathlib import Path
    from sqlalchemy.engine import make_url
    go = os.environ.get('SCWIKI_TEST_GO') or shutil.which('go')
    if not go:
        pytest.skip('跨语言验收需要 SCWIKI_TEST_GO')
    w = workflow
    seed_scientific_graph(w)
    saved = save(w, begin(w))
    version = w.check_all(saved['revision_id'])
    assert w.client.post(w.base+'/submit', json=submission(saved, version)).status_code == 200
    parsed = make_url(os.environ['FRESH_MYSQL_DATABASE_URL'])
    env = dict(os.environ, SCWIKI_REVISION_TEST_PAPER=str(w.paper.id), SCWIKI_REVISION_TEST_ADMIN=str(w.other.id),
        SCWIKI_TEST_MYSQL_DSN=f'{parsed.username}:{parsed.password or ""}@tcp({parsed.host}:{parsed.port or 3306})/{parsed.database}?parseTime=true')
    result = subprocess.run([go, 'test', './handlers', '-run', '^TestRevisionResubmittedReview$', '-count=1'],
        cwd=Path(__file__).resolve().parents[2]/'goserver', env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    reopened = begin(w)
    assert reopened['revision_id'] != saved['revision_id'] and reopened['base_revision'] == 2
    assert reopened['review_comment'] == '返修后再次核对'
    with w.factory() as session:
        events = list(session.scalars(w.select(w.models.PaperHistoryEvent).where(w.models.PaperHistoryEvent.paper_id == w.paper.id)))
        assert len(events) == 3


def test_revision_structure_upload_uses_server_provenance_and_owner_check(workflow):
    from backend.tests.test_structure_candidates import CIF
    w = workflow
    seed_scientific_graph(w)
    opened = begin(w)
    data = {'revision_id': opened['revision_id'], 'material_state_index': '0'}
    w.client.headers['Authorization'] = 'Bearer '+w.other_token
    assert w.client.post(w.base+'/structure-candidates', data=data, files={'file': ('sample.cif', CIF)}).status_code == 403
    w.client.headers['Authorization'] = 'Bearer '+w.owner_token
    response = w.client.post(w.base+'/structure-candidates', data=data, files={'file': ('sample.cif', CIF)})
    assert response.status_code == 200, response.text
    candidate = response.json()['data']
    assert candidate['material_state_ref'] == 'material_states[0]'
    with w.factory() as session:
        origin = session.scalar(w.select(w.models.ScientificStructureOrigin).where(
            w.models.ScientificStructureOrigin.target == 'revision', w.models.ScientificStructureOrigin.target_id == opened['revision_id']))
        assert origin.provenance['submitted_by_user_id'] == w.owner.id
    assert len(w.client.get(w.base).json()['data']['structure_candidates']) == 2  # 上传不代替整页保存


def test_invalid_definition_returns_field_error_and_preserves_saved_draft(workflow):
    w = workflow
    seed_scientific_graph(w)
    opened = begin(w)
    opened['data']['material_states'][0]['property_modules'][0]['records'][0]['definition_version'] = 999
    saved = save(w, opened)
    version = w.check_all(saved['revision_id'])
    response = w.client.post(w.base+'/submit', json=submission(saved, version))
    assert response.status_code == 400, response.text
    with w.factory() as session:
        assert session.get(w.models.Paper, w.paper.id).content_revision == 1
        assert session.get(w.models.PaperRevisionDraft, w.paper.id).draft == saved['data']
