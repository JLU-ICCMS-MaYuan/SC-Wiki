"""#116：真实登录校验与 HTTP 上游之间的模型归属边界。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import database
from backend.api import rag
from backend.models import User
from backend.rag import llm_context
from backend.rag.llm_catalog import parse_catalog
from backend.rag.llm_client import get_llm_client
from backend.security import create_access_token


@pytest.fixture
def catalog_app(monkeypatch, tmp_path):
    observed = []
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            observed.append((self.headers.get('Authorization'), body['model']))
            result = {'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': body['model'],
                      'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'OK'}, 'finish_reason': 'stop'}]}
            if body.get('stream'):
                chunk = {'id': 'test', 'object': 'chat.completion.chunk', 'created': 0, 'model': body['model'],
                         'choices': [{'index': 0, 'delta': {'content': body['model']}, 'finish_reason': None}]}
                data = ('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode()
            else:
                data = json.dumps(result).encode()
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream' if body.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        def log_message(self, *args):
            pass
    upstreams = {n: ThreadingHTTPServer(('127.0.0.1', 0), Upstream) for n in (1, 3)}
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in upstreams.values()]
    for thread in threads:
        thread.start()
    values = {}
    for n in (1, 3):
        values.update({f'LLM{n}_NAME': f'Model {n}', f'LLM{n}_BASE_URL': f'http://127.0.0.1:{upstreams[n].server_port}/v1',
                       f'LLM{n}_MODEL': f'model-{n}', f'LLM{n}_API_KEY': f'test-secret-{n}'})
    catalog = parse_catalog(values)
    monkeypatch.setattr(llm_context, 'get_catalog', lambda: catalog)
    monkeypatch.setattr(rag, 'get_catalog', lambda: catalog)
    monkeypatch.setattr(llm_context.settings, 'sc_wiki_data_dir', tmp_path)
    engine = create_engine('sqlite:///' + str(tmp_path/'auth.db'))
    User.__table__.create(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        session.add(User(email='catalog@example.test', username='catalog-user', password_hash='unused', real_name='测试用户',
                         account_status='active', session_version=2, role='user'))
        session.commit()
    def sessions():
        with factory() as session:
            yield session
    original_get_db = database.get_db
    monkeypatch.setattr(database, 'get_db', sessions)
    app = FastAPI(); app.include_router(rag.router)
    app.dependency_overrides[original_get_db] = sessions
    good = create_access_token({'sub': 'catalog@example.test', 'sv': 2})
    stale = create_access_token({'sub': 'catalog@example.test', 'sv': 1})
    async def chat(*args, **kwargs):
        config = llm_context.get_llm_config()
        result = get_llm_client().chat.completions.create(model=config.model, messages=[{'role':'user','content':'probe'}])
        return {'answer': result.choices[0].message.content, 'model': config.model}
    monkeypatch.setattr(rag.service, 'chat', chat)
    async def stream(*args, **kwargs):
        config = llm_context.get_llm_config()
        chunks = get_llm_client().chat.completions.create(model=config.model, messages=[{'role':'user','content':'probe'}], stream=True)
        for chunk in chunks:
            yield {'type':'token', 'data':chunk.choices[0].delta.content}
    monkeypatch.setattr(rag.service, 'chat_stream', stream)
    yield app, observed, good, stale, engine
    for server in upstreams.values():
        server.shutdown(); server.server_close()
    for thread in threads:
        thread.join()
    engine.dispose()


def test_real_auth_rejects_omission_forgery_expired_session_and_whitespace(catalog_app):
    app, observed, good, stale, engine = catalog_app
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            cases = [{}, {'X-LLM-Config-ID':'LLM3'}, {'Authorization':'Bearer invalid'},
                     {'Authorization':'Bearer '+stale},
                     {key:' ' for key in ('X-LLM-Provider','X-LLM-Model','X-LLM-Api-Key','X-LLM-Base-URL')}]
            for headers in cases:
                for path in ('/api/rag/chat', '/api/rag/chat/stream', '/api/rag/llm/test-connection'):
                    response = await client.post(path, headers=headers, json={'question':'probe'})
                    assert response.status_code == 401
            assert (await client.get('/api/rag/llm/current')).status_code == 200
            assert (await client.get('/api/rag/llm/catalog')).status_code == 401
            assert observed == []
            with sessionmaker(engine)() as session:
                account = session.query(User).first()
                account.account_status = 'banned'; session.commit()
            denied = await client.post('/api/rag/chat', headers={'Authorization':'Bearer '+good}, json={'question':'probe'})
            assert denied.status_code == 401 and observed == []
    anyio.run(run)


def test_catalog_selection_and_default_hit_correct_real_upstream(catalog_app):
    app, observed, good, stale, engine = catalog_app
    async def run():
        headers = {'Authorization':'Bearer '+good}
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/api/rag/llm/catalog', headers={**headers,'X-LLM-Config-ID':'LLM999'})
            assert response.status_code == 200
            assert [i['id'] for i in response.json()['data']['items']] == ['LLM1','LLM3']
            assert 'secret' not in response.text and 'base_url' not in response.text
            for extra, model in (({},'model-1'), ({'X-LLM-Config-ID':'LLM3'},'model-3')):
                r = await client.post('/api/rag/chat', headers={**headers,**extra},json={'question':'probe'})
                assert r.status_code == 200, r.text
                assert r.json()['data']['model'] == model
            for extra in ({'X-LLM-Config-ID':'LLM999'}, {'X-LLM-Config-ID':'LLM3','X-LLM-Api-Key':'personal'}):
                r = await client.post('/api/rag/chat',headers={**headers,**extra},json={'question':'probe'})
                assert r.status_code == 400 and 'test-secret' not in r.text
            assert observed == [('Bearer test-secret-1','model-1'),('Bearer test-secret-3','model-3')]
            response = await client.post('/api/rag/chat/stream', headers={**headers,'X-LLM-Config-ID':'LLM3'}, json={'question':'probe'})
            assert response.status_code == 200 and 'model-3' in response.text
            assert observed[-1] == ('Bearer test-secret-3','model-3')
            personal = {'X-LLM-Provider':'custom', 'X-LLM-Base-URL':llm_context.get_catalog().find('LLM1').base_url,
                        'X-LLM-Model':'personal-model', 'X-LLM-Api-Key':'personal-key'}
            response = await client.post('/api/rag/chat', headers=personal, json={'question':'probe'})
            assert response.status_code == 200
            assert observed[-1] == ('Bearer personal-key','personal-model')
    anyio.run(run)
