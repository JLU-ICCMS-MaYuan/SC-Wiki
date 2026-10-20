"""论文结构资料读取、无 Tc 元素检索及只读重提取预览。"""

from __future__ import annotations
import csv
import hashlib
import io
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.security import get_current_user, get_current_user_optional
from backend.structural_models import PaperStructuralRecord as Record
from backend.services import structural_records as service

router = APIRouter(prefix="/api/rag/structural-records", tags=["structural-records"])


def fail(message, status=409, code="structural_record_invalid"):
    raise HTTPException(status, detail={"code": code, "message": message})


def admin(user):
    return bool(user and user.role in {"admin", "superadmin"} and user.is_approved)


def visible_paper(db, paper_id, user):
    paper = db.get(models.Paper, paper_id)
    if paper is None:
        fail("论文不存在或无权访问", 404)
    privileged = bool(user and (admin(user) or user.id == paper.uploaded_by_user_id))
    if not privileged and not (
        paper.review_status == "approved" and paper.approved_revision == paper.content_revision
    ):
        fail("论文不存在或无权访问", 404)
    return paper, privileged


def ready(db):
    if not service.available(db):
        fail("结构资料存储尚未升级，请先应用 #49 迁移", 503, "structural_migration_required")


@router.get("/paper/{paper_id}")
def paper_records(paper_id: int, user=Depends(get_current_user_optional), db: Session = Depends(get_db)):
    paper, privileged = visible_paper(db, paper_id, user)
    ready(db)
    return {
        "items": [
            service.serialize(row, paper, private=privileged)
            for row in service.current_items(db, paper)
            if row.kind == "model" and (privileged or row.retention == "retained")
        ]
    }


class Search(BaseModel):
    elements: list[str] = Field(default_factory=list, max_length=118)
    mode: Literal[
        "formula_search", "elements_exact_search", "elements_combination_search", "elements_contained_search"
    ] = "elements_combination_search"
    formula: str = ""
    keyword: str = ""
    pressure_min: float | None = None
    pressure_max: float | None = None
    year_min: int | None = None
    year_max: int | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


