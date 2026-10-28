"""保存已读来源的版本元数据，使字段说明保存不再打开PDF或扫描旧历史。"""
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from backend import models
from . import property_evidence as ev, scientific_evidence as science

KEY = science.item_identity('field-source-metadata-v1')


def manifest(session, target, target_id):
    if target == 'upload':
        from .upload_tasks import get_state
        state = get_state(target_id) or {}
        files = state.get('files') or [{'file_id': 'main', 'sha256': state.get('file_sha256'), 'role': 'main'}]
        return [sorted((str(f['file_id']), f.get('role'), f.get('sha256'), f.get('extraction_status')) for f in files if f.get('role') in {'main', 'supplementary'}), state.get('parser_runs')]
    paper_id = int(target_id) if target == 'paper' else session.scalar(select(models.PaperRevisionDraft.paper_id).where(models.PaperRevisionDraft.revision_id == target_id))
    paper = session.get(models.Paper, paper_id)
    return sorted((str(f.id), f.role, f.sha256) for f in session.scalars(select(models.PaperFile).where(
        models.PaperFile.paper_id == paper_id, models.PaperFile.paper_revision == paper.content_revision,
        models.PaperFile.role.in_(['main', 'supplementary']))))


def remember(session, snapshot, actor):
    if not snapshot.get('_source_digest'):
        return
    token = ev.digest(manifest(session, snapshot['target'], snapshot['target_id']))
    metadata = {k: snapshot.get(k) for k in ('_source_digest', '_source_documents', '_source_expected', '_source_readable')}
    stmt = insert(models.ScientificEvidenceCheck).values(target=snapshot['target'], target_id=snapshot['target_id'],
        item_key=KEY, content_hash=token, source_hash=token, rule_version='field-source-metadata-v1',
        result=metadata, resolutions={}, actor_user_id=actor)
    session.execute(stmt.on_duplicate_key_update(result=stmt.inserted.result))


def read(session, target, target_id):
    token = ev.digest(manifest(session, target, target_id))
    return session.scalar(select(models.ScientificEvidenceCheck.result).where(
        models.ScientificEvidenceCheck.target == target, models.ScientificEvidenceCheck.target_id == target_id,
        models.ScientificEvidenceCheck.item_key == KEY, models.ScientificEvidenceCheck.content_hash == token,
        models.ScientificEvidenceCheck.source_hash == token))


def field_snapshot(session, target, target_id, user, item_key, metadata, *, draft_override=None):
    from .field_drafts import authorized_draft, draft_version
    draft, saved = authorized_draft(session, target, target_id, user)
    if draft_override is not None:
        draft = draft_override
    chunks = [{'file_id': file_id, 'content': '来源已读取', 'chunk_index': 0} for file_id in metadata.get('_source_readable') or []]
    context = {**draft, '_source_digest': metadata['_source_digest']}
    snapshot = ev.complete_snapshot(target, target_id, ev.draft_records(draft, {}), chunks, context, metadata_only=True)
    from .scientific_context import bind_snapshot_source_documents
    bind_snapshot_source_documents(snapshot, metadata.get('_source_documents') or {}, set(metadata.get('_source_expected') or []))
    if item_key is not None:
        snapshot['records'] = [r for r in snapshot['records'] if r['item_key'] == item_key]
    from .upload_tasks import get_state
    snapshot['_field_change_events'] = ((get_state(target_id) or {}).get('_field_change_events') or []) if target == 'upload' else draft.get('_field_change_events') or []
    # 说明与附件保存使用草稿版本；附件自身的变化不会让同批上传的下一份文件误判过期。
    snapshot['version'] = ev.digest([draft_version(draft), manifest(session, target, target_id)])
    if target == 'paper':
        paper = session.get(models.Paper, int(target_id))
        snapshot['review_state'] = [paper.review_status, str(paper.reviewed_at), paper.content_revision]
    baseline = {'records': []}
    for record in snapshot['records']:
        event = next((e for e in draft.get('_field_change_events') or [] if e.get('item_key') == item_key), None)
        if event:
            baseline['records'].append({**record, 'current_value': event.get('before_value')})
    return snapshot, baseline
