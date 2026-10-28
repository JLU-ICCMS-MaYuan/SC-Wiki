"""提交来源衔接、审核迁移与不可变快照的回归。"""
from copy import deepcopy
import io
import json
import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from test_scientific_evidence_mysql import current_mysql

from backend.ingest.submission_sources import reviewed_legacy_targets
from backend.ingest.scientific_drafts import ScientificEvidenceTarget
from backend.ingest import scientific_evidence as science, property_evidence as ev
from backend.ingest.field_review import valid_field_decision


def reviewed(field, **extra):
    row = {'item_key': field, 'key': field, 'field': field, 'content_hash': 'value', 'source_hash': 'source',
           'status': 'supported', 'evidences': [], **extra}
    row['field_decision'] = {'contract': 'field-review-v2', 'action': 'approve', 'actor_user_id': 2,
                           'content_hash': row['content_hash'], 'source_hash': row['source_hash']}
    return row


def test_space_group_uses_current_confirmed_source_preserves_old_quote():
    field = 'material_states[0].reported_space_group'
    old = ScientificEvidenceTarget(field, {'quote': 'AI paraphrase not in paper'})
    row = reviewed(field + '_symbol', evidences=[{'file_id': 'si', 'quote': 'Table S2 P6/mmm'}])
    chunks = [{'file_id': 'si', 'chunk_index': 0, 'content': 'Table S2 P6/mmm', 'page_start': 9, 'page_end': 9}]
    result = reviewed_legacy_targets([old], [row], {}, chunks)
    assert result[0].evidence['quote'] == 'Table S2 P6/mmm'
    assert row['legacy_source_history'][0]['evidence'] == old.evidence
    assert reviewed_legacy_targets([old], None, {}, chunks) == [old]


def test_model_without_current_source_does_not_drop_a_second_bad_legacy_quote():
    field = 'material_states[0].reported_space_group'
    targets = [ScientificEvidenceTarget(field, {'quote': quote}) for quote in ('one', 'two')]
    row = reviewed(field + '_symbol'); row.pop('field_decision')
    assert reviewed_legacy_targets(targets, [row], {}, []) == targets


def test_structural_confirmation_does_not_forge_paper_evidence():
    key = science.item_identity('structure', 's1', 'structure-key')
    row = reviewed('structure_candidates[0].structure_text', item_key=key)
    target = ScientificEvidenceTarget('material_states[0].structure_candidates[c1]', {'quote': 'wrong table layout'},
                                      'structure', SimpleNamespace(review_key='structure-key'))
    assert reviewed_legacy_targets([target], [row], {'material_states': [{'state_key': 's1'}]}, []) == []
    assert row['legacy_source_history'][0]['status'] == 'historical_unlocated'


def test_source_transfer_requires_same_text_roles_and_value():
    before = [{'file_id': 'main', 'file_role': 'main', 'chunk_index': 0, 'content': 'True source'}]
    after = [{**before[0], 'file_id': '42', 'chunk_id': 7}]
    assert science.source_transfer_matches(before, after, {'main': 42})
    assert not science.source_transfer_matches(before, [{**after[0], 'file_role': 'supplementary'}], {'main': 42})
    assert not science.source_transfer_matches(before, [{**after[0], 'content': 'Different source'}], {'main': 42})
    record = {'item_key': 'field', 'key': 'field', 'field': 'paper.title', 'fields': ['paper.title'],
              'content_hash': 'value', 'source_hash': 'new-source', 'current_value': 'same'}
    previous = reviewed('paper.title', item_key='field', current_value='same')
    assert science.transfer_result(record, previous, after, {'main': 42})['status'] == 'unchecked'
    moved = science.transfer_result(record, previous, after, {'main': 42}, source_transfer_verified=True)
    assert valid_field_decision(record, moved, 'approve')
    assert moved['field_decision']['actor_user_id'] == 2
    assert moved['field_decision']['transferred_from']['source_hash'] == 'source'
    changed = {**record, 'content_hash': 'different-value'}
    assert science.transfer_result(changed, previous, after, {'main': 42}, source_transfer_verified=True)['status'] == 'unchecked'


