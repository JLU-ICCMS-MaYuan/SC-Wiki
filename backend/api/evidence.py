"""共享证据核对入口。后台任务只读科学数据，应用结果由原提交/审核事务负责。"""
import json
import hashlib
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from sqlalchemy import select
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
    candidates: dict[str, list[dict]] = Field(default_factory=dict)
    retry_keys: list[str] | None = None
    purpose: Literal['check', 'review_all'] = 'check'


def snapshot_for(body, user):
    from backend.ingest.pdf_source_pages import current_pdf_results
    if body.target == 'revision':
        from backend.services.paper_revisions import revision_snapshot
        with SessionLocal() as session:
            snapshot = revision_snapshot(session, body.target_id, user.id)
            return snapshot, current_pdf_results(session, snapshot, science.load_results(session, snapshot, user.id, include_stale=True))
    if body.target == 'upload':
        snapshot = ev.upload_snapshot(body.target_id, user.id)
        with SessionLocal() as session:
            return snapshot, current_pdf_results(session, snapshot, science.load_results(session, snapshot, user.id, include_stale=True))
    if body.target != 'paper' or not body.target_id.isdigit():
        raise HTTPException(400, detail='证据目标无效')
    with SessionLocal() as session:
        snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
        return snapshot, current_pdf_results(session, snapshot, science.load_results(session, snapshot, user.id, include_stale=True))


