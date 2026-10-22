"""共享证据核对入口。后台任务只读科学数据，应用结果由原提交/审核事务负责。"""
import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_
from backend import models

from backend.database import SessionLocal
from backend.security import get_current_user, get_current_admin
from backend.rag.llm_context import request_llm_config, get_llm_config
from backend.ingest import property_evidence as ev
from backend.ingest import scientific_evidence as science
from backend.ingest import evidence_proposals as proposals
from backend.ingest import manual_evidence as manual
from backend.storage import FileRef, create_storage
from backend.ingest.upload_tasks import redis_client, upload_queue, save_llm_config, TASK_TTL, get_draft, get_state, save_draft, upload_task_lock

router = APIRouter(prefix='/api/rag/evidence', tags=['evidence'], dependencies=[Depends(request_llm_config)])


class Target(BaseModel):
    target: str
    target_id: str
    expected_version: str | None = None
    expected_draft_version: str | None = None
    candidates: dict[str, list[dict]] = Field(default_factory=dict)
    retry_keys: list[str] | None = None
    purpose: Literal['check', 'review_all', 'parse', 'submit', 'field'] = 'submit'


def review_response(snapshot, cached):
    from backend.ingest.field_review import compact_result
    result = ev.public_snapshot(snapshot, cached)
    by_key = {r['key']: r for r in result['records']}
    for record in result['records']:
        owners = (record.get('scope_review') or {}).get('required_keys') or []
        if owners and any(by_key.get(key, {}).get('status') != 'supported' for key in owners):
            record['pending_review'] = True
    return {'version': result['version'], 'needs_check': result['needs_check'],
            'records': [compact_result(r) for r in result['records']]}



class FieldDraftRequest(BaseModel):
    target: Literal['upload', 'revision', 'paper']
    target_id: str
    expected_version: str
    changes: list[dict] = Field(default_factory=list, max_length=5000)


class FieldLocator(Target):
    field: str
    state_key: str | None = None
    module_key: str | None = None
    record_key: str | None = None
    record_field_key: str | None = None
    structure_field: str | None = None
    structure_hash: str | None = None


@router.post('/identify-field')
def identify_field(body: FieldLocator, user=Depends(get_current_user)):
    import re
    from backend.ingest.field_drafts import authorized_draft
    from backend.ingest.field_review import independent_fields, compact_result
    from backend.ingest.property_field_review import expand_property_fields
    with SessionLocal() as session:
        draft, _ = authorized_draft(session, body.target, body.target_id, user)
    records = independent_fields(expand_property_fields(ev.draft_records(draft, {})))
    suffix = re.split(r'\.records\[\d+\]\.', body.field)[-1]
    matches = []
    for record in records:
        if body.structure_field:
            match = record.get('structure_field') == body.structure_field and record.get('structure_hash') == body.structure_hash
        elif body.record_key:
            match = all(record.get(k) == getattr(body, k) for k in ('state_key', 'module_key', 'record_key'))
            if body.record_field_key:
                match = match and record.get('record_field_key') == body.record_field_key and record.get('record_field', '').split('.')[-1] == suffix.split('.')[-1]
            else:
                match = match and record.get('record_field') == suffix
        elif body.state_key:
            match = record.get('state_key') == body.state_key and record['field'].split('].', 1)[-1] == body.field.split('].', 1)[-1]
        else:
            match = record['field'] == body.field
        if match:
            matches.append(record)
    if len(matches) != 1:
        ev.fail('evidence_field_missing', '字段已变化或无法唯一定位，请保留输入后重新打开')
    return {'record': compact_result({**matches[0], 'status': 'unchecked', 'reason': '', 'pending_review': True})}


@router.get('/draft-state')
def field_draft_state(target: str, target_id: str, user=Depends(get_current_user)):
    from backend.ingest.field_drafts import authorized_draft, draft_version
    with SessionLocal() as session:
        draft, saved = authorized_draft(session, target, target_id, user)
        return {'version': draft_version(draft), 'draft': draft, 'staged': isinstance(saved, models.ScientificReviewDraft)}


@router.patch('/draft')
def patch_field_draft(body: FieldDraftRequest, user=Depends(get_current_user)):
    from backend.ingest.field_drafts import target_lock, save_fields
    with target_lock(body.target, body.target_id), SessionLocal.begin() as session:
        return save_fields(session, body.target, body.target_id, user, body.expected_version, body.changes)


