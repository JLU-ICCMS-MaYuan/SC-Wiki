"""管理员暂存内容与批准在一个数据库事务中应用。"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from sqlalchemy import select, Text, String
from sqlalchemy.dialects.mysql import insert
from backend import models
from backend.ingest import scientific_evidence as science, property_evidence as ev
from backend.ingest.field_drafts import authorized_draft, draft_version


async def commit_review(session, body, user):
    paper = await session.scalar(select(models.Paper).where(models.Paper.id == body.paper_id).with_for_update())
    if paper is None or user.role not in {'admin', 'superadmin'} or paper.uploaded_by_user_id == user.id:
        ev.fail('review_forbidden', '需要管理员权限且不能审核自己的论文')
    draft, staged = await session.run_sync(lambda sync: authorized_draft(sync, 'paper', str(paper.id), user, lock=True))
    from backend.api.evidence import Target, snapshot_for
    # 同一事务的正式论文行锁阻止其他管理员完成提交；局部保存也按论文→暂存行顺序加锁。
    formal = await session.run_sync(lambda sync: ev.paper_snapshot(sync, paper.id, user.id, user.role))
    snapshot = formal
    if isinstance(staged, models.ScientificReviewDraft):
        from backend.services.paper_revisions import current_draft
        baseline = await session.run_sync(lambda sync: current_draft(sync, paper))
        if draft_version(baseline) != staged.base_fingerprint:
            ev.fail('draft_version_conflict', '正式论文已被其他操作修改，未覆盖当前内容')
        snapshot = {**formal, **ev.complete_snapshot('paper', str(paper.id),
            ev.draft_records(draft, {}), formal['chunks'], draft)}
        snapshot['_field_change_events'] = draft.get('_field_change_events') or []
        from backend.ingest.field_review import bind_support_versions
        await session.run_sync(lambda sync: bind_support_versions(snapshot, sync))
    cached = await session.run_sync(lambda sync: science.load_results(sync, snapshot, user.id, include_stale=True))
    checks = ev.resolve_results(snapshot, cached, user.id, body.evidence_job_id, body.expected_evidence_version)
    from backend.api.rag import _validate_draft, _rewrite_paper_scientific_draft_in_tx
    _validate_draft(draft)
    if isinstance(staged, models.ScientificReviewDraft):
        columns = {c.name: c for c in models.Paper.__table__.columns}
        for key in science.PAPER_FIELDS:
            if key not in columns or key not in draft['paper']:
                continue
            value = draft['paper'][key]
            if isinstance(value, (dict, list)) and isinstance(columns[key].type, (Text, String)):
                value = json.dumps(value, ensure_ascii=False)
            setattr(paper, key, value)
        await session.flush()
        await _rewrite_paper_scientific_draft_in_tx(session, paper.id, {
            **draft, 'paper_type': draft['paper']['paper_type'],
            'superconductor_kind': draft['paper'].get('superconductor_kind'),
            'material_families': draft['paper'].get('material_families') or [],
        }, user)
        current = await session.run_sync(lambda sync: ev.paper_snapshot(sync, paper.id, user.id, user.role))
        previous = {r['field']: r for r in checks}
        rebound = []
        for record in current['records']:
            old = previous.get(record['field'])
            if old is None and record.get('structure_field'):
                old = next((r for r in checks if r.get('structure_hash') == record.get('structure_hash')
                    and r.get('structure_field') == record['structure_field'] and r.get('state_key') == record.get('state_key')), None)
            if not old or science.canonical(record.get('current_value')) != science.canonical(old.get('current_value')):
                if record.get('required', True):
                    ev.fail('draft_materialization_changed', '正式保存改变了字段内容，事务已取消，输入保留')
                old = {'status': 'unchecked', 'evidences': []}
            rebound.append({**deepcopy(old), **record, 'status': old['status'],
                'evidences': deepcopy(old.get('evidences') or []), 'materialized_from': old.get('item_key')})
        checks = rebound
        await session.delete(staged)
    for record in checks:
        stmt = insert(models.ScientificEvidenceSource).values(paper_id=paper.id,
            paper_revision=paper.content_revision, item_key=record['item_key'], field_path=record['field'],
            content_hash=record['content_hash'], source_hash=record['source_hash'], rule_version=ev.RULE_VERSION,
            result=json.loads(json.dumps(record, default=str)))
        await session.execute(stmt.on_duplicate_key_update(result=stmt.inserted.result,
            content_hash=stmt.inserted.content_hash, source_hash=stmt.inserted.source_hash))
    now = datetime.now(timezone.utc)
    paper.review_status, paper.approved_revision = 'approved', paper.content_revision
    paper.reviewed_by_user_id, paper.reviewed_at, paper.review_comment = user.id, now, body.comment
    from backend.services.paper_history import append_paper_history_event
    await append_paper_history_event(session, paper_id=paper.id, paper_revision=paper.content_revision,
        event_type='reviewed', actor_user_id=user.id, actor_username_snapshot=user.username,
        operation_id=body.review_request_id or None, review_status='approved', review_comment=body.comment,
        occurred_at=now, classification_snapshot=json.loads(json.dumps({'evidence_review': checks, 'field_changes': draft.get('_field_change_events') or [], 'field_notes': draft.get('_review_notes_history') or []}, default=str)))
    await session.flush()
    return {'ok': True, 'paper_id': paper.id, 'review_status': 'approved'}
