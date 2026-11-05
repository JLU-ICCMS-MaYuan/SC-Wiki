"""管理员暂存内容与批准在一个数据库事务中应用。"""
from backend.ingest.evidence_audit import current_change_events
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

from sqlalchemy import select, Text, String
from sqlalchemy.dialects.mysql import insert
from backend import models
from backend.ingest import scientific_evidence as science, property_evidence as ev
from backend.ingest.field_drafts import authorized_draft, draft_version


def review_history_snapshot(checks, draft):
    """旧来源与校验上下文按内容共享存储，保留全部信息及原字段审计结构。"""
    contexts, records = {}, []
    for check in checks:
        record, refs = dict(check), {}
        for name in ('legacy_evidences', 'validation_record'):
            if name not in record:
                continue
            value = record.pop(name)
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(',', ':'))
            key = sha256(encoded.encode()).hexdigest()
            contexts.setdefault(key, value)
            refs[name] = key
        if refs:
            record['_history_context_refs'] = refs
        records.append(record)
    return json.loads(json.dumps({'evidence_review': records,
        'history_contexts': {'version': 1, 'values': contexts},
        'field_changes': current_change_events(draft),
        'field_notes': draft.get('_review_notes_history') or []}, default=str))


async def commit_review(session, body, user):
    paper = await session.scalar(select(models.Paper).where(models.Paper.id == body.paper_id).with_for_update())
    if paper is None or user.role not in {'admin', 'superadmin'} or paper.uploaded_by_user_id == user.id:
        ev.fail('review_forbidden', '需要管理员权限且不能审核自己的论文')
    from backend.services import manuscript_handoffs as handoffs
    operation_id=body.review_request_id or __import__('uuid').uuid4().hex
    action='approve' if getattr(body,'status','approved')=='approved' else 'return' if body.status=='rejected' else 'forward'
    previous=await session.scalar(select(models.PaperHistoryEvent).where(models.PaperHistoryEvent.operation_id==operation_id))
    if previous is not None:
        saved=(previous.classification_snapshot or {}).get('handoff') or {}
        if previous.paper_id!=paper.id or previous.actor_user_id!=user.id or saved.get('action')!=action:
            ev.fail('handoff_operation_conflict','操作身份已用于其他交接')
        return {'ok':True,'paper_id':paper.id,'review_status':paper.review_status}
    if getattr(body,'status','approved')!='approved':
        result=await session.run_sync(lambda s:handoffs.review_handoff(s,paper,user,status=body.status,
            operation_id=operation_id,comment=body.comment))
        await session.flush()
        return {'ok':True,'paper_id':paper.id,'review_status':paper.review_status,'handoff':result}
    await session.run_sync(lambda s:handoffs.require_writer(s,paper,user))
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
        snapshot = ev.working_snapshot(formal, 'paper', str(paper.id), draft)
        snapshot['_field_change_events'] = current_change_events(draft)
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
        }, user, evidence_checks=checks)
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
                    field = record['field']
                    label = record.get('label') or field
                    ev.fail('draft_materialization_changed',
                        f'正式保存改变了字段「{label}」（{field}）的内容，事务已取消，输入保留',
                        issues=[{'field': field, 'message': '正式保存前后字段内容不一致'}])
                old = {'status': 'unchecked', 'evidences': []}
            rebound.append({**deepcopy(old), **record, 'status': old['status'],
                'evidences': deepcopy(old.get('evidences') or []), 'materialized_from': old.get('item_key')})
        checks = rebound
        await session.delete(staged)
    from backend.ingest.field_sources import compact_contexts
    for record in checks:
        packed = await session.run_sync(lambda sync: compact_contexts(sync, record))
        stmt = insert(models.ScientificEvidenceSource).values(paper_id=paper.id,
            paper_revision=paper.content_revision, item_key=record['item_key'], field_path=record['field'],
            content_hash=record['content_hash'], source_hash=record['source_hash'], rule_version=ev.RULE_VERSION,
            result=json.loads(json.dumps(packed, default=str)))
        await session.execute(stmt.on_duplicate_key_update(result=stmt.inserted.result,
            content_hash=stmt.inserted.content_hash, source_hash=stmt.inserted.source_hash))
    if draft.get('_spectrum_target_id'):
        from backend.services.spectra import bind_to_paper
        await bind_to_paper(session,paper,draft,target='revision',target_id=draft['_spectrum_target_id'],preserve_review=True)
    now = datetime.now(timezone.utc)
    paper.review_status, paper.approved_revision = 'approved', paper.content_revision
    paper.reviewed_by_user_id, paper.reviewed_at, paper.review_comment = user.id, now, body.comment
    frozen=await session.run_sync(lambda s:handoffs.capture(s,paper,draft,snapshot,checks))
    await session.run_sync(lambda s:handoffs.record_handoff(s,paper,user,action='approve',holder='published',
        operation_id=operation_id,comment=body.comment,**frozen))
    await session.flush()
    return {'ok': True, 'paper_id': paper.id, 'review_status': 'approved'}
