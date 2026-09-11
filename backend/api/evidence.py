"""共享证据核对入口。后台任务只读科学数据，应用结果由原提交/审核事务负责。"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.database import SessionLocal
from backend.security import get_current_user, get_current_admin
from backend.rag.llm_context import request_llm_config, get_llm_config
from backend.ingest import property_evidence as ev
from backend.ingest.upload_tasks import redis_client, upload_queue, save_llm_config, TASK_TTL, get_draft, save_draft, upload_task_lock

router = APIRouter(prefix='/api/rag/evidence', tags=['evidence'], dependencies=[Depends(request_llm_config)])


class Target(BaseModel):
    target: str
    target_id: str
    expected_version: str | None = None
    candidates: dict[str, list[dict]] = Field(default_factory=dict)


def snapshot_for(body, user):
    if body.target == 'upload':
        return ev.upload_snapshot(body.target_id, user.id), {}
    if body.target != 'paper' or not body.target_id.isdigit():
        raise HTTPException(400, detail='证据目标无效')
    with SessionLocal() as session:
        snapshot = ev.paper_snapshot(session, int(body.target_id), user.id, user.role)
        return snapshot, ev.cached_results(session, snapshot)


@router.post('/preflight')
def preflight(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
    job_id, recent = ev.transient_results(snapshot, user.id)
    return {**ev.public_snapshot(snapshot, {**cached, **recent}), 'job_id': job_id}


@router.post('/jobs')
def create_job(body: Target, user=Depends(get_current_user)):
    snapshot, cached = snapshot_for(body, user)
    if body.expected_version != snapshot['version']:
        ev.fail('evidence_stale', '内容或来源已发生变化，请重新核对')
    _, recent = ev.transient_results(snapshot, user.id)
    cached = {k: v for k, v in {**cached, **recent}.items() if v['status'] == 'supported'}
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
    job = dict(id=job_id, owner=user.id, snapshot=snapshot, cached=cached, status='queued', progress='等待后台核对')
    redis_client().setex(ev.task_key(job_id), TASK_TTL, json.dumps(job, ensure_ascii=False, default=str))
    save_llm_config(job_id, config)
    try:
        upload_queue().enqueue(ev.run_evidence_job, job_id, job_id='evidence-'+job_id, job_timeout=600, result_ttl=TASK_TTL, failure_ttl=TASK_TTL, on_failure=ev.evidence_job_failed)
    except Exception:
        from backend.ingest.upload_tasks import delete_llm_config
        delete_llm_config(job_id)
        ev.update_job(job_id, status='failed', error={'code': 'evidence_queue_error', 'message': '后台任务未能启动，请重试'})
        ev.fail('evidence_queue_error', '后台任务未能启动，请重试')
    return {'id': job_id, 'version': snapshot['version'], 'status': 'queued'}


@router.get('/jobs/{job_id}')
def get_job(job_id: str, user=Depends(get_current_user)):
    job = ev.read_job(job_id, user.id)
    result = {k: job.get(k) for k in ('id', 'status', 'progress', 'error', 'completed_batches', 'total_batches', 'current_batch')}
    if job['status'] == 'completed':
        result['records'] = [ev.checked_result(r, job['results'][r['key']], job['snapshot']['chunks']) for r in job['snapshot']['records']]
    return result


@router.post('/jobs/{job_id}/save-draft')
def save_upload_evidence_draft(job_id: str, user=Depends(get_current_user)):
    """将已完成的自动证据临时写回 Redis 草稿；不创建或修改正式论文。"""
    job = ev.read_job(job_id, user.id)
    if job.get('snapshot', {}).get('target') != 'upload':
        ev.fail('evidence_target_invalid', '只有上传草稿可以临时保存自动找到的证据')
    if job.get('status') != 'completed':
        ev.fail('evidence_task_not_complete', '证据核对尚未完成，暂时不能保存结果')
    task_id = job['snapshot']['target_id']
    with upload_task_lock(task_id):
        draft = get_draft(task_id)
        state = job['snapshot']
        if draft is None:
            ev.fail('draft_not_ready', '上传草稿不存在或已过期')
        from backend.ingest.scientific_drafts import _property_modules_for_state
        draft = json.loads(json.dumps(draft, ensure_ascii=False))
        for result_key, result in job.get('results', {}).items():
            if result.get('status') == 'missing':
                continue
            record = next((r for r in job['snapshot']['records'] if r['key'] == result_key), None)
            if record is None:
                continue
            state_data = draft['material_states'][record['state_index']]
            modules = _property_modules_for_state(state_data)
            state_data['property_modules'] = modules
            module = next((m for m in modules if m.get('module_key') == record['module_key']), None)
            if module is None:
                continue
            target = next((r for r in module.get('records', []) if r.get('record_key') == record['record_key']), None)
            if target is not None:
                target.pop('evidence', None)
                target['evidences'] = result.get('evidences') or []
        save_draft(task_id, draft)
    return {'status': 'saved', 'target': 'upload', 'target_id': task_id}


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


@router.post('/prepare-review')
def prepare_review(body: PrepareReview, user=Depends(get_current_admin)):
    with SessionLocal() as session:
        snapshot = ev.paper_snapshot(session, body.paper_id, user.id, user.role)
        records = ev.resolve_results(snapshot, ev.cached_results(session, snapshot), user.id, body.job_id, body.expected_version)
        for record in records:
            reason = body.resolutions.get(record['key'], '').strip()
            if len(reason) > 4000:
                ev.fail('evidence_resolution_invalid', '人工裁决理由不能超过 4000 字')
            if record['status'] != 'supported' and not reason:
                ev.fail('evidence_review_required', '请逐条核对原文并填写人工裁决理由', records=records)
            record['resolution'] = reason
        # 计算应用候选后的缓存摘要，Go 同事务保存，下一次不重复调用模型。
        for r in records:
            original = next(x for x in snapshot['records'] if x['key'] == r['key'])
            r['source_hash'] = ev.digest([ev.digest(snapshot['chunks']), r['evidences']])
            r['content_hash'] = original['content_hash']
            r['rule_version'] = ev.RULE_VERSION
        return {'version': snapshot['version'], 'records': records}
