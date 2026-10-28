"""图谱标题使用生产保存函数；MySQL 外层回滚，Redis 仅写入随机测试键。"""
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend import database, models
from backend.ingest import field_drafts, property_evidence as ev, scientific_evidence as science, upload_tasks
from test_scientific_evidence_mysql import current_mysql

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅显式启用本地回滚测试')


@pytest.mark.parametrize('before,after', [('Old graph title', 'New graph title'), (None, 'New graph title'), ('Old graph title', '')])
def test_graph_title_save_reload_and_review_invalidation(current_mysql, monkeypatch, before, after):
    monkeypatch.setattr(database, 'SessionLocal', current_mysql)
    target = uuid4().hex
    client = upload_tasks.redis_client()
    draft = {'paper': {'title': 'Unchanged original title', 'knowledge_graph_title': before},
             'material_states': [], '_field_edit_format': 1}
    def snapshot(value):
        return ev.complete_snapshot('upload', target, ev.draft_records(value, {}), [], value)
    initial = snapshot(draft)
    row = next(r for r in initial['records'] if r['field'] == 'paper.knowledge_graph_title')
    keys = [upload_tasks.task_key(target), upload_tasks.draft_key(target), upload_tasks.lock_key(target)]
    try:
        with current_mysql.begin() as db:
            user = db.scalar(select(models.User).where(models.User.account_status == 'active').limit(1))
            assert user is not None
            actor = SimpleNamespace(id=user.id, role='user', username='graph-title-fixture')
            state = {'user_id': actor.id, 'stage': 'ready', 'status': 'ready', 'processing_status': 'succeeded'}
            science.persist_upload(db, target, state, draft)
            science.save_results(db, initial, {row['key']: {'status': 'supported', 'reason': '旧值核对记录', 'evidences': []}}, actor.id)
        client.setex(keys[0], 600, json.dumps(state))
        client.setex(keys[1], 600, json.dumps(draft))
        version = field_drafts.draft_version(draft)
        changes = [{'path': ['paper', 'knowledge_graph_title'], 'before': before, 'value': after}]
        with field_drafts.target_lock('upload', target), current_mysql.begin() as db:
            result = field_drafts.save_fields(db, 'upload', target, actor, version, changes)
            assert result['changed']
        loaded = upload_tasks.get_draft(target)
        assert loaded['paper'] == {'title': 'Unchanged original title', 'knowledge_graph_title': after}
        with current_mysql() as db:
            assert db.get(models.ScientificUploadDraft, target).draft['paper'] == loaded['paper']
            fresh = snapshot(loaded)
            record = next(r for r in fresh['records'] if r['field'] == row['field'])
            assert record['content_hash'] != row['content_hash']
            cached = science.load_results(db, fresh, actor.id)
            public = next(r for r in ev.public_snapshot(fresh, cached)['records'] if r['key'] == record['key'])
            assert public['status'] == 'unchecked'
            assert not public.get('human_confirmed')
            assert science.load_results(db, fresh, actor.id, include_stale=True)[record['key']]['stale']
        # 浏览器持有旧版本时不能覆盖新值。
        with field_drafts.target_lock('upload', target), current_mysql.begin() as db:
            with pytest.raises(HTTPException) as error:
                field_drafts.save_fields(db, 'upload', target, actor, version, changes)
            assert error.value.status_code == 409
        assert upload_tasks.get_draft(target)['paper']['knowledge_graph_title'] == after
    finally:
        client.delete(*keys)
