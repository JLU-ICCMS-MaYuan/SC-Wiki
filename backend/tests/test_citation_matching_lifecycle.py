"""#225：真实四篇资料贯穿持久快照、权限、提交及批准后的新会话重读。"""
import asyncio
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


FIXTURES = Path(__file__).resolve().parents[2] / 'docs/specs/225-citation-matching-and-static-graph/assets'


def test_four_papers_snapshot_permissions_submission_and_approval(tmp_path, monkeypatch):
    path = tmp_path / 'citations.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{path}')
    monkeypatch.setenv('JWT_SECRET_KEY', 'citation-225-isolated-test-key-not-for-production')
    from backend.database import Base
    from backend import database
    from backend.models import Paper, User, PaperReference, PaperReferenceExtraction
    from backend.workdraft_models import ScientificWorkDraft
    from backend.services.citation_matching import prepare_upload_matching, read_matching_snapshot
    from backend.services.citation_graph import persist_reference_extraction, reconcile_after_paper_approval
    corpus = json.loads((FIXTURES / 'citation-corpus.json').read_text())
    papers = {p['id']: p for p in corpus['papers']}
    sync_engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(sync_engine)
    factory = sessionmaker(sync_engine, expire_on_commit=False)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    engine = create_async_engine(f'sqlite+aiosqlite:///{path}')
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with sessions.begin() as session:
            session.add(User(id=1, email='citation@example.invalid', username='citation', real_name='Citation',
                             password_hash='not-a-credential', is_approved=True))
            for pid, p in papers.items():
                if pid == 1208:
                    continue
                session.add(Paper(id=pid, title=p['title'], authors=p['authors'], doi=p['doi'], year=p['year'],
                                  review_status='approved', content_revision=1, approved_revision=1))
            await session.flush()
            for pid in (271, 1204, 1429):
                paper = await session.get(Paper, pid)
                refs = [r for r in corpus['references'] if r['paper_id'] == pid]
                await persist_reference_extraction(session, paper, {'status': 'succeeded', 'references': refs})
    asyncio.run(seed())
    draft = {'paper': {k: papers[1208][k] for k in ('title', 'authors', 'doi', 'year')},
             'material_states': [], 'citation_extraction': {'status': 'succeeded', 'references':
                [r for r in corpus['references'] if r['paper_id'] == 1208]}}
    calls = []
    def unexpected_model(*a, **k):
        calls.append(1)
        raise AssertionError('已能由程序确定的本组书目不应发模型')
    snapshot = prepare_upload_matching(draft, 'upload:225-test', session_factory=factory, model=unexpected_model)
    assert len(snapshot['references']) == 37
    assert {r['paper']['paper_id'] for r in snapshot['downstream']} == {271, 1204, 1429}
    draft['citation_matching'] = snapshot
    with factory.begin() as session:
        session.add(ScientificWorkDraft(id='citation225', document_key='upload:225-test', target='upload',
                    target_id='225-test', owner_id=1, write_epoch='citation225', body=deepcopy(draft)))
    # 重新打开会话读取SQL工作稿，不使用模型或测试内存中的替代结果。
    from backend.ingest import upload_tasks
    reopened = upload_tasks.get_draft('225-test')
    assert reopened['citation_matching'] == snapshot
    with factory.begin() as session:
        paper = session.get(Paper, 271)
        paper.title = 'Changed bibliographic identity'
    current = read_matching_snapshot('225-test', reopened, factory)
    assert current['stale_count'] == 1
    assert sum(bool(r['decision'].get('stale')) for r in current['downstream']) == 1
    assert not any(r['decision'].get('stale') for r in reopened['citation_matching']['downstream'])
    with factory.begin() as session:
        session.get(Paper, 271).title = papers[271]['title']

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.upload_tasks import router
    from backend.security import get_current_user
    from backend.rag.llm_context import request_llm_config
    monkeypatch.setattr(upload_tasks, 'get_state', lambda task: {'user_id': 1, 'status': 'ready'} if task == '225-test' else None)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[request_llm_config] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='user', is_approved=True)
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get('/api/upload-tasks/225-test/citation-matching')
            assert response.status_code == 200 and len(response.json()['data']['downstream']) == 3
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='user', is_approved=True)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3, role='admin', is_approved=True)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code == 200
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=4, role='admin', is_approved=False)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3, role='superadmin', is_approved=True)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code == 200
        app.dependency_overrides.pop(get_current_user)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code in (401, 403)
    assert calls == []

    async def publish():
        async with sessions.begin() as session:
            # 原版本的引文被幂等重存后数据库自增ID变化，不能让旧指针丢掉真实关系。
            source = await session.get(Paper, 271)
            await persist_reference_extraction(session, source, {'status': 'succeeded', 'references':
                [r for r in corpus['references'] if r['paper_id'] == 271]})
            p = papers[1208]
            paper = Paper(id=1208, title=p['title'], authors=p['authors'], doi=p['doi'], year=p['year'],
                          review_status='pending', content_revision=1, upload_task_id='225-test', uploaded_by_user_id=1)
            session.add(paper)
            await session.flush()
            await persist_reference_extraction(session, paper, draft['citation_extraction'], matching_snapshot=snapshot)
            refs = await session.scalars(select(PaperReference).where(PaperReference.cited_paper_id == 1208))
            assert list(refs) == []
            extraction = await session.get(PaperReferenceExtraction, (1208, 1))
            assert len(extraction.matching_snapshot['downstream']) == 3
            paper.review_status = 'approved'
            paper.approved_revision = 1
            await session.flush()
            await reconcile_after_paper_approval(session, 1208)
        async with sessions() as session:
            rows = (await session.scalars(select(PaperReference).where(PaperReference.match_status == 'matched'))).all()
            assert {(r.paper_id, r.cited_paper_id) for r in rows} == {
                (271, 1204), (271, 1208), (271, 1429), (1204, 1208), (1429, 1204), (1429, 1208)}
            assert all(r.match_evidence and r.match_method in ('doi', 'title_year') for r in rows)
        await engine.dispose()
    asyncio.run(publish())
    monkeypatch.setattr(upload_tasks, 'get_state', lambda task: None)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='user', is_approved=True)
    with TestClient(app) as client:
        response = client.get('/api/upload-tasks/225-test/citation-matching')
        assert response.status_code == 200 and response.json()['data']['status'] == 'completed'
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='user', is_approved=True)
        assert client.get('/api/upload-tasks/225-test/citation-matching').status_code == 403
    repeated = prepare_upload_matching(draft, 'upload:225-test', session_factory=factory, model=unexpected_model)
    assert {r['paper']['paper_id'] for r in repeated['downstream']} == {271, 1204, 1429}
    sync_engine.dispose()


