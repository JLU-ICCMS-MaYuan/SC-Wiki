"""浏览器夹具的真实 MySQL 存储桥：仅随机目标，全部写入由外层事务回滚。"""
import json
import os
import sys
import uuid
from pathlib import Path

assert os.environ.get('SCWIKI_CURRENT_MYSQL') == '1', '必须显式选择 MySQL 回滚验证'
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / '.env')
from sqlalchemy.orm import sessionmaker
from backend import models
from backend.database import engine
from backend.ingest import property_evidence as ev, scientific_evidence as science

with engine.connect() as connection:
    assert connection.dialect.name == 'mysql'
    outer = connection.begin()
    sessions = sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
    try:
        for line in sys.stdin:
            command = json.loads(line)
            op = command['op']
            if op == 'close':
                break
            if op == 'init':
                task_id = uuid.uuid4().hex
                draft = command['draft']
                with sessions.begin() as session:
                    science.persist_upload(session, task_id, {'user_id': 7}, draft)
                snap = ev.complete_snapshot('upload', task_id, science.state_records(draft['material_states'][0], 0), [], {})
                results = {r['key']: {'status': 'supported', 'reason': '隔离夹具核验', 'resolution': '保留的人工说明',
                    'human_confirmed': True, 'decision': {'human_confirmed': True, 'accepted': True,
                    'actor_user_id': 7, 'reason': '保留的人工说明', 'final_content_hash': r['content_hash'],
                    'source_hash': r['source_hash']}} for r in snap['records'] if r.get('required', True)}
                with sessions.begin() as session:
                    science.save_results(session, snap, results, 7)
            elif op == 'save':
                with sessions.begin() as session:
                    science.persist_upload(session, task_id, {'user_id': 7}, command['draft'])
            with sessions.begin() as session:
                # 每次都从新 Session 读回，不拿浏览器内存或上次响应冒充持久化。
                draft = session.get(models.ScientificUploadDraft, task_id).draft
                snap = ev.complete_snapshot('upload', task_id, science.state_records(draft['material_states'][0], 0), [], {})
                result = ev.public_snapshot(snap, science.load_results(session, snap, 7, include_stale=True))
            print(json.dumps({'draft': draft, 'preflight': result}, default=str), flush=True)
    finally:
        outer.rollback()
