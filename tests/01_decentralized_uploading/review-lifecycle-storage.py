"""完整编辑器验证的存储桥：读取真实草稿副本，所有测试写入在MySQL事务中回滚。"""
import json
import os
import sys
import uuid
from pathlib import Path
from copy import deepcopy

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from dotenv import load_dotenv
load_dotenv(root / '.env')
assert os.environ.get('SCWIKI_CURRENT_MYSQL') == '1'
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from backend.database import engine, SessionLocal
from backend import models
from backend.ingest import property_evidence as ev, scientific_evidence as science, evidence_proposals as proposals
from backend.ingest.upload_tasks import get_draft

source_id = os.environ['SCWIKI_SOURCE_TASK']
owner = int(os.environ.get('SCWIKI_SOURCE_OWNER', '2'))
original = ev.upload_snapshot(source_id, owner)
with SessionLocal() as session:
    original_results = science.load_results(session, original, owner, include_stale=True)
    from backend.ingest.form_definitions import definition_payload
    definitions = [definition_payload(d) for d in session.scalars(select(models.FormDefinition))]
source_draft = get_draft(source_id)
with engine.connect() as connection:
    assert connection.dialect.name == 'mysql'
    outer = connection.begin()
    sessions = sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
    task_id = uuid.uuid4().hex
    def snapshot(draft):
        snap = ev.upload_snapshot(source_id, owner, parsing_draft=draft)
        snap['target_id'] = task_id
        return snap
    try:
        for line in sys.stdin:
            command = json.loads(line)
            if command['op'] == 'close': break
            try:
                with sessions.begin() as db:
                    if command['op'] == 'init':
                        draft = deepcopy(source_draft)
                        draft['material_states'] = [s for s in draft['material_states'] if s.get('pressure_value_gpa') in {200,250,300}]
                        # 隔离副本重建用户报告的“仅331/0.1→新增296/0.16”起点，原任务不变。
                        for state in draft['material_states']:
                            if state.get('pressure_value_gpa') == 250:
                                for module in state.get('property_modules') or []:
                                    module['records'] = [r for r in module['records'] if r.get('record_type') != 'predicted_tc' or r.get('value_number') == 331]
                        science.persist_upload(db, task_id, {'user_id':owner}, draft)
                        snap = snapshot(draft)
                        seeds = {r['key']: original_results[r['key']] for r in snap['records'] if r['key'] in original_results}
                        science.save_results(db, snap, seeds, owner)
                    else:
                        draft = db.get(models.ScientificUploadDraft, task_id).draft
                        if command['op'] == 'save':
                            draft = command['draft']
                            science.persist_upload(db, task_id, {'user_id':owner}, draft)
                        snap = snapshot(draft)
                    response = {}
                    if command['op'] == 'proposal':
                        body = command['body']
                        if body['expected_version'] != snap['version']:
                            ev.fail('evidence_stale', '当前版本已改变')
                        response = {'draft': proposals.save_draft(db, snap, owner, body['key'], body['values'], body['accepted'], body['reason'])}
                    if command['op'] == 'recheck':
                        # 故障注入：新一次尝试漏引，真实旧规则证据必须仍可重验；不调用LLM。
                        science.save_results(db, snap, {r['key']: {'status':'uncertain','reason':'浏览器回归：本次漏引软件段落',
                            'condition_window_errors':['软件证据遗漏']} for r in snap['records'] if r.get('condition_context')}, owner)
                with sessions.begin() as db:
                    draft = db.get(models.ScientificUploadDraft, task_id).draft
                    snap = snapshot(draft)
                    public = ev.public_snapshot(snap, science.load_results(db, snap, owner, include_stale=True))
                print(json.dumps({'draft':draft,'preflight':public,'response':response,'definitions':definitions}, default=str), flush=True)
            except HTTPException as error:
                print(json.dumps({'error':error.detail,'status':error.status_code}, default=str), flush=True)
    finally:
        outer.rollback()