class FieldNote(BaseModel):
    target: Literal['upload', 'revision', 'paper']
    target_id: str
    item_key: str
    reason: str = Field(max_length=4000)
    before: str = ''


class FieldReviewCommit(BaseModel):
    paper_id: int
    evidence_job_id: str | None = None
    expected_evidence_version: str
    comment: str = ''
    review_request_id: str = Field(default='', max_length=64)


@router.post('/review-commit')
async def commit_field_review(body: FieldReviewCommit, user=Depends(get_current_admin)):
    from backend.rag.database import async_session_factory
    from backend.services.field_review_commit import commit_review
    async with async_session_factory() as session, session.begin():
        result = await commit_review(session, body, user)
    from backend.api.rag import publish_approved_paper
    try:
        await publish_approved_paper(body.paper_id, _current_user=user)
    except Exception:
        result['publication_pending'] = True
    return result


@router.put('/field-note')
def save_field_note(body: FieldNote, user=Depends(get_current_user)):
    from backend.ingest.field_drafts import target_lock, save_note
    with target_lock(body.target, body.target_id), SessionLocal.begin() as session:
        return save_note(session, body.target, body.target_id, user, _manual_record_key(body.item_key), body.reason, body.before)


@router.get('/field-detail')
def field_detail(target: str, target_id: str, item_key: str, history: bool = False, user=Depends(get_current_user)):
    from backend.ingest.field_drafts import authorized_draft
    with SessionLocal() as session:
        authorized_draft(session, target, target_id, user)
        table = models.ScientificEvidenceCheck
        targets = [and_(table.target == target, table.target_id == target_id)]
        if history and target == 'paper':
            paper = session.get(models.Paper, int(target_id))
            if paper.upload_task_id:
                targets.append(and_(table.target == 'upload', table.target_id == paper.upload_task_id))
            revisions = session.scalars(select(models.PaperRevisionDraft.revision_id).where(models.PaperRevisionDraft.paper_id == paper.id)).all()
            if revisions:
                targets.append(and_(table.target == 'revision', table.target_id.in_(revisions)))
        query = select(table).where(or_(*targets), table.item_key == item_key).order_by(table.id.desc())
        rows = list(session.scalars(query if history else query.limit(1)))
        if history:
            return {'history': [{**row.result, 'content_hash': row.content_hash, 'source_hash': row.source_hash} for row in rows]}
        result = dict(rows[0].result) if rows else {}
        result.pop('history', None)
        result.pop('audit_events', None)
        return {'record': result}


@router.post('/summary')
def field_summary(body: 'Target', user=Depends(get_current_user)):
    from sqlalchemy import func
    from backend.ingest.field_drafts import authorized_draft, draft_version
    from backend.ingest.field_review import independent_fields, compact_result
    from backend.ingest.property_field_review import expand_property_fields
    with SessionLocal() as session:
        draft, _ = authorized_draft(session, body.target, body.target_id, user)
        records = independent_fields(expand_property_fields(ev.draft_records(draft, {})))
        table = models.ScientificEvidenceCheck
        latest = select(func.max(table.id)).where(table.target == body.target,
            table.target_id == body.target_id).group_by(table.item_key)
        # 只投影摘要字段；MySQL不把数十MB历史和PDF原文送回应用。
        rows = session.execute(select(table.item_key, table.result['current_value'], table.result['status'],
            table.result['reason'], table.result['ai_reason'], table.result['source_kind']).where(table.id.in_(latest))).all()
        results = {row[0]: row for row in rows}
        from backend.ingest.field_review import changed_keys
        modified = changed_keys({'records': records, '_field_change_events': (get_state(body.target_id) or {}).get('_field_change_events') or []}) if body.target == 'upload' else changed_keys({'records': records, '_field_change_events': draft.get('_field_change_events') or []})
        output = []
        for record in records:
            row = results.get(record['item_key'])
            matches = row is not None and row[5] != 'human_review' and science.canonical(row[1]) == science.canonical(record.get('current_value'))
            output.append(compact_result({**record, 'status': row[2] if matches else 'unchecked',
                'reason': (row[3] or '') if row else '', 'ai_reason': (row[4] or '') if row else '',
                'pending_review': not matches, 'human_modified': record['item_key'] in modified, 'resolution': (draft.get('_review_notes', {}).get(record['item_key']) or {}).get('reason', '')}))
        return {'version': draft_version(draft), 'records': output, 'needs_check': False}




