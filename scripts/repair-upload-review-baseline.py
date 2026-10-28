"""＃147 用户授权的一次性本机修正；默认只盘点，固定一个任务，不暴露普通 API。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = 'c16cc627a0c04dc8ad4289624d1da80a'
REPAIR = '147-lasch-approval-baseline-20261028-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')


def project(session, task_id, actor):
    from backend.ingest import field_source_metadata as meta, scientific_evidence as science
    from backend.ingest.field_review import bind_support_versions
    metadata = meta.read(session, 'upload', task_id)
    if not metadata:
        raise ValueError('缺少当前来源元数据，停止；本脚本不重新解析论文')
    snapshot, _ = meta.field_snapshot(session, 'upload', task_id, actor, None, metadata)
    bind_support_versions(snapshot, session)
    return snapshot, science.load_results(session, snapshot, actor.id, include_stale=True)


def inventory(snapshot, cached, state, draft):
    from backend.ingest.field_decisions import detail
    records = []
    for record in snapshot['records']:
        view = detail({**snapshot, 'records': [record]}, cached)
        current = view['record']
        # 冻结修复前的“稳定灰色”资格，不把修复后已可操作的待确认项漏掉。
        legacy_enabled = (view['can_approve'] and not current['pending_review'] and not current['stale']
                          and current['status'] in {'unsupported', 'uncertain', 'missing'})
        if not legacy_enabled:
            records.append({key: deepcopy(record.get(key)) for key in
                ('item_key', 'field', 'label', 'current_value', 'content_hash', 'source_hash', 'state_review_context')})
    return {'repair_id': REPAIR, 'target_id': snapshot['target_id'], 'version': snapshot['version'],
            'draft_hash': digest(draft), 'events_hash': digest(state.get('_field_change_events') or []),
            'checks_hash': digest(cached), 'records': records}


def apply_records(session, snapshot, cached, state, actor, selected):
    """仅在隔离测试或本脚本固定目标事务中调用；无外部数据覆盖字段值。"""
    from backend.ingest import scientific_evidence as science
    from backend.ingest.field_review import valid_field_decision
    from backend import models
    from sqlalchemy import select
    old_rows = list(session.scalars(select(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == snapshot['target'],
        models.ScientificEvidenceCheck.target_id == snapshot['target_id'],
        models.ScientificEvidenceCheck.item_key.in_(selected)).order_by(models.ScientificEvidenceCheck.id)))
    old_exact = {(r.item_key, r.content_hash, r.source_hash): r.result for r in old_rows}
    now = datetime.now(timezone.utc).isoformat()
    updated = deepcopy(state)
    events = updated.setdefault('_field_change_events', [])
    results = {}
    for record in snapshot['records']:
        if record['item_key'] not in selected:
            continue
        previous = cached.get(record['key']) or {}
        if (valid_field_decision(record, previous, 'approve')
                and (previous.get('field_decision') or {}).get('repair_id') == REPAIR):
            continue
        decision = {'contract': 'field-review-v2', 'action': 'approve', 'actor_user_id': actor.id,
            'actor_name': actor.username, 'occurred_at': now,
            'content_hash': record['content_hash'], 'source_hash': record['source_hash'],
            'authorization_origin': '用户明确授权修正本任务历史灰色状态；不是过去的按钮点击', 'repair_id': REPAIR}
        baseline = {'id': REPAIR + ':' + record['item_key'], 'kind': 'field_review_baseline',
            'repair_id': REPAIR, 'item_key': record['item_key'], 'field': record['field'], 'label': record['label'],
            'actor': {'kind': 'human', 'user_id': actor.id, 'name': actor.username}, 'occurred_at': now,
            'summary': '按用户当前授权确认现有内容并建立审核基线；保留此前修改历史',
            'before_value': science.canonical(record.get('current_value')), 'after_value': science.canonical(record.get('current_value')),
            'content_hash': record['content_hash'], 'source_hash': record['source_hash'], 'decision': decision}
        if not any(e.get('id') == baseline['id'] for e in events):
            events.append(baseline)
        result = {**deepcopy(previous), **record, 'status': 'supported', 'stale': False, 'pending_review': False,
            'human_modified': False, 'human_confirmed': True, 'field_decision': decision,
            'check_method': 'human', 'source_kind': previous.get('source_kind') or 'human_review',
            'machine_status': previous.get('machine_status', previous.get('status', 'unchecked')),
            'reason': previous.get('reason') or '', 'ai_reason': previous.get('ai_reason') or previous.get('reason') or '',
            'evidences': deepcopy(previous.get('evidences') or record.get('evidences') or []),
            'audit_events': [baseline],
            'resolved_generation_issue': deepcopy(record.get('generation_issue'))}
        # 同版本旧行可能会被 upsert；把原始结果留在历史，而不覆盖旧科学结论。
        prior_row = old_exact.get((record['item_key'], record['content_hash'], record['source_hash']), previous)
        result['history'] = [*deepcopy(prior_row.get('history', [])), {k: deepcopy(prior_row.get(k)) for k in
            ('current_value', 'status', 'reason', 'ai_reason', 'field_decision', 'content_hash', 'source_hash')}]
        results[record['key']] = result
    science.save_results(session, snapshot, results, actor.id, update_decision=True)
    updated.setdefault('_review_baseline_repairs', {}).setdefault(REPAIR, {
        'occurred_at': now, 'item_keys': sorted(selected), 'authorization': 'Issue #147 已确认 Spec，含理论子类型的一次性例外'})
    return updated, len(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='本机清单与备份目录')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    values = read_config(ROOT)
    validate_local(values, ROOT)
    os.environ.update(values)
    from sqlalchemy import select
    from backend import models
    from backend.database import SessionLocal
    from backend.ingest import upload_tasks as uploads, scientific_evidence as science
    from backend.ingest.field_review import valid_field_decision, changed_keys
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    client = uploads.redis_client()
    with uploads.upload_task_lock(TARGET), SessionLocal.begin() as session:
        state = json.loads(client.get(uploads.task_key(TARGET)) or '{}')
        draft = json.loads(client.get(uploads.draft_key(TARGET)) or '{}')
        if state.get('stage') != 'ready' or state.get('processing_status') != 'succeeded' or state.get('paper_id'):
            raise ValueError('任务不再是待提交的已解析草稿')
        user = session.get(models.User, int(state['user_id']))
        actor = SimpleNamespace(id=user.id, username=user.username, role=user.role)
        saved = session.get(models.ScientificUploadDraft, TARGET, with_for_update=True)
        if saved and REPAIR in (saved.state.get('_review_baseline_repairs') or {}):
            # 数据库提交后 Redis 同步中断时，仅在草稿和旧事件仍相同的条件下恢复缓存。
            persisted = saved.state
            prior_events = [e for e in persisted.get('_field_change_events', []) if e.get('repair_id') != REPAIR]
            if digest(saved.draft) != digest(draft) or (REPAIR not in state.get('_review_baseline_repairs', {})
                    and digest(prior_events) != digest(state.get('_field_change_events') or [])):
                raise ValueError('修正后出现新编辑，拒绝覆盖 Redis')
            if args.apply:
                expected = json.loads((directory / 'inventory.json').read_text())
                frozen = {r['item_key']: r for r in expected['records']}
                # 首次运行在末位浮点表示的回读断言中断时，用冻结清单恢复精确基线，绝不改科学值。
                corrected = deepcopy(persisted)
                for event in corrected.get('_field_change_events', []):
                    if event.get('repair_id') == REPAIR and event.get('kind') == 'field_review_baseline':
                        original = frozen[event['item_key']]
                        if any(event[k] != original[k] for k in ('content_hash', 'source_hash')):
                            raise ValueError('已保存基线不匹配冻结清单，停止恢复')
                        event['before_value'] = event['after_value'] = science.canonical(original['current_value'])
                saved.state = corrected
                session.commit()
                client.set(uploads.task_key(TARGET), json.dumps(corrected, ensure_ascii=False))
                with SessionLocal() as verify_session:
                    persisted = verify_session.get(models.ScientificUploadDraft, TARGET)
                    assert digest(persisted.state) == digest(json.loads(client.get(uploads.task_key(TARGET))))
                    assert digest(persisted.draft) == expected['draft_hash'] == digest(draft)
                    snap, cached = project(verify_session, TARGET, actor)
                    assert not (changed_keys(snap) & frozen.keys())
                    assert all(valid_field_decision(r, cached.get(r['key']), 'approve') for r in snap['records'] if r['item_key'] in frozen)
                result_path = directory / 'result.json'
                if not result_path.exists():
                    write_json(result_path, {'status': 'applied', 'repair_id': REPAIR, 'target_id': TARGET,
                        'fields': len(frozen), 'scientific_values_unchanged': True, 'old_events_preserved': True,
                        'storage_reread_equal': True, 'recovered_baseline_numeric_representation': True})
            print(json.dumps({'status': 'already_applied', 'repair_id': REPAIR}, ensure_ascii=False))
            return
        if saved and (digest(saved.draft) != digest(draft)
                      or digest(saved.state.get('_field_change_events') or []) != digest(state.get('_field_change_events') or [])):
            raise ValueError('Redis 与持久草稿不一致，停止修正以保留两份内容')
        job_id = state.get('evidence_job_id')
        if job_id:
            job = json.loads(client.get('evidence:' + job_id) or '{}')
            if job.get('status') in {'queued', 'running'}:
                raise ValueError('目标正在核对，请等待完成后重新盘点')
        snapshot, cached = project(session, TARGET, actor)
        current = inventory(snapshot, cached, state, draft)
        manifest = directory / 'inventory.json'
        if not args.apply:
            write_json(manifest, current)
            print(json.dumps({'status': 'inventoried', 'fields': len(current['records']), 'manifest': str(manifest)}, ensure_ascii=False))
            return
        expected = json.loads(manifest.read_text())
        if digest(current) != digest(expected):
            raise ValueError('目标内容、来源、审核或事件已变化，拒绝应用旧清单')
        checks = session.scalars(select(models.ScientificEvidenceCheck).where(
            models.ScientificEvidenceCheck.target == 'upload', models.ScientificEvidenceCheck.target_id == TARGET)).all()
        backup = {'repair_id': REPAIR, 'state': state, 'draft': draft,
            'persistent': {'state': saved.state, 'draft': saved.draft, 'owner_id': saved.owner_id} if saved else None,
            'checks': [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in checks]}
        backup_path = directory / 'before.json'
        write_json(backup_path, backup)
        write_json(directory / 'backup-sha256.json', {'before.json': hashlib.sha256(backup_path.read_bytes()).hexdigest()})
        selected = {r['item_key'] for r in expected['records']}
        updated, count = apply_records(session, snapshot, cached, state, actor, selected)
        science.persist_upload(session, TARGET, updated, draft)
        session.flush()
        verified_snapshot = {**snapshot, '_field_change_events': updated['_field_change_events']}
        checked = science.load_results(session, verified_snapshot, actor.id)
        assert all(valid_field_decision(r, checked.get(r['key']), 'approve') for r in snapshot['records'] if r['item_key'] in selected)
        assert not (changed_keys(verified_snapshot) & selected)
        assert updated['_field_change_events'][:len(state.get('_field_change_events', []))] == state.get('_field_change_events', [])
        session.commit()
        # 目标锁仍持有；保持草稿原始字节，Redis/持久状态均使用同一审核事件序列。
        client.set(uploads.task_key(TARGET), json.dumps({**updated, 'cleanup_at': None}, ensure_ascii=False))
        with SessionLocal() as verify_session:
            saved = verify_session.get(models.ScientificUploadDraft, TARGET)
            assert digest(saved.draft) == digest(draft)
            assert digest(saved.state) == digest(json.loads(client.get(uploads.task_key(TARGET))))
            assert digest(json.loads(client.get(uploads.draft_key(TARGET)))) == digest(draft)
        report = {'status': 'applied', 'repair_id': REPAIR, 'target_id': TARGET, 'fields': count,
            'scientific_values_unchanged': True, 'old_events_preserved': True, 'storage_reread_equal': True}
        write_json(directory / 'result.json', report)
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