@router.post('/preflight')
def preflight(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
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
    manual_pending_keys = []
    if body.target in {'upload', 'revision'}:
        with SessionLocal() as session:
            if manual.table_available(session):
                _, baseline = _manual_snapshots(body.target, body.target_id, user)
                manual_pending_keys = sorted(manual.complete_keys(session, snapshot, baseline))
    return {**ev.public_snapshot(snapshot, cached), 'job_id': active_job,
            'manual_pending_keys': manual_pending_keys}


@router.post('/jobs')
def create_job(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
    if body.purpose == 'review_all' and (body.target != 'paper' or user.role not in {'admin', 'superadmin'}):
        raise HTTPException(403, detail='全量复核仅用于管理员论文审核')
    if body.expected_version != snapshot['version']:
        ev.fail('evidence_stale', '内容或来源已发生变化，请重新核对')
    retry_keys = set(body.retry_keys or [])
    if retry_keys - {r['key'] for r in snapshot['records']}:
        ev.fail('evidence_target_invalid', '重查项目不属于当前内容')
    by_item = {r['item_key']: r for r in snapshot['records']}
    for record in snapshot['records']:
        dependency = by_item.get(record.get('dependency'))
        if dependency and (record['key'] in retry_keys or dependency['key'] in retry_keys):
            retry_keys.update((record['key'], dependency['key']))
    prior = dict(cached)
    cached = {} if body.purpose == 'review_all' else {k: v for k, v in cached.items() if not v.get('stale') and k not in retry_keys and
              (v.get('status') != 'unchecked' or science.human_confirmed(v))}
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
    config = get_llm_config()
    if not config.api_key:
        ev.fail('evidence_model_config', '尚未配置模型，请先填写模型配置')
    job_id = uuid.uuid4().hex
    job = dict(id=job_id, owner=user.id, snapshot=snapshot, cached=cached, prior=prior, purpose=body.purpose,
               requested_keys=None if body.purpose == 'review_all' else sorted(retry_keys) or None, status='queued', progress='等待后台核对')
    redis_client().setex(ev.task_key(job_id), TASK_TTL, json.dumps(job, ensure_ascii=False, default=str))
    save_llm_config(job_id, config)
    try:
        upload_queue().enqueue(ev.run_evidence_job, job_id, job_id='evidence-'+job_id, job_timeout=1800, result_ttl=TASK_TTL, failure_ttl=TASK_TTL, on_failure=ev.evidence_job_failed)
    except Exception:
        from backend.ingest.upload_tasks import delete_llm_config
        delete_llm_config(job_id)
        ev.update_job(job_id, status='failed', error={'code': 'evidence_queue_error', 'message': '后台任务未能启动，请重试'})
        ev.fail('evidence_queue_error', '后台任务未能启动，请重试')
    return {'id': job_id, 'version': snapshot['version'], 'status': 'queued', 'timeout_seconds': 1800}


@router.get('/jobs/{job_id}')
def get_job(job_id: str, user=Depends(get_current_user)):
    job = ev.read_job(job_id, user.id)
    result = {k: job.get(k) for k in ('id', 'status', 'progress', 'error', 'completed_batches', 'total_batches', 'current_batch')}
    if job['status'] == 'completed':
        # 任务执行期间可能已有人工决定；以落库后的当前版本为准，不用任务快照覆盖它。
        snapshot, cached = snapshot_for(Target(target=job['snapshot']['target'], target_id=job['snapshot']['target_id']), user)
        result.update(ev.public_snapshot(snapshot, cached))
    return result


@router.post('/jobs/{job_id}/save-draft')
def save_upload_evidence_draft(job_id: str, user=Depends(get_current_user)):
    """将已完成的自动证据临时写回 Redis 草稿；不创建或修改正式论文。"""
    job = ev.read_job(job_id, user.id)
    if job.get('snapshot', {}).get('target') != 'upload':
        ev.fail('evidence_target_invalid', '只有上传草稿可以临时保存自动找到的证据')
    if job.get('status') != 'completed':
        ev.fail('evidence_task_not_complete', '证据核对尚未完成，暂时不能保存结果')
    ev.save_completed_upload(job['snapshot'], job['results'], user.id)
    return {'status': 'saved', 'version': job['snapshot']['version']}


@router.delete('/jobs/{job_id}')
def cancel_job(job_id: str, user=Depends(get_current_user)):
    ev.read_job(job_id, user.id)
    ev.update_job(job_id, status='cancelled')
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
        snapshot = ev.paper_snapshot(session, body.paper_id, user.id, user.role)
        manual_baseline = manual.paper_baseline(session, snapshot)
        manual_issues = manual.validate_submission(session, snapshot, manual_baseline)
        if manual_issues:
            ev.fail('manual_evidence_incomplete', '请补齐人工修改依据', issues=manual_issues)
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


def _manual_snapshots(target: str, target_id: str, user):
    if target not in {"upload", "revision", "paper"} or not target_id.isalnum():
        raise HTTPException(400, detail={"code": "manual_target_invalid", "message": "人工证据目标无效"})
    snapshot, _ = snapshot_for(Target(target=target, target_id=target_id), user)
    with SessionLocal() as session:
        if not manual.table_available(session):
            raise HTTPException(503, detail={"code": "manual_evidence_unavailable", "message": "人工证据存储尚未启用"})
    if target == "upload":
        from backend.rag.config import settings
        path = settings.sc_wiki_data_dir / "review_artifacts" / target_id / "result.json"
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


def _manual_record_key(item_key: str) -> str:
    if len(item_key) != 64 or any(ch not in "0123456789abcdef" for ch in item_key):
        raise HTTPException(400, detail={"code": "manual_field_invalid", "message": "字段身份无效"})
    return item_key


@router.get("/{target}/{target_id}/manual/{item_key}")
def get_manual_evidence(target: str, target_id: str, item_key: str, user=Depends(get_current_user)):
    snapshot, baseline = _manual_snapshots(target, target_id, user)
    try:
        with SessionLocal() as session:
            data = manual.read_field(session, snapshot, baseline, _manual_record_key(item_key))
        return {"ok": True, "data": data}
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc


@router.put("/{target}/{target_id}/manual/{item_key}")
def put_manual_evidence(target: str, target_id: str, item_key: str, body: ManualExplanation,
                        user=Depends(get_current_user)):
    snapshot, baseline = _manual_snapshots(target, target_id, user)
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
    snapshot, baseline = _manual_snapshots(target, target_id, user)
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
    snapshot, _ = _manual_snapshots(target, target_id, user)
    try:
        with SessionLocal() as session:
            _, entry, path = manual.file_entry(session, snapshot, _manual_record_key(item_key), item_id)
        background = BackgroundTask(path.unlink, missing_ok=True) if entry.get("storage_key") and manual.os.environ.get("FILE_STORAGE_BACKEND") == "s3" else None
        return FileResponse(path, media_type=entry["media_type"], filename=entry["filename"],
                            content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"},
                            background=background)
    except manual.ManualEvidenceError as exc:
        raise _manual_error(exc) from exc


@router.delete("/{target}/{target_id}/manual/{item_key}/files/{item_id}")
def delete_manual_evidence_file(target: str, target_id: str, item_key: str, item_id: str,
                                user=Depends(get_current_user)):
    snapshot, _ = _manual_snapshots(target, target_id, user)
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
