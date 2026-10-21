"""Canonical multi-file upload task API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from backend.ingest.upload_contracts import (
    MAX_UPLOAD_BYTES,
    UPLOAD_STATE_SCHEMA_VERSION,
    public_task_state,
)
from backend.models import User
from backend.security import get_current_user
from backend.rag.llm_context import request_llm_config


router = APIRouter(
    prefix="/api/upload-tasks", tags=["upload-tasks"],
    dependencies=[Depends(request_llm_config)],
)


class FileDeclaration(BaseModel):
    client_id: str
    role: Literal["main", "supplementary", "attachment"]
    filename: str
    size: int = Field(ge=0, le=MAX_UPLOAD_BYTES)
    media_type: str | None = None


class CreateUploadTask(BaseModel):
    files: list[FileDeclaration] = Field(min_length=1)
    parser_profile: Literal["complementary"] | None = None


class RoleDecision(BaseModel):
    file_id: str
    role: Literal["main", "supplementary", "attachment"]


class ResolveRoles(BaseModel):
    expected_revision: int = Field(ge=0)
    roles: list[RoleDecision] = Field(min_length=1)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _owned_state(task_id: str, user: User) -> dict[str, Any]:
    from backend.ingest.upload_tasks import get_state

    state = get_state(task_id)
    if not state or state.get("is_shadow"):
        raise _error(404, "UPLOAD_TASK_NOT_FOUND", "上传任务不存在或已过期")
    is_admin = user.role in {"admin", "superadmin"} and user.is_approved
    if int(state.get("user_id") or 0) != user.id and not is_admin:
        raise _error(403, "UPLOAD_TASK_FORBIDDEN", "无权访问该上传任务")
    return state


def _versioned_public_state(state: dict[str, Any]) -> dict[str, Any]:
    try:
        version = int(state.get("state_schema_version") or 0)
    except (TypeError, ValueError):
        version = 0
    if version != UPLOAD_STATE_SCHEMA_VERSION:
        raise _error(
            409,
            "UPLOAD_STATE_VERSION_UNSUPPORTED",
            "上传任务由旧版 Worker 生成，请先执行状态迁移",
        )
    return public_task_state(state)


@router.post("")
def create_upload_task(
    body: CreateUploadTask,
    current_user: User = Depends(get_current_user),
):
    from backend.ingest.upload_tasks import create_task

    try:
        state = create_task(
            current_user.id,
            files=[item.model_dump() for item in body.files],
            parser_profile=body.parser_profile,
        )
    except ValueError as exc:
        message = str(exc)
        code = "ACTIVE_TASK_LIMIT_REACHED" if "100" in message else "INVALID_MANIFEST"
        raise _error(409 if code.startswith("ACTIVE") else 400, code, message) from exc
    return JSONResponse(status_code=201, content={"ok": True, "data": public_task_state(state)})


@router.get("")
def get_upload_tasks(
    current_user: User = Depends(get_current_user),
):
    from backend.ingest.upload_tasks import list_user_tasks

    return {
        "ok": True,
        "data": [_versioned_public_state(state) for state in list_user_tasks(current_user.id)],
    }


@router.get("/{task_id}")
def get_upload_task(
    task_id: str,
    touch: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    from backend.ingest.upload_tasks import touch_user_activity

    try:
        state = _owned_state(task_id, current_user)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # 仅在临时任务缺失时回溯正式论文，处理另一页面/进程已提交后的旧入口。
        # 不重建 Redis 草稿；先鉴权再返回论文位置，避免泄露他人的待审核论文。
        from sqlalchemy import select
        from backend.database import SessionLocal
        from backend.models import Paper

        with SessionLocal() as session:
            paper = session.scalar(select(Paper).where(Paper.upload_task_id == task_id))
            is_admin = current_user.role in {"admin", "superadmin"} and current_user.is_approved
            if paper is not None and (paper.uploaded_by_user_id == current_user.id or is_admin):
                raise HTTPException(status_code=409, detail={
                    "code": "UPLOAD_TASK_SUBMITTED",
                    "message": "该论文已提交审核，解析任务已归档，请查看论文详情。",
                    "paper_id": paper.id,
                }) from exc
        raise
    if touch:
        state = touch_user_activity(task_id)
    return {"ok": True, "data": _versioned_public_state(state)}


@router.post("/{task_id}/activity")
def record_upload_activity(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import touch_user_activity

    _owned_state(task_id, current_user)
    return {"ok": True, "data": public_task_state(touch_user_activity(task_id))}


@router.put("/{task_id}/files/{file_id}")
async def upload_task_file(
    task_id: str,
    file_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    from backend.ingest.upload_jobs import sha256_file
    from backend.storage import FileConflict, FileStorageUnavailable, create_storage
    from backend.storage.paths import object_mode
    from backend.ingest.upload_tasks import (
        enqueue_processing,
        lock_uploaded_manifest,
        task_directory,
        update_state,
        update_task_file,
    )

    state = _owned_state(task_id, current_user)
    declared = next((item for item in state.get("files") or [] if item.get("file_id") == file_id), None)
    if not declared:
        raise _error(404, "UPLOAD_FILE_NOT_FOUND", "上传文件不存在")
    if declared.get("upload_status") == "completed":
        raise _error(409, "UPLOAD_FILE_ALREADY_COMPLETED", "该文件已经上传完成")

    suffix = Path(declared["original_filename"]).suffix.lower()
    destination = task_directory(task_id) / f"{file_id}{suffix}"
    total = 0
    reference = None
    referenced = False
    try:
        with destination.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise _error(413, "FILE_TOO_LARGE", "文件超过 50 MB 限制")
                stream.write(chunk)
        digest = sha256_file(destination)
        key = (f"upload_PDFs/{task_id}/{file_id}/{uuid4().hex}{suffix}"
               if object_mode() else f"upload_PDFs/{task_id}/{destination.name}")
        stored_path = str(destination)
        if object_mode():
            with destination.open("rb") as source:
                reference = create_storage().put(key, source, file.content_type or "application/octet-stream")
            stored_path = reference.key
        state = update_task_file(
            task_id,
            file_id,
            upload_status="completed",
            size=total,
            sha256=digest,
            stored_path=stored_path,
            source_file_path=key,
        )
        referenced = True
    except FileConflict as exc:
        raise _error(409, "FILE_REFERENCE_CONFLICT", "文件标识已被不同内容占用") from exc
    except FileStorageUnavailable as exc:
        raise _error(503, "FILE_STORAGE_UNAVAILABLE", "文件存储暂时不可用") from exc
    except Exception:
        if reference is not None and not referenced:
            create_storage().delete(reference)
        if not object_mode():
            destination.unlink(missing_ok=True)
        raise
    finally:
        if object_mode():
            destination.unlink(missing_ok=True)
        await file.close()

    queued = False
    if all(item.get("upload_status") == "completed" for item in state.get("files") or []):
        state, queued = lock_uploaded_manifest(task_id)
        if queued:
            try:
                enqueue_processing(task_id)
            except Exception as exc:
                update_state(
                    task_id, status="failed", processing_status="failed",
                    error_code="upload_queue_unavailable", processing_error=str(exc),
                )
                raise _error(503, "UPLOAD_QUEUE_UNAVAILABLE", "文件已保存，但解析任务暂时无法启动") from exc
    return {"ok": True, "queued": queued, "data": public_task_state(state)}


@router.post("/{task_id}/finalize")
def finalize_upload_task(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import enqueue_processing, lock_uploaded_manifest

    _owned_state(task_id, current_user)
    try:
        state, queued = lock_uploaded_manifest(task_id)
    except ValueError as exc:
        raise _error(409, "UPLOAD_INCOMPLETE", str(exc)) from exc
    if queued:
        enqueue_processing(task_id)
    return {"ok": True, "queued": queued, "data": public_task_state(state)}


@router.post("/{task_id}/cancel")
def cancel_upload_task(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import schedule_cleanup, update_state

    state = _owned_state(task_id, current_user)
    if state.get("status") in {"cancelled", "submitted"}:
        return {"ok": True, "data": public_task_state(state)}
    if state.get("status") in {"uploading", "queued"}:
        state = update_state(
            task_id, status="cancelled", processing_status="cancelled",
            cancel_requested_at=state.get("updated_at"),
        )
        schedule_cleanup(task_id)
    else:
        state = update_state(task_id, status="cancelling", cancel_requested_at=state.get("updated_at"))
    return JSONResponse(status_code=202, content={"ok": True, "data": public_task_state(state)})


@router.get("/{task_id}/parsing")
def get_parsing_detail(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_jobs import public_parsing_detail

    _owned_state(task_id, current_user)
    return {"ok": True, "data": public_parsing_detail(task_id)}


@router.get("/{task_id}/chunks")
def get_parsing_chunks(
    task_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    from backend.ingest.upload_jobs import public_parsing_detail

    _owned_state(task_id, current_user)
    detail = public_parsing_detail(task_id)
    chunks = detail.pop("chunks")
    return {
        "ok": True,
        "data": chunks[offset:offset + limit],
        "total": len(chunks),
        "revision": detail["revision"],
        "next_poll_ms": detail["next_poll_ms"],
    }


@router.post("/{task_id}/retry")
def retry_upload_task(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import enqueue_processing, update_state

    state = _owned_state(task_id, current_user)
    if state.get("status") != "failed":
        raise _error(409, "RETRY_NOT_ALLOWED", "只有失败任务可以重试")
    state = update_state(
        task_id, status="queued", retry=True, processing_status="processing",
        processing_error=None, error_code=None,
    )
    enqueue_processing(task_id)
    return JSONResponse(status_code=202, content={"ok": True, "data": public_task_state(state)})


@router.post("/{task_id}/resolve-roles")
def resolve_upload_roles(task_id: str, body: ResolveRoles, current_user: User = Depends(get_current_user)):
    """仅在正文身份不确定时接收完整角色表，复用已经解析的原文。"""
    from backend.ingest.upload_tasks import (
        available_published_path, data_path, enqueue_processing, get_state,
        load_llm_config, update_state, upload_task_lock,
    )
    from backend.ingest.document_roles import assess_roles, TEXT_KINDS

    _owned_state(task_id, current_user)
    with upload_task_lock(task_id):
        state = get_state(task_id)
        if not state or int(state.get("user_id") or 0) != current_user.id:
            raise _error(403, "UPLOAD_TASK_FORBIDDEN", "只有上传者可以确认文件角色")
        if state.get("status") != "needs_role_review":
            raise _error(409, "ROLE_REVIEW_NOT_PENDING", "当前任务不等待文件角色确认")
        if int(state.get("revision") or 0) != body.expected_revision:
            raise _error(409, "ROLE_REVIEW_STALE", "任务版本已变化，请刷新后重新确认")
        files = state.get("files") or []
        choices = {item.file_id: item.role for item in body.roles}
        if (len(choices) != len(body.roles) or set(choices) != {str(f.get("file_id")) for f in files}
                or sum(role == "main" for role in choices.values()) != 1):
            raise _error(422, "ROLE_REVIEW_INVALID", "请为每份文件指定角色，并且恰好选择一个正文")
        if any(choices[str(f["file_id"])] == "main" and str(f.get("kind") or "").lower() not in TEXT_KINDS
               for f in files):
            raise _error(422, "ROLE_REVIEW_INVALID", "结构附件不能作为论文正文")
        root = data_path("parsed_markdown") / task_id
        texts = {}
        for item in files:
            path = available_published_path(task_id, root / f"{item['file_id']}.md")
            if path.is_file():
                texts[str(item["file_id"])] = path.read_text(encoding="utf-8")
        observed = assess_roles(files, texts)
        assessment = state.get("role_assessment") or {}
        if observed["source_hash"] != assessment.get("source_hash"):
            raise _error(409, "ROLE_SOURCE_CHANGED", "来源文件已变化，请重新解析后确认")
        if load_llm_config(task_id) is None:
            raise _error(409, "ROLE_MODEL_EXPIRED", "原解析模型配置已过期，请重新发起解析")
        selected = [{**f, "declared_role": f.get("declared_role") or f.get("role"),
                     "role": choices[str(f["file_id"])]} for f in files]
        detail = {item["file_id"]: {**item, "effective_role": choices[item["file_id"]]}
                  for item in assessment.get("files") or []}
        resolved = {**assessment, "status": "user_confirmed",
                    "main_file_id": next(file_id for file_id, role in choices.items() if role == "main"),
                    "files": list(detail.values()), "reason": "上传者确认了文件角色"}
        update_state(task_id, status="queued", stage="extracting", files=selected,
                     role_assessment=resolved, processing_status="processing")
        try:
            enqueue_processing(task_id, preserve_llm_config=True)
        except Exception as exc:
            update_state(task_id, status="needs_role_review", stage="extracting", files=files,
                         role_assessment=assessment, processing_status="needs_input")
            raise _error(503, "ROLE_RESUME_FAILED", "角色已确认但任务未能入队，请重试") from exc
    return JSONResponse(status_code=202, content={"ok": True, "data": public_task_state(get_state(task_id))})


@router.delete("/{task_id}")
def delete_upload_task(task_id: str, current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import delete_task_record, submitted_paper_id

    state = _owned_state(task_id, current_user)
    if state.get("status") not in {"failed", "duplicate", "cancelled"}:
        raise _error(409, "UPLOAD_TASK_NOT_CLEARABLE", "运行中或待校对任务不能直接清理")
    if submitted_paper_id(task_id) is not None:
        raise _error(409, "UPLOAD_TASK_PERSISTED", "任务已经生成正式论文，不能删除文件")
    try:
        delete_task_record(task_id)
    except TimeoutError:
        raise _error(409, "UPLOAD_TASK_BUSY", "任务正被其他请求处理，请稍后重试")
    return {"ok": True}


class BatchDeleteUploadTasks(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/batch-delete")
def batch_delete_upload_tasks(
    body: BatchDeleteUploadTasks,
    current_user: User = Depends(get_current_user),
):
    """批量删除上传解析记录：逐条处理，单条失败不影响其余（best-effort）。"""
    from backend.ingest.upload_tasks import delete_task_record

    deleted: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for task_id in dict.fromkeys(body.task_ids):
        try:
            _owned_state(task_id, current_user)
            delete_task_record(task_id)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            reason = str(detail.get("message") or detail) if detail else str(exc.detail)
            failed.append({"task_id": task_id, "reason": reason})
        except TimeoutError:
            failed.append({"task_id": task_id, "reason": "任务正被其他请求处理，请稍后重试"})
        except Exception as exc:  # noqa: BLE001 - 单条失败需收敛为结果明细
            failed.append({"task_id": task_id, "reason": str(exc) or exc.__class__.__name__})
        else:
            deleted.append({"task_id": task_id})
    return {"ok": True, "deleted": deleted, "failed": failed}


@router.post("/cleanup")
def cleanup_upload_tasks(current_user: User = Depends(get_current_user)):
    from backend.ingest.upload_tasks import cleanup_task_files, get_state, list_user_tasks, submitted_paper_id

    deleted: list[str] = []
    skipped: list[str] = []
    deferred: list[str] = []
    for item in list_user_tasks(current_user.id):
        task_id = item["task_id"]
        state = get_state(task_id)
        if not state or state.get("status") not in {"failed", "duplicate", "cancelled"}:
            skipped.append(task_id)
            continue
        try:
            if submitted_paper_id(task_id) is not None:
                skipped.append(task_id)
                continue
        except Exception:
            deferred.append(task_id)
            continue
        cleanup_task_files(task_id)
        deleted.append(task_id)
    return {"ok": True, "deleted": deleted, "skipped": skipped, "deferred": deferred}
