"""#100 隔离 MySQL 验收服务：真实保存/认证/prepare-review，仅人工确认使用夹具。"""
import os

from fastapi import FastAPI
from sqlalchemy.engine import make_url
from backend import models
from backend.database import SessionLocal
from backend.api import rag, evidence
from backend.ingest import property_evidence as ev

url = make_url(os.environ['DATABASE_URL'])
assert url.host == '127.0.0.1' and 'test' in url.database
app = FastAPI()
app.include_router(rag.router)
app.include_router(evidence.router)


@app.post('/test/confirm/{paper_id}/{actor_id}')
def confirm(paper_id: int, actor_id: int):
    with SessionLocal.begin() as session:
        actor = session.get(models.User, actor_id)
        snapshot = ev.paper_snapshot(session, paper_id, actor.id, actor.role)
        for row in snapshot['records']:
            result = {**row, 'status': 'missing', 'evidences': [], 'decision': {
                'human_confirmed': True, 'accepted': True, 'actor_user_id': actor.id,
                'reason': '隔离测试中的已保存管理员逐项确认', 'final_content_hash': row['content_hash'],
                'source_hash': row['source_hash']}}
            session.add(models.ScientificEvidenceCheck(target='paper', target_id=str(paper_id), item_key=row['item_key'],
                content_hash=row['content_hash'], source_hash=row['source_hash'], rule_version=snapshot['rule_version'],
                result=result, resolutions={}, actor_user_id=actor.id))
        return {'version': snapshot['version']}
