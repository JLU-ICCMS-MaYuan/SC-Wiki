"""提交区分有效通过、明确科学失败和系统尚未完成，不能只按是否人工修改筛选。"""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import json

from backend.api import evidence as api
from backend.ingest import property_evidence as ev, scientific_evidence as science


def test_submit_only_enqueues_unfinished_and_reuses_completed_scientific_decisions(monkeypatch):
    draft = {'paper': {'summary': 'A summary', 'key_finding': 'A finding', 'research_motivation': 'A motivation'}}
    snap = ev.complete_snapshot('upload', 'isolated', science.field_records('paper', 'paper',
        draft['paper'], {k: k for k in draft['paper']}),
        [{'file_id': 'main', 'chunk_index': 0, 'content': 'Original scientific source.'}], draft)
    rows = snap['records']
    cached = {r['key']: {**deepcopy(r), 'status': state, 'reason': '当前版本的已保存结论'}
              for r, state in zip(rows, ['supported', 'unsupported', 'unchecked'])}
    writes = {}; queued = []
    client = SimpleNamespace(eval=lambda *a: '', setex=lambda key, ttl, value: writes.__setitem__(key, value))
    monkeypatch.setattr(api, 'redis_client', lambda: client)
    monkeypatch.setattr(api, 'get_llm_config', lambda: SimpleNamespace(api_key='isolated'))
    monkeypatch.setattr(api, 'save_llm_config', lambda *a: None)
    monkeypatch.setattr(api, 'upload_queue', lambda: SimpleNamespace(enqueue=lambda *a, **kw: queued.append(a)))
    from backend import database
    from backend.ingest import field_drafts
    monkeypatch.setattr(database, 'SessionLocal', lambda: nullcontext(SimpleNamespace()))
    monkeypatch.setattr(field_drafts, 'authorized_draft', lambda *a: (draft, None))
    monkeypatch.setattr(api, 'preparation_progress', lambda *a: None)
    # job控制投影与完整任务仍由生产构造器生成，只替换存储连接。
    monkeypatch.setattr(ev, 'write_job_control', lambda job, c: None)
    body = api.Target(target='upload', target_id='isolated', purpose='submit', expected_version=snap['version'])
    response = api.enqueue_review(body, SimpleNamespace(id=7, role='user'), snap, cached)
    assert response['status'] == 'queued' and len(queued) == 1
    job = json.loads(writes[ev.task_key(response['id'])])
    assert job['requested_keys'] == [rows[2]['key']]
    assert job['cached'][rows[0]['key']]['status'] == 'supported'
    assert job['cached'][rows[1]['key']]['status'] == 'unsupported'
    assert not any(r['human_modified'] for r in job['snapshot']['records'])