def test_submitted_snapshot_does_not_conflict_with_original_or_retry(tmp_path, monkeypatch):
    from backend.api import rag
    from backend.ingest import upload_tasks as uploads
    from backend import storage
    from backend.storage import paths
    from backend.storage.files import LocalFileStorage
    task = '7' * 32
    store = LocalFileStorage(tmp_path / 'objects')
    initial = {'ai_values': {'paper': {'title': 'original AI'}}, 'user_values': {}}
    original_bytes = json.dumps(initial).encode()
    original_key = f'review_artifacts/{task}/result.json'
    old_ref = store.put(original_key, io.BytesIO(original_bytes), 'application/json')
    state = {'artifact_manifest': [{'logical_path': original_key, 'key': old_ref.key, 'sha256': old_ref.sha256,
                                   'size': old_ref.size, 'media_type': old_ref.media_type}]}
    destination = tmp_path / 'working.json'
    monkeypatch.setattr(paths, 'object_mode', lambda: True)
    monkeypatch.setattr(paths, 'create_storage', lambda **kw: store)
    monkeypatch.setattr(paths, '_cache_root', lambda namespace=None: tmp_path / 'cache')
    monkeypatch.setattr(storage, 'create_storage', lambda **kw: store)
    monkeypatch.setattr(uploads, 'get_state', lambda _: deepcopy(state))
    monkeypatch.setattr(uploads, 'artifact_path', lambda _: destination)
    monkeypatch.setattr(uploads, 'update_state', lambda _, **changes: state.update(changes))
    first = {'paper': {'title': 'confirmed user value'}}
    rag._record_submitted_upload(task, 271, first)
    new_key = uploads.submitted_artifact_key(task, 271, 1)
    ref = store.describe(new_key)
    assert store.describe(original_key) == old_ref
    # 即使缓存中的任务清单仍是原解析产物，已提交的不可变快照也能按论文版本找回。
    state.clear()
    rag._record_submitted_upload(task, 271, {'paper': {'title': 'stale retry input'}})
    assert store.describe(new_key) == ref
    with store.open(ref) as f: saved = json.load(f)
    assert saved['user_values'] == first
    found = rag._artifact_by_paper_id(271, task, 1)
    assert found and found[2] == saved
    # Redis 已清理后的终态收尾也必须读取送审版本，不能读到原解析对象。
    import asyncio
    state.clear()
    monkeypatch.setattr(rag, '_paper_review_context', lambda _: {
        'task_id': task, 'paper_id': 271, 'paper_revision': 1, 'review_status': 'approved'})
    cleaned = asyncio.run(rag.delete_paper_review_artifact(271, SimpleNamespace(role='admin')))
    assert cleaned['cleaned'] and store.list_prefix(f'review_artifacts/{task}/') == []


@pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅本机回滚测试')
@pytest.mark.parametrize('partial', [False, True])
def test_empty_manual_placeholder_is_history_but_partial_evidence_still_blocks(current_mysql, partial):
    from backend.ingest import manual_evidence as manual
    from backend.manual_evidence_models import ScientificManualEvidence
    target, identity = uuid4().hex, uuid4().hex
    record = {'item_key': 'a' * 64, 'field': 'paper.title', 'content_hash': '1' * 64, 'source_hash': '2' * 64}
    snapshot = {'target': 'upload', 'target_id': target, 'records': [record]}
    with current_mysql.begin() as session:
        row = ScientificManualEvidence(id=identity, target='upload', target_id=target, item_key=record['item_key'],
            baseline_hash='0' * 64, value_hash=record['content_hash'], source_hash=record['source_hash'],
            actor_user_id=7, reason='未完成的修改理由' if partial else '', no_evidence_reason='', items=[], status='draft')
        session.add(row); session.flush()
        if partial:
            with pytest.raises(manual.ManualEvidenceError):
                manual.transfer_to_paper(session, snapshot, snapshot, 271, 1, snapshot)
        else:
            manual.transfer_to_paper(session, snapshot, snapshot, 271, 1, snapshot)
            assert row.target == 'paper' and row.status == 'historical' and row.reason == ''


def test_scope_representation_change_does_not_cancel_approval_but_value_change_does():
    from backend.ingest.state_field_review import scope_matches
    old = {'state_review_context': {'pressure_value_gpa': 150.0, 'structure_optimization': 'sscha'}}
    assert scope_matches({'state_review_context': {'pressure_value_gpa': '150', 'structure_optimization': 'sscha'}}, old)
    assert not scope_matches({'state_review_context': {'pressure_value_gpa': '151', 'structure_optimization': 'sscha'}}, old)