@router.post("/search")
def search_records(body: Search, db: Session = Depends(get_db)):
    from pymatgen.core import Composition, Element

    ready(db)
    try:
        selected = (
            set(str(e) for e in Composition(body.formula).elements)
            if body.mode == "formula_search"
            else set(body.elements)
        )
        for symbol in selected:
            Element(symbol)
    except (ValueError, TypeError):
        fail("元素或化学式无效", 422)
    query = (
        select(Record, models.Paper)
        .join(models.Paper, models.Paper.id == Record.paper_id)
        .where(
            Record.retention == "retained",
            Record.kind == "model",
            Record.paper_revision == models.Paper.content_revision,
            models.Paper.review_status == "approved",
            models.Paper.approved_revision == models.Paper.content_revision,
        )
    )
    if selected:
        systems = db.scalars(select(Record.system_key).distinct()).all()
        matched = [
            key
            for key in systems
            if (
                (set(key.split("-")) == selected)
                if body.mode in {"formula_search", "elements_exact_search"}
                else (
                    selected.issubset(set(key.split("-")))
                    if body.mode == "elements_contained_search"
                    else set(key.split("-")).issubset(selected)
                )
            )
        ]
        if not matched:
            return {"items": [], "total": 0}
        query = query.where(Record.system_key.in_(matched))
    for value, column, lower in (
        (body.pressure_min, Record.pressure_gpa, True),
        (body.pressure_max, Record.pressure_gpa, False),
        (body.year_min, models.Paper.year, True),
        (body.year_max, models.Paper.year, False),
    ):
        if value is not None:
            query = query.where(column >= value if lower else column <= value)
    if body.keyword:
        pattern = "%" + body.keyword + "%"
        query = query.where(
            or_(
                Record.material.ilike(pattern),
                models.Paper.title.ilike(pattern),
                models.Paper.doi.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(models.Paper.year.desc(), Record.paper_id, Record.record_key)
        .offset(body.offset)
        .limit(body.limit)
    ).all()
    return {"items": [service.serialize(row, paper) for row, paper in rows], "total": total}


class Preview(BaseModel):
    target: Literal["upload", "revision"]
    target_id: str


@router.post("/reextract")
def reextract(body: Preview, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.ingest.upload_tasks import get_state, get_draft
    from backend.storage.paths import resolve_file
    from backend.ingest.structure_extractor import extract_structure_candidates
    from backend.ingest.upload_jobs import _bind_structure_candidates

    if body.target == "upload":
        state = get_state(body.target_id)
        if not state or (int(state.get("user_id") or 0) != user.id and not admin(user)):
            fail("任务不存在或无权访问", 404)
        if state.get("status") != "ready":
            fail("请等待任务就绪后重提取")
        draft = get_draft(body.target_id)
        files = state.get("files") or []
    else:
        saved = db.scalar(
            select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == body.target_id)
        )
        if not saved or saved.owner_id != user.id or not saved.draft:
            fail("返修草稿不存在或无权访问", 404)
        paper = db.get(models.Paper, saved.paper_id)
        if saved.base_revision != paper.content_revision:
            fail("返修版本已变化，请重新打开")
        draft = saved.draft
        files = [
            dict(
                file_id=str(f.id),
                role=f.role,
                kind="pdf",
                stored_path=f.stored_path,
                sha256=f.sha256,
                size=f.size,
                original_filename=f.original_filename,
            )
            for f in db.scalars(
                select(models.PaperFile).where(
                    models.PaperFile.paper_id == paper.id,
                    models.PaperFile.paper_revision == paper.content_revision,
                )
            )
        ]
    if not draft:
        fail("草稿尚未就绪")
    candidates, observations, issues = [], [], []
    for source in files:
        if source.get("role") not in {"main", "supplementary"} or not str(
            source.get("original_filename") or ""
        ).lower().endswith(".pdf"):
            continue
        path = resolve_file(
            source["stored_path"],
            size=int(source.get("size") or 0),
            sha256=source.get("sha256") or "",
            media_type="application/pdf",
            namespace=body.target_id,
        )
        if hashlib.sha256(path.read_bytes()).hexdigest() != source.get("sha256"):
            fail("原始文件摘要变化，请重新核对来源")
        import pymupdf

        with pymupdf.open(path) as document:
            markdown = "\n".join(
                f"<!-- page: {i+1} -->\n" + page.get_text(sort=True) for i, page in enumerate(document)
            )
        origin = dict(
            file_id=str(source["file_id"]),
            filename=source["original_filename"],
            role=source["role"],
            sha256=source["sha256"],
        )
        candidates.extend(extract_structure_candidates(markdown, source=origin, pdf_path=path))
        # 不完整参数不再作为独立资料项返回。
    for value in candidates:
        value["retention"] = "pending"
    _bind_structure_candidates(draft, candidates)
    return dict(
        base_version=service.fingerprint(draft),
        structure_candidates=candidates,
        structural_observations=observations,
        structural_extraction_issues=issues,
        structural_extraction_version=service.VERSION,
        model_calls=0,
    )


def visible_record(db, identity, user):
    ready(db)
    row = db.get(Record, identity)
    if row is None or row.kind != "model":
        fail("结构资料不存在或无权访问", 404)
    paper, privileged = visible_paper(db, row.paper_id, user)
    if row.paper_revision != paper.content_revision or (not privileged and row.retention != "retained"):
        fail("结构资料不存在或无权访问", 404)
    return row, paper


@router.get("/{identity}")
def record(identity: str, user=Depends(get_current_user_optional), db: Session = Depends(get_db)):
    row, paper = visible_record(db, identity, user)
    return service.serialize(row, paper)


@router.get("/{identity}/download")
def download(
    identity: str,
    format: Literal["cif", "poscar", "json", "csv"] = "json",
    cell: Literal["primitive", "conventional"] = "conventional",
    user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    row, paper = visible_record(db, identity, user)
    value = service.serialize(row, paper)
    if format in {"cif", "poscar"}:
        if row.kind != "model":
            fail("原文未报告原子位置，不能导出完整结构文件", 400)
        representation = row.data_json.get("representations", {}).get(cell, {}).get(format, {})
        if not representation.get("text"):
            fail("该晶胞表示暂不可用", 400)
        data, media = representation["text"], "text/plain; charset=utf-8"
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "material",
                "pressure_gpa",
                "calculation_label",
                "space_group",
                "reported_cell_parameters",
                "derived_cell_parameters",
                "bond_lengths",
                "sources",
                "paper_id",
                "doi",
            ]
        )
        payload = row.data_json
        writer.writerow(
            [
                row.material,
                row.pressure_gpa,
                payload.get("calculation_label"),
                row.space_group,
                json.dumps(
                    payload.get("cell_parameters") or payload.get("validation", {}).get("cell_parameters", {})
                ),
                json.dumps(payload.get("derived_cell_parameters", {})),
                json.dumps(payload.get("bond_lengths", [])),
                json.dumps(payload.get("sources", []), ensure_ascii=False),
                paper.id,
                paper.doi,
            ]
        )
        data, media = output.getvalue(), "text/csv; charset=utf-8"
    else:
        data, media = json.dumps(value, ensure_ascii=False, allow_nan=False), "application/json"
    return Response(
        data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="structure-{row.id}.{format}"',
            "Cache-Control": "private, no-store",
        },
    )