def test_model_decision_requires_server_cache_and_survives_only_valid_identity(tmp_path, monkeypatch):
    path = tmp_path / 'model.sqlite'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{path}')
    from backend.database import Base
    from backend.models import Paper, CitationMatchCache, PaperReference
    from backend.services.citation_matching import CitationCatalog, load_catalog, match_references
    from backend.services.citation_graph import persist_reference_extraction, reconcile_after_paper_approval
    sync = create_engine(f'sqlite:///{path}');Base.metadata.create_all(sync)
    factory = sessionmaker(sync, expire_on_commit=False)
    with factory.begin() as s:
        s.add(Paper(id=9, title='Superconductivity in compressed hydrogen cages', authors=['Hanyu Liu'],
                    year=2017, content_revision=1, approved_revision=1, review_status='approved'))
    with factory() as s:
        catalog = CitationCatalog(load_catalog(s))
    references = [{'reference_index': 0, 'raw_citation': 'H Liu (2017) Superconductivity in compressed hydrogen cages',
                   'title': 'Superconductivity of compressed hydrogen cages', 'authors': ['H Liu'], 'year': 2017}]
    calls = []
    def model(*a, **k):
        calls.append(1)
        return {'matches': {'0': {'paper_id': 9, 'reason': '原始引文对应'}}}
    def put(key, value):
        with factory.begin() as s:s.merge(CitationMatchCache(cache_key=key, payload=value))
    def get(key):
        with factory() as s:
            row=s.get(CitationMatchCache,key)
            return row.payload if row else None
    decided = match_references(references, catalog, namespace='model-proof', model=model, cache_get=get, cache_put=put)
    assert decided[0]['method'] == 'llm2'
    match_references(references, catalog, namespace='model-proof', model=model, cache_get=get, cache_put=put)
    assert len(calls) == 1
    async def scenario():
        engine = create_async_engine(f'sqlite+aiosqlite:///{path}')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions.begin() as s:
            source = Paper(id=10, title='Source', year=2024, content_revision=1, review_status='pending')
            s.add(source);await s.flush()
            await persist_reference_extraction(s, source, {'status': 'succeeded', 'references': references},
                matching_snapshot={'references': [{'reference_index': 0, 'decision': decided[0]}]})
            source.review_status='approved';source.approved_revision=1;await s.flush()
            await reconcile_after_paper_approval(s,10)
        async with sessions.begin() as s:
            row=await s.scalar(select(PaperReference).where(PaperReference.paper_id==10))
            assert row.match_method=='llm2' and row.cited_paper_id==9
            target=await s.get(Paper,9);target.title='A genuinely different work';await s.flush()
            await reconcile_after_paper_approval(s,9)
            assert row.cited_paper_id is None and row.match_evidence is None
            target.title='Superconductivity in compressed hydrogen cages'
            await s.flush()
            for pid, method in [(11, 'llm2'), (12, 'title_year')]:
                forged={**decided[0], 'cache_key':'not-a-server-cache-key', 'method':method}
                other=Paper(id=pid,title='Other source',year=2024,content_revision=1,review_status='pending')
                s.add(other);await s.flush()
                await persist_reference_extraction(s,other,{'status':'succeeded','references':references},
                    matching_snapshot={'references':[{'reference_index':0,'decision':forged}]})
                untrusted=await s.scalar(select(PaperReference).where(PaperReference.paper_id==pid))
                assert untrusted.cited_paper_id is None and untrusted.match_method is None
        await engine.dispose()
    asyncio.run(scenario())
    assert len(calls)==1
    sync.dispose()
