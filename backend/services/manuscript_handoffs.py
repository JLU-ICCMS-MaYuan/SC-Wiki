"""正式整稿交接：复用既有事件存储，工作稿不承担冻结历史。"""
from __future__ import annotations

from backend.ingest.evidence_audit import current_change_events
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import mimetypes
import json
from pathlib import Path
import uuid

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from backend import models

CONTRACT = 'manuscript-handoff-v1'
TRANSIENT = frozenset({'history', 'audit_events', 'legacy_evidences', 'validation_record',
    '_field_change_events', '_field_baselines', '_field_edit_format', '_spectrum_target_id', '_review_notes_history', 'review_started_at', 'detail_ref',
    'field_input_token', 'field_review_binding', 'stored_result', 'created_at', 'updated_at', '_structure_model_input'})


def error(code, message, status=409):
    raise HTTPException(status, detail={'code': code, 'message': message})


def current_content(value):
    """只比较/保存当前事实，不把中间审计、处理时间复制进快照。"""
    if isinstance(value, dict):
        return {k: current_content(v) for k, v in value.items() if k not in TRANSIENT}
    if isinstance(value, list):
        return [current_content(v) for v in value]
    return jsonable_encoder(value)


def content_hash(content):
    def comparison(value,path=()):
        if isinstance(value,dict):
            return {k:comparison(v,(*path,k)) for k,v in value.items() if v is not None and not (
                len(path)==2 and path[0]=='records' and k in {'content_hash','source_hash','paper_source_hash','state_review_context','empty_allowed','manual_evidence_hash','manual_evidence_complete','manual_evidence_provided'})}
        if isinstance(value,list):return [comparison(v,(*path,index)) for index,v in enumerate(value)]
        return value
    encoded = json.dumps(comparison(current_content(content)), sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def event_headers(session, paper_id, *, limit=None, offset=0, descending=False, current_read=False):
    # 列表只读取小型交接元数据，绝不随列表加载每个完整版本。
    query = select(models.PaperHistoryEvent.id, models.PaperHistoryEvent.occurred_at,
        models.PaperHistoryEvent.actor_user_id, models.PaperHistoryEvent.actor_username_snapshot,
        models.PaperHistoryEvent.classification_snapshot['handoff']).where(
            models.PaperHistoryEvent.paper_id == paper_id,
            models.PaperHistoryEvent.classification_snapshot['handoff']['contract'].as_string() == CONTRACT)
    if current_read:query=query.with_for_update(read=True)
    # MySQL filesort 可能复制完整底层JSON；这里只排序已投影的小型交接头。
    rows = sorted(session.execute(query).all(), key=lambda row: row[0], reverse=descending)
    if limit is not None: rows = rows[offset:offset + limit]
    return [dict(event_id=r[0], occurred_at=r[1], actor_user_id=r[2], actor_name=r[3], **r[4])
            for r in rows if isinstance(r[4], dict) and r[4].get('contract') == CONTRACT]


def latest(session, paper_id, *, current_read=False):
    headers = event_headers(session, paper_id, limit=1, descending=True,current_read=current_read)
    return headers[0] if headers else None


def readable(paper, user):
    if paper is None:
        error('paper_not_found', '论文不存在', 404)
    if user.id != paper.uploaded_by_user_id and user.role not in {'admin', 'superadmin'}:
        error('handoff_forbidden', '无权查看这份稿件的交接记录', 403)


def require_writer(session, paper, user, *, author=False, lock=False):
    if lock:
        from backend.services.workdrafts import lock_scope
        lock_scope(session, 'paper', str(paper.id))
    locked=lock or session.info.get('workdraft_locked_papers',{}).get(paper.id) is session.get_transaction() and session.get_transaction() is not None
    state = latest(session, paper.id,current_read=locked)
    if state is None:
        return  # 存量稿件沿原权限读取；只有正式交接才建立新合同，不在读页面时迁移。
    if author:
        allowed = state['holder'] == 'author' and user.id == paper.uploaded_by_user_id
    else:
        allowed = state['holder'] == 'review' and user.role in {'admin', 'superadmin'} and user.id != paper.uploaded_by_user_id
        if allowed:
            # 权限只读取属主，不为判断可编辑权加载整份科学稿。
            from backend.services.workdrafts import row
            work = row(session, 'paper', str(paper.id), locked)
            owner_query=select(models.ScientificReviewDraft.owner_id).where(models.ScientificReviewDraft.paper_id == paper.id)
            staged_owner = session.scalar(owner_query.with_for_update(read=True) if locked else owner_query)
            # 旧forward保留原经手人私稿；不再把已接手稿开放给下一审核员。
            legacy_owner = (state.get('action') == 'forward' and staged_owner is not None and work is not None
                and staged_owner == work.owner_id == state['actor_user_id'] == user.id)
            if state['actor_user_id'] == user.id and not legacy_owner:
                allowed = False
            queued_author = (state.get('action') == 'submit' and staged_owner is not None
                and staged_owner == state['actor_user_id'] == paper.uploaded_by_user_id)
            if (staged_owner is not None and staged_owner != user.id and not queued_author
                    or work is not None and work.document_key == str(state['event_id']) and work.owner_id != user.id):
                error('workdraft_claimed', '工作稿已由其他审核员接手；请查看正式快照')
    if not allowed:
        error('manuscript_handed_off', '稿件已交出，当前没有编辑权；须由其他合法经手人正式退回')


def snapshot_event(session, paper_id, snapshot_id):
    ids = list(session.scalars(select(models.PaperHistoryEvent.id).where(
        models.PaperHistoryEvent.paper_id == paper_id,
        models.PaperHistoryEvent.classification_snapshot['handoff']['snapshot_id'].as_string() == snapshot_id,
        models.PaperHistoryEvent.classification_snapshot['manuscript_snapshot'].is_not(None))))
    row = session.get(models.PaperHistoryEvent, min(ids)) if ids else None
    if row is None or not (row.classification_snapshot or {}).get('manuscript_snapshot'):
        error('snapshot_missing', '交接快照不存在', 404)
    return row


def _freeze_files(files):
    from backend.storage import create_storage
    from backend.storage.paths import resolve_file
    storage = create_storage()
    frozen = []
    for item in files:
        item = deepcopy(item)
        path = resolve_file(str(item['stored_path']), size=int(item.get('size') or 0),
            sha256=str(item.get('sha256') or ''), media_type=item.get('media_type') or 'application/octet-stream')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if item.get('sha256') and digest != item['sha256']:
            error('snapshot_source_changed', '快照依据文件与已核验来源不一致')
        suffix = Path(item.get('original_filename') or path.name).suffix.lower()
        key = f'manuscript_snapshots/files/{digest}{suffix}'
        with path.open('rb') as stream:
            ref = storage.put(key, stream, item.get('media_type') or 'application/octet-stream')
        item.update(stored_path=ref.key, size=ref.size, sha256=ref.sha256, media_type=ref.media_type)
        frozen.append(item)
    return frozen


def record_handoff(session, paper, user, *, action, draft, records, operation_id, files=(), manual=(),
                   holder='review', comment='', initial=False, spectra=None):
    """调用方持有论文行锁，并与业务修改处在同一事务内。"""
    from backend.ingest.parsing_workflows import require_workflow
    require_workflow(draft)
    if not operation_id or len(operation_id) > 64:
        error('handoff_operation_required', '正式交接需要有效的操作身份', 400)
    existing = session.scalar(select(models.PaperHistoryEvent).where(
        models.PaperHistoryEvent.operation_id == operation_id))
    if existing is not None:
        h = (existing.classification_snapshot or {}).get('handoff') or {}
        if existing.paper_id != paper.id or existing.actor_user_id != user.id or h.get('action') != action:
            error('handoff_operation_conflict', '本次操作身份已用于其他交接')
        return h
    previous = latest(session, paper.id,current_read=True)
    if not initial:
        require_writer(session, paper, user, author=action == 'submit', lock=True)
    from backend.ingest.tc_contexts import map_draft
    content = current_content({'draft': map_draft(draft,compact=True), 'records': records, 'manual': list(manual),
        'files': [{k: v for k, v in f.items() if k != 'stored_path'} for f in files], 'spectra':spectra})
    fingerprint = content_hash(content)
    reused = bool(previous and previous['content_hash'] == fingerprint)
    snapshot_id = previous['snapshot_id'] if reused else uuid.uuid4().hex
    number = previous['snapshot_number'] if reused else 1 + (previous['snapshot_number'] if previous else 0)
    public_id = (previous or {}).get('published_snapshot_id')
    if action == 'approve' or initial and previous is None and paper.review_status == 'approved':
        public_id = snapshot_id
    handoff = dict(contract=CONTRACT, action=action, snapshot_id=snapshot_id, snapshot_number=number,
        content_hash=fingerprint, reused=reused, holder=holder,
        receiver_user_id=paper.uploaded_by_user_id if holder == 'author' else None,
        receiver='原上传者' if holder == 'author' else '审核人员' if holder == 'review' else '公开批准版',
        published_snapshot_id=public_id, comment=comment)
    payload = {'handoff': handoff}
    if action=='submit' and initial:
        payload['upload_submission']={'paper':{k:(draft.get('paper') or {}).get(k)
            for k in ('material_families','co_first_authors','corresponding_authors')},
            'material_states':[{k:s.get(k) for k in ('state_key','structure_families')}
                               for s in draft.get('material_states') or []]}
        from backend.ingest.parsing_workflows import preserve_binding
        preserve_binding(payload['upload_submission'], draft)
    if not reused:
        from backend.ingest.field_sources import compact_contexts
        payload['manuscript_snapshot'] = compact_contexts(session,
            {**content, 'files': _freeze_files(files)}, keys={'legacy_evidences','legacy_source_history','sources'})
    event = models.PaperHistoryEvent(paper_id=paper.id, paper_revision=paper.content_revision,
        event_type='uploaded' if action == 'submit' and initial else 'reviewed',
        review_status=None if action == 'submit' and initial else
            'approved' if action == 'approve' else 'rejected' if holder == 'author' else 'pending',
        review_comment=None if action == 'submit' and initial else comment,
        actor_user_id=user.id, actor_username_snapshot=user.username,
        occurred_at=datetime.now(timezone.utc), operation_id=operation_id,
        classification_snapshot=payload)
    session.add(event)
    session.flush()
    if action=='submit' and initial and paper.upload_task_id:
        from backend.services.workdrafts import row
        upload_work=row(session,'upload',paper.upload_task_id,True)
        if upload_work is not None:
            upload_work.document_key='closed:'+str(event.id)
            upload_work.body={}  # 正式冻结成功且同事务提交后，关闭稿不再保留重复正文。
    return dict(handoff, event_id=event.id)


def paper_files(session, paper):
    return [dict(file_id=str(f.id), original_filename=f.original_filename, role=f.role,
                 kind=Path(f.original_filename).suffix.lstrip('.'),
                 stored_path=f.stored_path, size=f.size, sha256=f.sha256,
                 media_type=getattr(f, 'media_type', None) or mimetypes.guess_type(f.original_filename)[0] or 'application/octet-stream')
            for f in session.scalars(select(models.PaperFile).where(
                models.PaperFile.paper_id == paper.id, models.PaperFile.paper_revision == paper.content_revision))]


def capture(session, paper, draft, snapshot, checks):
    """冻结一份整稿及其当前字段资料，不复制旧总清单和中间回答。"""
    keys = {'key','item_key','field','fields','label','current_value','status','reason','ai_reason',
        'required','stale','pending_review','human_modified','human_confirmed','adopted_basis','source_kind',
        'evidences','supplemental_evidences','source_associations','provenance','content_hash','source_hash',
        'record_field','record_field_key','record_group_key','state_key','module_key','record_key',
        'structure_hash','structure_field','settings_field','settings_part','owner_label','check_mode','field_decision',
        'claim','state_review_context','paper_source_hash','association_review','rule_review',
        'manual_reason_review','manual_evidence_hash','manual_evidence_complete','manual_evidence_provided','empty_allowed','point_binding','condition_window','dependency_policy_version','record_dependencies','state_dependencies'}
    records = [{k:v for k,v in row.items() if k in keys} for row in checks]
    files, manual = paper_files(session,paper), []
    from backend.ingest.manual_evidence import ScientificManualEvidence, table_available
    if table_available(session):
        current={r['item_key']:r for r in snapshot['records']}
        candidates=list(session.scalars(select(ScientificManualEvidence).where(
                ScientificManualEvidence.target==snapshot['target'],
                ScientificManualEvidence.target_id==snapshot['target_id'],
                ScientificManualEvidence.status!='historical').order_by(ScientificManualEvidence.created_at,ScientificManualEvidence.id)))
        chosen={}
        for row in candidates:
            previous=chosen.get(row.item_key)
            if previous is None or row.status=='draft' or previous.status!='draft':chosen[row.item_key]=row
        for row in chosen.values():
            record=current.get(row.item_key)
            if not record or row.status!='draft' and row.value_hash!=record['content_hash']:
                continue
            items=deepcopy(row.items or [])
            for item in items:
                item.setdefault('submitted_by_user_id',row.actor_user_id)
                if item.get('kind')=='url':
                    cached=item.get('link_snapshot')
                    if cached:
                        source_id='manual-link-'+cached['sha256']
                        if not any(f['file_id']==source_id for f in files):
                            files.append(dict(file_id=source_id,original_filename='链接正文快照.txt',role='manual',
                                kind='text_file',stored_path=cached['storage_key'],sha256=cached['sha256'],
                                size=cached['size'],media_type='text/plain'))
                        item['file_id']=source_id
                    continue
                storage_key=item.pop('storage_key',None) or (f"manual_evidence/{row.id}/{item['id']}" if item.get('kind')!='text' else None)
                if storage_key:
                    source_id='manual-file-'+item['sha256']
                    if not any(f['file_id']==source_id for f in files):
                        files.append(dict(file_id=source_id,original_filename=item.get('filename') or source_id,
                            role='manual',kind=item['kind'],stored_path=storage_key,sha256=item['sha256'],
                            size=item['size'],media_type=item['media_type']))
                    item['file_id']=source_id
            manual.append(dict(item_key=row.item_key,reason=row.reason,no_evidence_reason=row.no_evidence_reason,
                               items=items,actor_user_id=row.actor_user_id))
    from backend.ingest.field_sources import compact
    records = [compact(session,snapshot,row,row) for row in records]
    from backend.services.manuscript_spectra import capture as capture_spectra
    frozen_spectra=capture_spectra(session,paper,draft,files)
    return dict(draft=draft,records=records,files=files,manual=manual,spectra=frozen_spectra)


def current_review_content(session, paper, user):
    from backend.ingest.field_drafts import authorized_draft
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    from backend.ingest.field_review import bind_support_versions
    draft,_=authorized_draft(session,'paper',str(paper.id),user,lock=True)
    formal=ev.paper_snapshot(session,paper.id,user.id,user.role)
    snapshot=ev.working_snapshot(formal,'paper',str(paper.id),draft)
    snapshot['_field_change_events']=current_change_events(draft)
    bind_support_versions(snapshot,session)
    cached=science.load_results(session,snapshot,user.id,include_stale=True)
    # 所有读取使用交接事务的会话，不另开连接读取尚未提交的旧稿。
    return capture(session,paper,draft,snapshot,ev.public_snapshot(snapshot,cached)['records'])


def review_handoff(session, paper, user, *, status, operation_id, comment=''):
    """拒绝是唯一返修入口；公开批准图保持，工作稿归属在调用方事务内交接。"""
    if user.role not in {'admin', 'superadmin'} or user.id == paper.uploaded_by_user_id:
        error('review_forbidden', '需要管理员权限且不能审核自己的论文', 403)
    if status != 'rejected':
        error('review_status_invalid', '无效的审核状态', 400)
    previous = session.scalar(select(models.PaperHistoryEvent).where(models.PaperHistoryEvent.operation_id == operation_id))
    action = 'return'
    if previous is not None:
        saved = (previous.classification_snapshot or {}).get('handoff') or {}
        if previous.paper_id != paper.id or previous.actor_user_id != user.id or saved.get('action') != action:
            error('handoff_operation_conflict', '操作身份已用于其他交接')
        return saved
    state = latest(session, paper.id, current_read=True)
    published = paper.review_status == 'approved' and paper.approved_revision == paper.content_revision and (
        state is None or state['holder'] == 'published')
    if published:
        if status != 'rejected':
            error('manuscript_handed_off', '已批准稿需要拒绝后由原上传者返修')
        if session.get(models.ScientificReviewDraft, paper.id) is not None:
            error('workdraft_claimed', '已有尚未交出的暂存稿，已保留；请先完成当前稿件处理')
        from backend.ingest import property_evidence as ev, scientific_evidence as science
        from backend.services.paper_revisions import current_draft
        snapshot = ev.paper_snapshot(session, paper.id, 0, '', check_access=False)
        cached = science.load_results(session, snapshot, user.id, include_stale=True)
        content = capture(session, paper, current_draft(session, paper), snapshot, ev.public_snapshot(snapshot, cached)['records'])
    else:
        require_writer(session, paper, user, lock=True)
        content = current_review_content(session, paper, user)
    result = record_handoff(session, paper, user, action=action, holder='author' if status == 'rejected' else 'review',
        operation_id=operation_id, comment=comment, initial=published, **content)
    if status == 'rejected':
        if paper.review_status != 'approved':
            paper.review_status, paper.review_comment = 'rejected', comment
        author_working_copy(session, paper, paper.uploaded_by_user_id, content['draft'], content['records'])
        staged = session.get(models.ScientificReviewDraft, paper.id)
        if staged is not None:
            session.delete(staged)
    session.flush()
    return result


def author_working_copy(session, paper, author_id, draft, records):
    """收到正式退回后建立可覆盖工作稿，不改公开正式内容或旧快照。"""
    from backend.services import paper_revisions
    from backend.ingest import property_evidence as ev, scientific_evidence as science
    from backend.ingest.field_review import bind_support_versions
    baseline_fingerprint=paper_revisions.fingerprint(session,paper)
    saved=session.get(models.PaperRevisionDraft,paper.id)
    if saved is None:
        saved=models.PaperRevisionDraft(paper_id=paper.id,owner_id=author_id)
        session.add(saved)
    saved.revision_id=uuid.uuid4().hex
    saved.base_revision=paper.content_revision
    from backend.ingest.tc_contexts import map_draft
    saved.draft=map_draft(draft,compact=True)
    spectrum_source=saved.draft.pop('_spectrum_target_id',None)
    saved.draft_version=1
    saved.submitted_revision=None
    saved.base_fingerprint=baseline_fingerprint
    session.flush()
    from backend.services.spectra import copy_to_revision_sync
    copy_to_revision_sync(session,paper,saved.revision_id,source_target='revision' if spectrum_source else 'paper',
        source_id=spectrum_source,preserve_review=True)
    formal=ev.paper_snapshot(session,paper.id,0,'',check_access=False)
    snapshot=ev.working_snapshot(formal,'revision',saved.revision_id,draft)
    snapshot['_field_change_events']=current_change_events(saved.draft)
    from backend.ingest.manual_evidence import ScientificManualEvidence,table_available
    if table_available(session):
        fields={r['item_key']:r for r in snapshot['records']}
        candidates=list(session.scalars(select(ScientificManualEvidence).where(
            ScientificManualEvidence.target=='paper',ScientificManualEvidence.target_id==str(paper.id),
            ScientificManualEvidence.status!='historical').order_by(ScientificManualEvidence.created_at,ScientificManualEvidence.id)))
        chosen={}
        for old in candidates:
            prior=chosen.get(old.item_key)
            if prior is None or old.status=='draft' or prior.status!='draft':chosen[old.item_key]=old
        for old in chosen.values():
            record=fields.get(old.item_key)
            if not record or old.status!='draft' and old.value_hash!=record['content_hash']:continue
            if old.status=='draft':
                old.target,old.target_id='revision',saved.revision_id
                old.source_hash=record.get('paper_source_hash',record['source_hash'])
                old.value_hash=record['content_hash'];old.after_value=deepcopy(record.get('current_value'))
            else:
                from backend.ingest.manual_evidence import _inherited_items
                data={c.name:deepcopy(getattr(old,c.name)) for c in old.__table__.columns
                      if c.name not in {'id','created_at','updated_at','target','target_id','paper_id','paper_revision'}}
                data.update(source_hash=record['source_hash'],items=_inherited_items(old),status='draft')
                session.add(ScientificManualEvidence(id=uuid.uuid4().hex,target='revision',
                    target_id=saved.revision_id,paper_id=paper.id,paper_revision=paper.content_revision,**data))
        session.flush()
    bind_support_versions(snapshot,session)
    from backend.ingest.field_sources import expand
    previous={r['item_key']:r for r in expand(session,records)}
    transferred={r['key']:science.transfer_result(r,previous[r['item_key']],snapshot['chunks'],
        source_transfer_verified=True) for r in snapshot['records'] if r['item_key'] in previous}
    snapshot['_handoff_transfer'] = True
    science.save_results(session,snapshot,transferred,author_id)
    from backend.ingest.field_source_metadata import remember
    remember(session,snapshot,author_id)
    session.flush()
    return saved


def public_snapshot(session, paper, user, snapshot_id):
    readable(paper, user)
    event = snapshot_event(session, paper.id, snapshot_id)
    from backend.ingest.field_sources import expand
    payload = expand(session,event.classification_snapshot['manuscript_snapshot'])
    from backend.ingest.tc_contexts import map_draft
    payload['draft'] = map_draft(payload['draft'])
    payload['files'] = [{k: v for k, v in f.items() if k != 'stored_path'} for f in payload['files']]
    return dict(snapshot_id=snapshot_id, snapshot_number=event.classification_snapshot['handoff']['snapshot_number'],
                content=payload)