def snapshot_for(body, user):
    from backend.ingest.pdf_source_pages import current_pdf_results
    if body.target == 'revision':
        from backend.services.paper_revisions import revision_snapshot
        with SessionLocal() as session:
            snapshot = revision_snapshot(session, body.target_id, user.id)
            return snapshot, science.load_results(session, snapshot, user.id, include_stale=True)
    if body.target == 'upload':
        snapshot = ev.upload_snapshot(body.target_id, user.id)
        with SessionLocal() as session:
            return snapshot, science.load_results(session, snapshot, user.id, include_stale=True)
    if body.target != 'paper' or not body.target_id.isdigit():
        raise HTTPException(400, detail='证据目标无效')
    with SessionLocal() as session:
        snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
        staged = session.get(models.ScientificReviewDraft, int(body.target_id))
        if staged:
            from backend.ingest.field_drafts import authorized_draft
            draft, _ = authorized_draft(session, body.target, body.target_id, user)
            snapshot = {**snapshot, **ev.complete_snapshot('paper', body.target_id,
                ev.draft_records(draft, science.origins_for(session, 'paper', body.target_id)), snapshot['chunks'], draft)}
            snapshot['_field_change_events'] = draft.get('_field_change_events') or []
            from backend.ingest.field_review import bind_support_versions
            bind_support_versions(snapshot, session)
        return snapshot, science.load_results(session, snapshot, user.id, include_stale=True)


