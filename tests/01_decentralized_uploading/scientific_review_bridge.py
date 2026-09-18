"""跨 Go/Python 审核事务验收桥；固定模型判断，真实来源与 MySQL，写入回滚。"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api import evidence
from backend.database import engine, SessionLocal
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.ingest import evidence_proposals as proposals
from backend import models
from backend.security import decode_access_token
from sqlalchemy import select

app = FastAPI()
app.include_router(evidence.router)
client = TestClient(app)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        paper_id = int(self.path.rsplit('/', 1)[-1])
        with SessionLocal() as session:
            snap = ev.paper_snapshot(session, paper_id, 0, '', check_access=False)
        self.reply(200, {'version':snap['version'],'keys':[r['key'] for r in snap['records']]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with engine.connect() as connection:
            outer = connection.begin()
            original = evidence.SessionLocal
            factory = lambda: Session(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
            try:
                with factory() as session, session.begin():
                    snap = ev.paper_snapshot(session, body['paper_id'], 0, '', check_access=False)
                    source = snap['chunks'][0]
                    # 模型替身只决定语义结论。真实 locator、缓存读取、权限、版本与接口全部执行。
                    results = {r['key']: {'status':'uncertain','reason':'事务验收的模型疑点，需人工裁决',
                        'suggestion':'核对当前论文原文','evidences':[{'file_id':source['file_id'],'chunk_index':source['chunk_index'],'quote':source['content']}]} for r in snap['records']}
                    if os.environ.get('SCWIKI_TEST_HUMAN_CONFIRM') == '1':
                        results = {r['key']: {'status': 'missing', 'reason': '论文未直接表述', 'evidences': []} for r in snap['records']}
                    science.save_results(session, snap, results, 0)
                    if os.environ.get('SCWIKI_TEST_HUMAN_CONFIRM') == '1' and body.get('resolutions'):
                        claims = decode_access_token(self.headers.get('Authorization', '').removeprefix('Bearer '))
                        actor = session.scalar(select(models.User).where(models.User.email == claims['sub']))
                        for record in snap['records']:
                            proposals.save_draft(session, snap, actor.id, record['key'], {}, True, body['resolutions'][record['key']])
                        prepared = proposals.prepare(session, snap, actor.id)
                        proposals.finalize(session, snap, actor.id, prepared['preparation_id'])
                evidence.SessionLocal = factory
                response = client.post('/api/rag/evidence/prepare-review', json=body,
                    headers={'Authorization':self.headers.get('Authorization','')})
                status, content = response.status_code, response.json()
            finally:
                evidence.SessionLocal = original
                outer.rollback()
        # 回滚后才发送结果，不让 Go 的清理事务等待测试缓存行锁。
        self.reply(status, content)

    def reply(self, status, content):
        raw = json.dumps(content, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1',0),Handler)
    print(server.server_address[1],flush=True)
    server.serve_forever()
