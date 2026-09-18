"""已拒绝论文的上传者返修接口。"""
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from backend.models import User
from backend.security import get_current_user
from backend.services import paper_revisions as revisions

router = APIRouter(prefix='/api/rag/papers', tags=['paper-revisions'])


class RevisionVersion(BaseModel):
    revision_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    draft_version: int = Field(ge=1)


class RevisionSave(RevisionVersion):
    draft: dict
    evidence_preparation_id: str | None = None


class RevisionSubmit(RevisionVersion):
    evidence_job_id: str | None = None
    expected_evidence_version: str | None = None


async def transaction(operation):
    from backend.rag.database import async_session_factory
    from backend.ingest.property_modules import PropertyValidationError
    try:
        async with async_session_factory() as session:
            async with session.begin():
                return await operation(session)
    except IntegrityError:
        revisions.error(409, 'revision_integrity_conflict', '数据校验或并发写入失败，原论文和返修草稿已保留，请核对后重试')
    except PropertyValidationError as exc:
        raise HTTPException(400, detail=exc.as_dict()) from exc


@router.post('/{paper_id}/revision-draft')
async def begin_revision(paper_id: int, user: User = Depends(get_current_user)):
    return await transaction(lambda s: revisions.open_draft(s, paper_id, user, create=True))


@router.get('/{paper_id}/revision-draft')
async def get_revision(paper_id: int, user: User = Depends(get_current_user)):
    return await transaction(lambda s: revisions.open_draft(s, paper_id, user))


@router.put('/{paper_id}/revision-draft')
async def save_revision(paper_id: int, payload: RevisionSave, user: User = Depends(get_current_user)):
    return await transaction(lambda s: revisions.save_draft(s, paper_id, user, payload))


@router.post('/{paper_id}/revision-draft/submit')
async def submit_revision(paper_id: int, payload: RevisionSubmit, user: User = Depends(get_current_user)):
    return await transaction(lambda s: revisions.submit_draft(s, paper_id, user, payload))


@router.post('/{paper_id}/revision-draft/structure-candidates')
async def upload_structure(paper_id: int, revision_id: str = Form(...), material_state_index: int = Form(..., ge=0),
                           file: UploadFile = File(...), user: User = Depends(get_current_user)):
    from backend.api.rag import MAX_UPLOAD_BYTES
    from backend.ingest.upload_contracts import structure_format_for_filename
    from backend.services.structure_candidates import build_structure_candidate, StructureCandidateError
    from backend.ingest.scientific_evidence import register_structure_origin
    filename = Path(file.filename or 'structure.cif').name
    fmt = structure_format_for_filename(filename)
    if fmt is None:
        revisions.error(400, 'unsupported_structure_type', '只支持 CIF 或 VASP 结构文件')
    try:
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if len(raw) > MAX_UPLOAD_BYTES:
        revisions.error(413, 'file_too_large', '结构文件超过 50 MB 限制')

    async def operation(session):
        _, saved = await revisions.load_for_write(session, paper_id, user, revision_id)
        if material_state_index >= len(saved.draft.get('material_states') or []):
            revisions.error(400, 'material_state_not_found', '请先保存新增的材料状态，再上传结构')
        try:
            candidate = build_structure_candidate(structure_format=fmt, structure_text=raw.decode('utf-8'),
                source={'file_id': uuid.uuid4().hex, 'filename': filename, 'role': 'attachment'},
                material_state_ref=f'material_states[{material_state_index}]')
        except (UnicodeDecodeError, StructureCandidateError, ValueError) as exc:
            revisions.error(400, 'structure_validation_failed', str(exc))
        await session.run_sync(lambda s: register_structure_origin(s, 'revision', revision_id, candidate, user.id, user.username, filename, raw))
        return {'ok': True, 'data': candidate}
    return await transaction(operation)
