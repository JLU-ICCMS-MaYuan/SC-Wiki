"""超级管理员专用的社区 AI 生命周期接口。"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from backend.database import engine
from backend.security import get_current_superadmin
from backend.models import User
from backend.community import service
from backend.community.generation import GenerationError
from backend.rag.llm_catalog import CatalogConfigError
from backend.rag.llm_context import UserCredentialError
from backend.community.models import CommunityAIBatch as Batch, CommunityEntryRevision as Revision

def authenticated_header(request: Request):
    if not request.headers.get("Authorization", "").startswith("Bearer "):
        raise HTTPException(401, detail={"code": "authentication_required"})


router = APIRouter(prefix="/api/community/ai", tags=["community-ai"], dependencies=[Depends(authenticated_header)])


def authorized(user: User = Depends(get_current_superadmin)):
    if not user.is_email_verified:
        raise HTTPException(403, detail={"code": "verified_account_required"})
    return user


def call(operation, *args):
    try:
        return operation(*args)
    except GenerationError as exc:
        code = str(exc)
        status = 403 if code == "superadmin_required" else 404 if code == "content_unavailable" else 409
        raise HTTPException(status, detail={"code": code}) from None
    except (RedisError, SQLAlchemyError, KeyError, CatalogConfigError, UserCredentialError):
        raise HTTPException(503, detail={"code": "community_ai_unavailable"}) from None


class GenerateRequest(BaseModel):
    request_id: UUID


class QuestionRequest(GenerateRequest):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(default="", max_length=20000)


def submit(user, payload, title=None):
    def operation():
        try:
            return service.submit(user.id, str(payload.request_id), title, getattr(payload, "body", "").strip())
        except IntegrityError:
            # 仅在并发唯一键冲突后复读；不可将缺迁移/队列失败冒充重复请求。
            return service.submit(user.id, str(payload.request_id), title, getattr(payload, "body", "").strip())
    identifier = call(operation)
    return get_batch(identifier, user)


@router.post("/questions", status_code=202)
def manual_question(payload: QuestionRequest, user=Depends(authorized)):
    title = payload.title.strip()
    if len(title) < 3:
        raise HTTPException(422, detail={"code": "invalid_community_input"})
    return submit(user, payload, title)


@router.post("/questions/generate", status_code=202)
def generate_question(payload: GenerateRequest, user=Depends(authorized)):
    return submit(user, payload)


@router.get("/batches")
def batches(user=Depends(authorized)):
    def read():
        service.reconcile()
        with Session(engine) as db:
            rows = db.scalars(select(Batch).order_by(Batch.created_at.desc()).limit(30))
            return {"items": [service.batch_dto(db, row) for row in rows]}
    return call(read)


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, user=Depends(authorized)):
    def read():
        with Session(engine) as db:
            batch = db.get(Batch, batch_id)
            if not batch:
                raise GenerationError("content_unavailable")
            return service.batch_dto(db, batch)
    return call(read)


@router.post("/batches/{batch_id}/retry", status_code=202)
def retry_batch(batch_id: str, user=Depends(authorized)):
    call(service.reconcile)
    return get_batch(call(service.retry_batch, user.id, batch_id), user)


@router.post("/tasks/{task_id}/retry", status_code=202)
def retry_task(task_id: int, user=Depends(authorized)):
    call(service.reconcile)
    return get_batch(call(service.retry_task, user.id, task_id), user)


@router.get("/entries/{entry_id}/revisions")
def revisions(entry_id: int, user=Depends(authorized)):
    def read():
        with Session(engine) as db:
            rows = db.scalars(select(Revision).where(Revision.entry_id == entry_id).order_by(Revision.revision.desc()).limit(100))
            return {"items": [{"revision": r.revision, "body": r.body, "human_edited": r.human_edited,
                               "actor_id": r.actor_id, "created_at": r.created_at} for r in rows]}
    return call(read)


class AnswerRequestPayload(GenerateRequest):
    model_key: str = Field(min_length=64, max_length=64)


class TurnEditPayload(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    revision: int = Field(ge=1)


@router.get("/models")
def answer_models(user=Depends(authorized)):
    from backend.community.answers import model_options
    return {"items": call(model_options)}


@router.post("/questions/{question_id}/answers", status_code=202)
def add_answer(question_id: int, payload: AnswerRequestPayload, user=Depends(authorized)):
    from backend.community.answers import enqueue_answer
    def submit_once():
        try:
            return enqueue_answer(user.id, question_id, str(payload.request_id), payload.model_key)
        except IntegrityError:
            return enqueue_answer(user.id, question_id, str(payload.request_id), payload.model_key)
    return call(submit_once)


@router.get("/questions/{question_id}/queue")
def answer_queue(question_id: int, user=Depends(authorized)):
    from backend.community.answers import Request, dto, question_locked, reconcile_answers
    def read():
        reconcile_answers()
        with Session(engine) as db:
            question_locked(db, question_id)
            rows = db.scalars(select(Request).where(Request.question_id == question_id).order_by(Request.sequence.desc()).limit(100))
            return {"items": sorted([dto(row) for row in rows], key=lambda row: row['sequence'])}
    return call(read)


@router.post("/answer-requests/{identifier}/retry", status_code=202)
def retry_answer_request(identifier: int, payload: GenerateRequest, user=Depends(authorized)):
    from backend.community.answers import retry_answer
    return call(retry_answer, user.id, identifier, str(payload.request_id))


@router.patch("/turns/{identifier}")
def edit_answer_turn(identifier: int, payload: TurnEditPayload, user=Depends(authorized)):
    from backend.community.answers import edit_turn
    body = payload.body.strip()
    if not body: raise HTTPException(422, detail={"code":"invalid_community_input"})
    return call(edit_turn, user.id, identifier, body, payload.revision)


@router.get("/turns/{identifier}/revisions")
def answer_turn_revisions(identifier: int, user=Depends(authorized)):
    from backend.community.models import CommunityTurnRevision
    def read():
        with Session(engine) as db:
            rows = db.scalars(select(CommunityTurnRevision).where(CommunityTurnRevision.turn_id == identifier).order_by(CommunityTurnRevision.revision.desc()).limit(100))
            return {"items": [{"revision": r.revision, "body": r.body, "human_edited": r.human_edited, "created_at": r.created_at} for r in rows]}
    return call(read)
