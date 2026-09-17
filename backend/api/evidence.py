"""共享证据核对入口。后台任务只读科学数据，应用结果由原提交/审核事务负责。"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend import models

from backend.database import SessionLocal
from backend.security import get_current_user, get_current_admin
from backend.rag.llm_context import request_llm_config, get_llm_config
from backend.ingest import property_evidence as ev
from backend.ingest import scientific_evidence as science
from backend.ingest import evidence_proposals as proposals
from backend.ingest.upload_tasks import redis_client, upload_queue, save_llm_config, TASK_TTL, get_draft, save_draft, upload_task_lock

router = APIRouter(prefix='/api/rag/evidence', tags=['evidence'], dependencies=[Depends(request_llm_config)])


class Target(BaseModel):
    target: str
    target_id: str
    expected_version: str | None = None
    candidates: dict[str, list[dict]] = Field(default_factory=dict)
    retry_keys: list[str] | None = None


def snapshot_for(body, user):
    if body.target == 'upload':
        snapshot = ev.upload_snapshot(body.target_id, user.id)
        with SessionLocal() as session:
            return snapshot, science.load_results(session, snapshot, user.id, include_stale=True)
    if body.target != 'paper' or not body.target_id.isdigit():
        raise HTTPException(400, detail='证据目标无效')
    with SessionLocal() as session:
        snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
        return snapshot, science.load_results(session, snapshot, user.id, include_stale=True)


@router.post('/preflight')
def preflight(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
    return {**ev.public_snapshot(snapshot, cached), 'job_id': None}


@router.post('/jobs')
def create_job(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
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
    cached = {k: v for k, v in cached.items() if not v.get('stale') and k not in retry_keys and
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
    job = dict(id=job_id, owner=user.id, snapshot=snapshot, cached=cached, requested_keys=sorted(retry_keys) or None, status='queued', progress='等待后台核对')
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
        if body.classifications is not None:
            science.validate_review_classifications(session, body.paper_id, body.classifications)
        records = ev.resolve_results(snapshot, science.load_results(session, snapshot, user.id), user.id, body.job_id, body.expected_version)
        for record in records:
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