@router.post('/preflight')
def preflight(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
    from backend.ingest.field_review import deterministic_results
    cached.update({key: {**value, 'stored_result': True} for key, value in deterministic_results(snapshot).items()})
    active_job = None
    if body.target == 'upload':
        state = get_state(body.target_id) or {}
        candidate_id = state.get('evidence_job_id')
        if candidate_id:
            try:
                candidate = ev.read_job(candidate_id, user.id)
                if candidate.get('status') in {'queued', 'running'}:
                    active_job = candidate_id
            except Exception:
                pass
    return {**review_response(snapshot, cached), 'job_id': active_job}


@router.post('/jobs')
def create_job(body: Target, user=Depends(get_current_user)):
    # 摘要只承诺草稿版本，不能与包含来源的科学快照版本混用。
    if body.expected_draft_version is not None:
        from backend.ingest.field_drafts import authorized_draft, draft_version, target_lock
        with target_lock(body.target, body.target_id):
            with SessionLocal() as session:
                draft, _ = authorized_draft(session, body.target, body.target_id, user)
            if body.expected_draft_version != draft_version(draft):
                ev.fail('evidence_stale', '核对前草稿已发生变化，当前输入保留，请重新打开后核对')
            snapshot, cached = snapshot_for(body, user)
            snapshot['draft_version_token'] = body.expected_draft_version
            return enqueue_review(body.model_copy(update={'expected_version': snapshot['version']}), user, snapshot, cached)
    snapshot, cached = snapshot_for(body, user)
    return enqueue_review(body, user, snapshot, cached)


def enqueue_review(body, user, snapshot, cached):
    from backend.ingest.field_review import needs_review, reusable
    review_started_at = datetime.now(timezone.utc).isoformat()
    if body.purpose == 'review_all' and (body.target != 'paper' or user.role not in {'admin', 'superadmin'}):
        raise HTTPException(403, detail='全量复核仅用于管理员论文审核')
    if body.expected_version != snapshot['version']:
        ev.fail('evidence_stale', '内容或来源已发生变化，请重新核对')
    retry_keys = set(body.retry_keys or [])
    if retry_keys - {r['key'] for r in snapshot['records']}:
        ev.fail('evidence_target_invalid', '重查项目不属于当前内容')
    if body.purpose == 'field' and len(retry_keys) != 1:
        ev.fail('evidence_target_invalid', '主动核对必须指定一个字段')
    prior = dict(cached)
    cached = {r['key']: cached[r['key']] for r in snapshot['records']
              if reusable(r, cached.get(r['key'])) and r['key'] not in retry_keys}
    requested = retry_keys if body.purpose == 'field' else {
        r['key'] for r in snapshot['records'] if needs_review(r, cached.get(r['key']))}
    if not requested:
        return {'status': 'completed', **review_response(snapshot, cached)}
    if not snapshot.get('chunks') or snapshot.get('condition_source_manifest_complete') is False:
        ev.fail('evidence_source_incomplete', '正文或补充材料尚未读取完整，未启动模型核对，也未把缺失内容当成未报告')
    for record in snapshot['records']:
        if record['key'] in body.candidates:
            candidates = []
            for source in body.candidates[record['key']]:
                located, error = ev.locate_with_reason(source, snapshot['chunks'])
                if error:
                    ev.fail('evidence_invalid_source', record['label']+'：'+error, issues=[{'field': record['field'], 'message': error}])
                candidates.append(located)
            if not candidates:
                ev.fail('evidence_invalid_source', '请至少选择一条原文来源', issues=[{'field': record['field'], 'message': '没有选择原文来源'}])
            record['evidences'] = candidates
            cached.pop(record['key'], None)
    from backend.ingest.field_drafts import authorized_draft, draft_version
    with SessionLocal() as session:
        draft, _ = authorized_draft(session, body.target, body.target_id, user)
    if snapshot.get('draft_version_token') and snapshot['draft_version_token'] != draft_version(draft):
        ev.fail('evidence_stale', '构建核对依据期间草稿发生变化，未启动旧内容的核对')
    snapshot['draft_version_token'] = draft_version(draft)
    config = get_llm_config()
    if not config.api_key:
        ev.fail('evidence_model_config', '尚未配置模型，请先填写模型配置')
    client = redis_client()
    lock_keys = ['field-review-job:' + ev.digest([body.target, body.target_id, r['item_key'], r['content_hash'], r['source_hash']])
                 for r in snapshot['records'] if r['key'] in requested]
    job_id = uuid.uuid4().hex
    conflict = client.eval("""
        for _,key in ipairs(KEYS) do
            local owner = redis.call('get', key)
            if owner then return owner end
        end
        for _,key in ipairs(KEYS) do redis.call('set', key, ARGV[1], 'EX', ARGV[2]) end
        return ''
    """, len(lock_keys), *lock_keys, job_id, TASK_TTL)
    if conflict:
        try:
            previous = ev.read_job(conflict, user.id)
            if previous['status'] in {'queued', 'running'} and set(previous.get('requested_keys') or []) == requested:
                return {'id': previous['id'], 'version': snapshot['version'], 'status': previous['status']}
        except HTTPException:
            pass
        ev.fail('evidence_task_busy', '当前字段已有核对任务，未建立重复任务')
    job = dict(id=job_id, owner=user.id, snapshot=snapshot, cached=cached, prior=prior, purpose=body.purpose,
               review_started_at=review_started_at, lock_keys=lock_keys,
               requested_keys=sorted(requested), status='queued', progress='等待后台核对')
    client = redis_client()
    client.setex(ev.task_key(job_id), TASK_TTL, json.dumps(job, ensure_ascii=False, default=str))
    ev.write_job_control(job, client)
    save_llm_config(job_id, config)
    try:
        upload_queue().enqueue(ev.run_evidence_job, job_id, job_id='evidence-'+job_id, job_timeout=1800, result_ttl=TASK_TTL, failure_ttl=TASK_TTL, on_failure=ev.evidence_job_failed)
    except Exception:
        from backend.ingest.upload_tasks import delete_llm_config
        delete_llm_config(job_id)
        ev.release_field_jobs(client, {'id': job_id, 'lock_keys': lock_keys})
        ev.update_job(job_id, status='failed', error={'code': 'evidence_queue_error', 'message': '后台任务未能启动，请重试'})
        ev.fail('evidence_queue_error', '后台任务未能启动，请重试')
    return {'id': job_id, 'version': snapshot['version'], 'status': 'queued', 'timeout_seconds': 1800}


@router.post('/submit-check')
def submit_check(body: Target, user=Depends(get_current_user)):
    from backend.ingest.field_drafts import authorized_draft
    from backend.api.rag import _validate_draft
    with SessionLocal() as session:
        draft, _ = authorized_draft(session, body.target, body.target_id, user)
    try:
        _validate_draft(draft)
    except HTTPException as error:
        snapshot = ev.complete_snapshot(body.target, body.target_id, ev.draft_records(draft, {}), [], draft, metadata_only=True)
        cached = {}
        detail = error.detail if isinstance(error.detail, dict) else {'message': str(error.detail)}
        issues = detail.get('issues') or [{'field': detail.get('field') or {'title_required': 'paper.title', 'year_required': 'paper.year', 'paper_type_required': 'paper.paper_type'}.get(detail.get('code'), ''), 'message': detail.get('message') or '输入格式无效'}]
        program = {}
        for issue in issues:
            record = next((r for r in snapshot['records'] if r['field'] == issue.get('field')), None)
            if record:
                program[record['key']] = {**record, 'status': 'unsupported', 'source_kind': 'program',
                    'reason': '程序检查：' + str(issue.get('message') or '输入不符合要求'), 'evidences': [],
                    'stored_result': True}
        with SessionLocal.begin() as session:
            science.save_results(session, snapshot, program, user.id)
        return {'status': 'completed', **review_response(snapshot, {**cached, **program}), 'program_issues': issues}
    snapshot, cached = snapshot_for(body, user)
    from backend.ingest.field_review import deterministic_results
    cached.update({key: {**value, 'stored_result': True} for key, value in deterministic_results(snapshot).items()})
    from backend.ingest.field_review_migration import migrated, migrate
    with SessionLocal.begin() as session:
        if not migrated(session, snapshot):
            if body.target == 'upload':
                legacy = ev.upload_snapshot(body.target_id, user.id, legacy=True)
            elif body.target == 'revision':
                from backend.services.paper_revisions import revision_snapshot
                legacy = revision_snapshot(session, body.target_id, user.id, legacy=True)
            else:
                legacy = ev.paper_snapshot(session, int(body.target_id), user.id, user.role, legacy=True)
            migrate(session, snapshot, legacy, user.id)
            cached = science.load_results(session, snapshot, user.id, include_stale=True)
    from backend.ingest.field_review import prepare_submission
    snapshot, cached = prepare_submission(snapshot, cached)
    body.expected_version = snapshot['version']
    body.purpose = 'submit'
    body.retry_keys = None
    return enqueue_review(body, user, snapshot, cached)


@router.get('/jobs/{job_id}')
def get_job(job_id: str, user=Depends(get_current_user)):
    job = ev.read_job_status(job_id, user.id)
    result = {k: job.get(k) for k in ('id', 'status', 'progress', 'error', 'completed_batches', 'total_batches', 'current_batch')}
    if job['status'] == 'completed':
        stored = ev.read_job(job_id, user.id)
        from backend.ingest.field_drafts import authorized_draft, draft_version
        if not stored['snapshot'].get('draft_version_token'):
            snapshot, cached = snapshot_for(Target(target=stored['snapshot']['target'], target_id=stored['snapshot']['target_id']), user)
            result.update(review_response(snapshot, cached))
            return result
        with SessionLocal() as session:
            draft, _ = authorized_draft(session, stored['snapshot']['target'], stored['snapshot']['target_id'], user)
            if stored['snapshot'].get('draft_version_token') != draft_version(draft):
                ev.fail('evidence_stale', '核对期间内容发生变化，未提交；已经完成的有效结果保留')
            from backend.ingest.field_review import validate_support_versions
            validate_support_versions(stored['snapshot'], session)
            cached = science.load_results(session, stored['snapshot'], user.id)
        result.update(review_response(stored['snapshot'], {**stored.get('results', {}), **cached}))
    return result


@router.post('/jobs/{job_id}/save-draft')
def save_upload_evidence_draft(job_id: str, user=Depends(get_current_user)):
    """将已完成的自动证据临时写回 Redis 草稿；不创建或修改正式论文。"""
    job = ev.read_job(job_id, user.id)
    if job.get('snapshot', {}).get('target') != 'upload':
        ev.fail('evidence_target_invalid', '只有上传草稿可以临时保存自动找到的证据')
    if job.get('status') != 'completed':
        ev.fail('evidence_task_not_complete', '证据核对尚未完成，暂时不能保存结果')
    # 旧客户端兼容响应：结果已由任务持久化，不再为核对完成重写科学草稿。
    return {'status': 'saved', 'version': job['snapshot']['version']}


@router.delete('/jobs/{job_id}')
def cancel_job(job_id: str, user=Depends(get_current_user)):
    job = ev.read_job(job_id, user.id)
    ev.update_job(job_id, status='cancelled')
    ev.release_field_jobs(redis_client(), job)
    from backend.ingest.upload_tasks import delete_llm_config
    delete_llm_config(job_id)
    return {'status': 'cancelled'}


class PrepareReview(BaseModel):
    paper_id: int
    job_id: str | None = None
    expected_version: str | None = None
    resolutions: dict[str, str] = Field(default_factory=dict)
    classifications: dict | None = None


@router.post('/prepare-review')
def prepare_review(body: PrepareReview, user=Depends(get_current_admin)):
    with SessionLocal() as session:
        if session.get(models.ScientificReviewDraft, body.paper_id):
            ev.fail('review_staged_draft', '存在管理员草稿，请使用逐字段审核提交入口')
        snapshot = ev.paper_snapshot(session, body.paper_id, user.id, user.role)
        manual_baseline = manual.paper_baseline(session, snapshot)
        if body.classifications is not None:
            science.validate_review_classifications(session, body.paper_id, body.classifications)
        records = ev.resolve_results(snapshot, science.load_results(session, snapshot, user.id), user.id, body.job_id, body.expected_version)
        manual_ids = manual.current_ids(session, snapshot, manual_baseline)
        for record in records:
            if record['key'] in manual_ids:
                record['manual_evidence_id'] = manual_ids[record['key']]['id']
                record['manual_evidence_version'] = manual_ids[record['key']]['version']
            if not record.get('required', True):
                continue
            reason = body.resolutions.get(record['key'], record.get('resolution', '')).strip()
            if len(reason) > 4000:
                ev.fail('evidence_resolution_invalid', '人工裁决理由不能超过 4000 字')
            decision = record.get('decision') or {}
            if decision.get('actor_user_id') == user.id:
                reason = reason or decision.get('reason') or ('采纳经来源核对的 AI 建议' if decision.get('supported') else '')
            if record['status'] != 'supported' and not reason:
                ev.fail('evidence_review_required', '请逐条核对原文并填写人工裁决理由', records=records)
            record['resolution'] = reason
        # 计算应用候选后的缓存摘要，Go 同事务保存，下一次不重复调用模型。
        for r in records:
            original = next(x for x in snapshot['records'] if x['key'] == r['key'])
            r['source_hash'] = original['source_hash']
            r['content_hash'] = original['content_hash']
            r['rule_version'] = ev.RULE_VERSION
        return {'version': snapshot['version'], 'records': records}


class Resolutions(Target):
    resolutions: dict[str, str] = Field(default_factory=dict)


@router.post('/resolutions')
def persist_resolutions(body: Resolutions, user=Depends(get_current_admin)):
    if body.target != 'paper':
        ev.fail('evidence_target_invalid', '人工裁决仅用于论文审核')
    with SessionLocal.begin() as session:
        if not body.target_id.isdigit():
            raise HTTPException(400, detail='论文标识无效')
        session.scalar(select(models.Paper).where(models.Paper.id == int(body.target_id)).with_for_update())
        snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
        if body.expected_version != snapshot['version']:
            ev.fail('evidence_stale', '内容已变化，裁决草稿未保存')
        science.save_resolutions(session, snapshot, user.id, body.resolutions)
    return {'status': 'saved', 'version': snapshot['version']}


class ProposalDraft(Target):
    key: str
    values: dict = Field(default_factory=dict)
    accepted: bool = False
    reason: str = ''


class ProposalFinalization(Target):
    preparation_id: str


def proposal_operation(body, user, operation, require_version=True):
    # 上传与删除/提交共用目标锁；论文与既有编辑/批准共用行锁。
    from contextlib import nullcontext
    with upload_task_lock(body.target_id) if body.target == 'upload' else nullcontext():
        with SessionLocal.begin() as session:
            if body.target == 'paper' and body.target_id.isdigit():
                session.scalar(select(models.Paper).where(models.Paper.id == int(body.target_id)).with_for_update())
                snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
            elif body.target == 'revision':
                from backend.services.paper_revisions import revision_snapshot
                paper_id = session.scalar(select(models.PaperRevisionDraft.paper_id).where(models.PaperRevisionDraft.revision_id == body.target_id))
                if paper_id is not None:
                    session.scalar(select(models.Paper).where(models.Paper.id == paper_id).with_for_update())
                snapshot = revision_snapshot(session, body.target_id, user.id)
            elif body.target == 'upload':
                snapshot = ev.upload_snapshot(body.target_id, user.id)
            else:
                raise HTTPException(400, detail='证据目标无效')
            if require_version and body.expected_version != snapshot['version']:
                ev.fail('evidence_stale', '内容或来源已变化，请刷新后处理建议')
            return operation(session, snapshot)


@router.post('/proposals')
def save_proposal(body: ProposalDraft, user=Depends(get_current_user)):
    return proposal_operation(body, user, lambda session, snapshot: {
        'draft': proposals.save_draft(session, snapshot, user.id, body.key, body.values, body.accepted, body.reason),
        'version': snapshot['version']})


@router.post('/proposals/prepare')
def prepare_proposals(body: Target, user=Depends(get_current_user)):
    return proposal_operation(body, user, lambda session, snapshot: proposals.prepare(session, snapshot, user.id))


@router.post('/proposals/finalize')
def finalize_proposals(body: ProposalFinalization, user=Depends(get_current_user)):
    return proposal_operation(body, user, lambda session, snapshot: proposals.finalize(session, snapshot, user.id, body.preparation_id), False)


class ProposalSaveValidation(ProposalFinalization):
    stage: str = 'paper'


@router.post('/proposals/validate-save')
def validate_proposal_save(body: ProposalSaveValidation, user=Depends(get_current_admin)):
    # Go 已持有论文行锁，此接口只读，不能再次申请锁。
    snapshot, _ = snapshot_for(body, user)
    with SessionLocal() as session:
        proposals.validate_save(session, snapshot, user.id, body.preparation_id, body.stage)
    return {'status': 'valid'}


class RegionRequest(BaseModel):
    target: Literal["upload", "paper", "revision"]
    target_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    file_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    quote: str = Field(default="", max_length=10000)
    pdf_page: int | None = Field(default=None, ge=1)
    block_id: str | None = Field(default=None, min_length=1, max_length=255)


@router.post("/region")
def document_region(body: RegionRequest, user=Depends(get_current_user)):
    from backend.ingest.document_regions import region_document, render_region
    if not body.quote.strip() and not body.block_id:
        raise HTTPException(400, detail="必须提供原文引句或可靠的 PDF 区域身份")
    with SessionLocal() as session:
        ir, path, digest = region_document(session, body.target, body.target_id, body.file_id, user)
    return render_region(ir, path, digest, quote=body.quote, pdf_page=body.pdf_page, block_id=body.block_id)


class ManualTextItem(BaseModel):
    text: str = Field(min_length=1, max_length=manual.MAX_TEXT_CHARS)
    source_description: str = Field(min_length=1, max_length=200)


class ManualExplanation(BaseModel):
    expected_version: str
    reason: str = Field(default="", max_length=4000)
    no_evidence_reason: str = Field(default="", max_length=4000)
    text_items: list[ManualTextItem] = Field(default_factory=list, max_length=manual.MAX_ITEMS)


def _manual_error(exc: manual.ManualEvidenceError) -> HTTPException:
    return HTTPException(exc.status, detail={"code": exc.code, "message": str(exc), "field": exc.field})


def _manual_snapshots(target: str, target_id: str, user, item_key=None):
    if target not in {"upload", "revision", "paper"} or not target_id.isalnum():
        raise HTTPException(400, detail={"code": "manual_target_invalid", "message": "人工证据目标无效"})
    if item_key is not None:
        from backend.ingest.field_drafts import authorized_draft
        from backend.ingest.field_source_metadata import read, remember, field_snapshot
        with SessionLocal.begin() as session:
            authorized_draft(session, target, target_id, user)
            metadata = read(session, target, target_id)
            if metadata is None:
                # 旧数据首次访问建立来源元数据；以后只读版本，不加载正文和整篇历史。
                snapshot, _ = snapshot_for(Target(target=target, target_id=target_id), user)
                remember(session, snapshot, user.id)
                metadata = read(session, target, target_id)
            return field_snapshot(session, target, target_id, user, item_key, metadata)
    snapshot, _ = snapshot_for(Target(target=target, target_id=target_id), user)
    with SessionLocal() as session:
        if not manual.table_available(session):
            raise HTTPException(503, detail={"code": "manual_evidence_unavailable", "message": "人工证据存储尚未启用"})
    if target == "upload":
        from backend.ingest.upload_tasks import available_published_path, artifact_path

        path = available_published_path(target_id, artifact_path(target_id))
        artifact = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        ai_values = artifact.get("ai_values")
        baseline = ev.upload_snapshot(target_id, user.id, parsing_draft=ai_values) if isinstance(ai_values, dict) else {"records": []}
    elif target == "revision":
        with SessionLocal() as session:
            paper_id = session.scalar(select(models.PaperRevisionDraft.paper_id).where(
                models.PaperRevisionDraft.revision_id == target_id))
            baseline = ev.paper_snapshot(session, int(paper_id), user.id, user.role, check_access=False) if paper_id else {"records": []}
    else:
        with SessionLocal() as session:
            baseline = manual.paper_baseline(session, snapshot)
    return snapshot, baseline


@router.get('/manual-context')
def manual_context(target: str, target_id: str, item_key: str, user=Depends(get_current_user)):
    snapshot, _ = _manual_snapshots(target, target_id, user, _manual_record_key(item_key))
    return {'version': snapshot['version'], 'record': snapshot['records'][0] if snapshot['records'] else None}


def _manual_record_key(item_key: str) -> str:
    if len(item_key) != 64 or any(ch not in "0123456789abcdef" for ch in item_key):
        raise HTTPException(400, detail={"code": "manual_field_invalid", "message": "字段身份无效"})
    return item_key


@router.get("/{target}/{target_id}/manual/{item_key}")
def get_manual_evidence(target: str, target_id: str, item_key: str, user=Depends(get_current_user)):
    snapshot, baseline = _manual_snapshots(target, target_id, user, item_key)
    try:
        with SessionLocal() as session:
            data = manual.read_field(session, snapshot, baseline, _manual_record_key(item_key), include_history=False)
        return {"ok": True, "data": data}
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc


@router.put("/{target}/{target_id}/manual/{item_key}")
def put_manual_evidence(target: str, target_id: str, item_key: str, body: ManualExplanation,
                        user=Depends(get_current_user)):
    snapshot, baseline = _manual_snapshots(target, target_id, user, item_key)
    if body.expected_version != snapshot["version"]:
        raise HTTPException(409, detail={"code": "manual_evidence_stale", "message": "字段或来源已变化，请刷新后重新填写"})
    try:
        with SessionLocal.begin() as session:
            data = manual.save_explanation(session, snapshot, baseline, _manual_record_key(item_key), user.id,
                reason=body.reason, no_evidence_reason=body.no_evidence_reason,
                text_items=[item.model_dump() for item in body.text_items], actor_name=user.username)
        return {"ok": True, "data": data}
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc


@router.post("/{target}/{target_id}/manual/{item_key}/files")
async def post_manual_evidence_file(target: str, target_id: str, item_key: str,
                                    expected_version: str = Form(...), source_description: str = Form(""),
                                    file: UploadFile = File(...), user=Depends(get_current_user)):
    snapshot, baseline = _manual_snapshots(target, target_id, user, item_key)
    if expected_version != snapshot["version"]:
        raise HTTPException(409, detail={"code": "manual_evidence_stale", "message": "字段或来源已变化，请刷新后重新上传"})
    try:
        raw = await file.read(manual.MAX_FILE_BYTES + 1)
    finally:
        await file.close()
    data = None
    try:
        with SessionLocal.begin() as session:
            data = manual.add_file(session, snapshot, baseline, _manual_record_key(item_key), user.id,
                                   filename=file.filename or "", raw=raw, source_description=source_description,
                                   actor_name=user.username)
        return {"ok": True, "data": data}
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc
    except Exception:
        if data and data.get("items"):
            entry = data["items"][-1]
            create_storage(local_root=manual.settings.sc_wiki_data_dir).delete(manual._file_ref(data["id"], entry))
        raise


@router.get("/{target}/{target_id}/manual/{item_key}/files/{item_id}")
def get_manual_evidence_file(target: str, target_id: str, item_key: str, item_id: str,
                             user=Depends(get_current_user)):
    snapshot, _ = _manual_snapshots(target, target_id, user, item_key)
    try:
        with SessionLocal() as session:
            _, entry, path = manual.file_entry(session, snapshot, _manual_record_key(item_key), item_id)
        background = BackgroundTask(path.unlink, missing_ok=True) if manual.os.environ.get("FILE_STORAGE_BACKEND") == "s3" else None
        return FileResponse(path, media_type=entry["media_type"], filename=entry["filename"],
                            content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"},
                            background=background)
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc


@router.delete("/{target}/{target_id}/manual/{item_key}/files/{item_id}")
def delete_manual_evidence_file(target: str, target_id: str, item_key: str, item_id: str,
                                user=Depends(get_current_user)):
    snapshot, _ = _manual_snapshots(target, target_id, user, item_key)
    try:
        with SessionLocal.begin() as session:
            path = manual.remove_file(session, snapshot, _manual_record_key(item_key), item_id, user.id)
        if isinstance(path, FileRef):
            create_storage(local_root=manual.settings.sc_wiki_data_dir).delete(path)
        else:
            path.unlink(missing_ok=True)
        return {"ok": True}
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc
