"""批准历史保留完整审计，但不能逐字段复制巨大的旧上下文。"""
import asyncio
import json
import os
from types import SimpleNamespace

from backend.services import field_review_commit as service


def test_approval_history_deduplicates_context_without_losing_field_decisions(monkeypatch):
    if not os.environ.get('JWT_SECRET_KEY'):
        monkeypatch.setenv('JWT_SECRET_KEY', 'test-review-history-only')
    from backend.api import rag
    from backend.services import paper_history

    shared = {'original_source': '保留原始出处及历史，不作科学放行。' * 1800}
    checks = [{'item_key': str(i), 'key': str(i), 'field': f'field.{i}',
               'content_hash': 'content', 'source_hash': 'source', 'current_value': i,
               'status': 'supported', 'reason': '已核对', 'evidences': [{'quote': f'quote {i}'}],
               'field_decision': {'actor_user_id': 2, 'action': 'approve'},
               'legacy_evidences': [shared], 'validation_record': shared} for i in range(200)]
    paper = SimpleNamespace(id=999, uploaded_by_user_id=1, content_revision=1)
    actor = SimpleNamespace(id=2, username='isolated-reviewer', role='superadmin')
    draft = {'paper': {}, 'material_states': [], '_field_change_events': [{'field': 'kept'}]}
    captured = {}
    monkeypatch.setattr(service, 'authorized_draft', lambda *a, **k: (draft, None))
    monkeypatch.setattr(service.ev, 'paper_snapshot', lambda *a, **k: {})
    monkeypatch.setattr(service.science, 'load_results', lambda *a, **k: {})
    monkeypatch.setattr(service.ev, 'resolve_results', lambda *a, **k: checks)
    monkeypatch.setattr(rag, '_validate_draft', lambda *a: None)

    async def record_history(session, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr(paper_history, 'append_paper_history_event', record_history)

    class Session:
        async def scalar(self, query): return paper
        async def run_sync(self, callback): return callback(None)
        async def execute(self, query): pass
        async def flush(self): pass

    body = SimpleNamespace(paper_id=999, evidence_job_id=None, expected_evidence_version='v1', comment='认可当前内容', review_request_id='isolated')
    result = asyncio.run(service.commit_review(Session(), body, actor))
    snapshot = captured['classification_snapshot']
    # 旧实现会逐字段复制上下文，使该样本超过 MySQL 64 MiB 单包上限。
    original_bytes = len(json.dumps({'evidence_review': checks}).encode())
    assert original_bytes > 64 * 1024 * 1024
    assert len(json.dumps(snapshot).encode()) < 2 * 1024 * 1024
    assert result['review_status'] == 'approved'
    assert snapshot['field_changes'] == draft['_field_change_events']
    assert len(snapshot['evidence_review']) == len(checks)
    pool = snapshot['history_contexts']['values']
    restored = []
    for stored in snapshot['evidence_review']:
        row = dict(stored)
        for name, key in row.pop('_history_context_refs', {}).items():
            row[name] = pool[key]
        restored.append(row)
    assert restored == checks
    assert checks[0]['legacy_evidences'] == [shared]
