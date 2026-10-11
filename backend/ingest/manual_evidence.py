"""人工修改依据独立于论文原文保存，并按字段版本校验。"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import copy
import base64
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
import pymupdf
from sqlalchemy import case, inspect, select

from backend.manual_evidence_models import ScientificManualEvidence
from backend.rag.config import settings


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ITEMS = 5
MAX_TEXT_CHARS = 20_000
MAX_REVIEW_IMAGE_BYTES = 20 * 1024 * 1024
MAX_REVIEW_PDF_PAGES = 20
EMPTY_HASH = hashlib.sha256(b"null").hexdigest()
IMAGE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


class ManualEvidenceError(ValueError):
    def __init__(self, code: str, message: str, *, field: str = "", status: int = 400):
        self.code, self.field, self.status = code, field, status
        super().__init__(message)


def table_available(session) -> bool:
    return inspect(session.connection()).has_table(ScientificManualEvidence.__tablename__)


def _by_item(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["item_key"]): item for item in snapshot.get("records") or []}


def _semantic_value(record: dict[str, Any]) -> Any:
    """忽略旧草稿升级到模块化表单时的表示差异。"""
    from backend.ingest.scientific_evidence import canonical

    value = copy.deepcopy(record.get("current_value"))
    if record.get("field", "").endswith((".calculation_context", ".experimental_context")):
        return None  # 状态级旧条件已迁至独立记录；界面不再编辑该旧字段。
    if record.get("kind") == "property" and isinstance(value, dict):
        state = value.get("state")
        if isinstance(state, dict):
            state.pop("calculation_context", None)
            state.pop("experimental_context", None)
        property_record = value.get("record")
        if isinstance(property_record, dict) and property_record.get("value_kind") in {"number", "range"}:
            if any(property_record.get(key) is not None for key in ("value_number", "value_min", "value_max")):
                property_record.pop("value_raw", None)
    return canonical(value)


def changed_records(snapshot: dict[str, Any], baseline: dict[str, Any]) -> list[tuple[dict, str]]:
    previous = _by_item(baseline)
    return [(record, str(previous.get(str(record["item_key"]), {}).get("content_hash") or EMPTY_HASH))
            for record in snapshot.get("records") or []
            if str(record["item_key"]) not in previous
            or _semantic_value(record) != _semantic_value(previous[str(record["item_key"])])]


def paper_baseline(session, snapshot: dict[str, Any]) -> dict[str, Any]:
    """从已保存的修改记录和论文修改事件恢复管理员编辑前的字段值。"""
    from backend import models
    from backend.ingest import property_evidence as evidence, scientific_evidence as science

    baseline = copy.deepcopy(snapshot)
    current = _by_item(baseline)
    first_baselines: dict[str, ScientificManualEvidence] = {}
    for row in session.scalars(select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == "paper",
        ScientificManualEvidence.target_id == snapshot["target_id"],
        ScientificManualEvidence.paper_revision == int(snapshot.get("review_state", [None, None, 1])[2] or 1),
    ).order_by(ScientificManualEvidence.created_at, ScientificManualEvidence.id)):
        first_baselines.setdefault(row.item_key, row)
    for item_key, first in first_baselines.items():
        if item_key in current:
            current[item_key]["content_hash"] = first.baseline_hash
            current[item_key]["current_value"] = first.before_value

    paper_id = int(snapshot["target_id"])
    earliest: dict[str, Any] = {}
    for event in session.scalars(select(models.PaperHistoryEvent).where(
        models.PaperHistoryEvent.paper_id == paper_id,
        models.PaperHistoryEvent.paper_revision == int(snapshot.get("review_state", [None, None, 1])[2] or 1),
        models.PaperHistoryEvent.event_type == "modified",
    ).order_by(models.PaperHistoryEvent.id)):
        old_values = (event.classification_snapshot or {}).get("manual_edit_baseline")
        if not isinstance(old_values, dict):
            continue
        for field, value in old_values.items():
            earliest.setdefault(field, value)
    for old in science.field_records("paper", "paper", earliest, science.PAPER_FIELDS):
        if old["field"].split(".")[-1] not in earliest:
            continue
        record = current.get(old["item_key"])
        if record is not None:
            record["content_hash"] = evidence.digest(science.canonical(old["claim"]))
            record["current_value"] = old["current_value"]
    return baseline


def mark_changes(session, snapshot: dict, baseline: dict, actor_id: int, actor_name: str | None = None) -> None:
    for record, _ in changed_records(snapshot, baseline):
        _ensure(session, snapshot, baseline, str(record["item_key"]), actor_id, actor_name)


def _current(session, snapshot: dict, record: dict, *, for_update: bool = False) -> ScientificManualEvidence | None:
    query = select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == snapshot["target"],
        ScientificManualEvidence.target_id == str(snapshot["target_id"]),
        ScientificManualEvidence.item_key == record["item_key"],
        ScientificManualEvidence.value_hash == record["content_hash"],
        ScientificManualEvidence.source_hash == record["source_hash"],
        ScientificManualEvidence.status != "historical",
    )
    if snapshot["target"] == "paper":
        query = query.where(ScientificManualEvidence.paper_revision == int(snapshot.get("review_state", [None, None, 1])[2] or 1))
    if for_update:
        query = query.with_for_update()
    return session.scalar(query.order_by(case((ScientificManualEvidence.status == "draft", 0), else_=1),
                                        ScientificManualEvidence.created_at.desc(), ScientificManualEvidence.id.desc()).limit(1))


def _ensure(session, snapshot: dict, baseline: dict, item_key: str, actor_id: int,
            actor_name: str | None = None) -> tuple[ScientificManualEvidence, dict]:
    current = _by_item(snapshot).get(item_key)
    if current is None:
        raise ManualEvidenceError("manual_field_not_found", "当前字段不存在", status=404)
    prior = _by_item(baseline).get(item_key)
    if prior and _semantic_value(prior) == _semantic_value(current):
        raise ManualEvidenceError("manual_field_unchanged", "字段没有实际修改", field=current["field"], status=409)
    row = _current(session, snapshot, current, for_update=True)
    if row is not None and row.status == "draft" and row.actor_user_id == actor_id:
        if actor_name and not row.actor_name_snapshot and row.actor_user_id == actor_id:
            row.actor_name_snapshot = actor_name[:100]
        return row, current
    for old in session.scalars(select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == snapshot["target"],
        ScientificManualEvidence.target_id == str(snapshot["target_id"]),
        ScientificManualEvidence.item_key == item_key,
        ScientificManualEvidence.status == "draft",
    ).with_for_update()):
        if old.actor_user_id != actor_id and old.value_hash == current["content_hash"] and old.source_hash == current["source_hash"]:
            raise ManualEvidenceError("manual_evidence_conflict", "该字段正由其他人修改，请刷新后重试", field=current["field"], status=409)
        old.status = "historical"
    row = ScientificManualEvidence(
        id=uuid.uuid4().hex, target=snapshot["target"], target_id=str(snapshot["target_id"]),
        paper_id=int(snapshot["target_id"]) if snapshot["target"] == "paper" else None,
        paper_revision=int(snapshot.get("review_state", [None, None, 1])[2] or 1) if snapshot["target"] == "paper" else None,
        item_key=item_key, baseline_hash=str(prior.get("content_hash") if prior else EMPTY_HASH),
        value_hash=str(current["content_hash"]), source_hash=str(current["source_hash"]),
        before_value=json.loads(json.dumps(prior.get("current_value") if prior else None, default=str)),
        after_value=json.loads(json.dumps(current.get("current_value"), default=str)),
        actor_user_id=actor_id, actor_name_snapshot=(actor_name or "")[:100],
        reason="", no_evidence_reason="", items=[], status="draft",
    )
    session.add(row)
    session.flush()
    return row, current


def public_record(row: ScientificManualEvidence | None, *, changed: bool) -> dict[str, Any]:
    if row is None:
        return {"changed": changed, "reason": "", "no_evidence_reason": "", "items": []}
    return {
        "id": row.id, "changed": changed, "reason": row.reason,
        "before_value": row.before_value, "after_value": row.after_value,
        "no_evidence_reason": row.no_evidence_reason, "status": row.status,
        "evidence_version": row.evidence_version,
        "actor_user_id": row.actor_user_id, "created_at": row.created_at.isoformat() if row.created_at else None,
        "actor_name": row.actor_name_snapshot,
        "items": [{key: value for key, value in item.items() if key != "storage_key"}
                  for item in row.items or []],
    }


def read_field(session, snapshot: dict, baseline: dict, item_key: str) -> dict[str, Any]:
    current = _by_item(snapshot).get(item_key)
    if current is None:
        raise ManualEvidenceError("manual_field_not_found", "当前字段不存在", status=404)
    prior = _by_item(baseline).get(item_key)
    row = _current(session, snapshot, current)
    changed = prior is None or _semantic_value(current) != _semantic_value(prior)
    result = public_record(row if changed else None, changed=changed)
    result["before_value"] = row.before_value if changed and row else (prior or {}).get("current_value")
    result["after_value"] = row.after_value if changed and row else current.get("current_value")
    query = select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == snapshot["target"],
        ScientificManualEvidence.target_id == str(snapshot["target_id"]),
        ScientificManualEvidence.item_key == item_key,
    )
    result["history"] = [public_record(previous, changed=True) for previous in session.scalars(
        query.order_by(ScientificManualEvidence.created_at.desc(), ScientificManualEvidence.id.desc()))
        if row is None or previous.id != row.id]
    return result


def save_explanation(session, snapshot: dict, baseline: dict, item_key: str, actor_id: int,
                     *, reason: str, no_evidence_reason: str, text_items: list[dict], actor_name: str | None = None) -> dict[str, Any]:
    row, current = _ensure(session, snapshot, baseline, item_key, actor_id, actor_name)
    if len(reason) > 4000 or len(no_evidence_reason) > 4000:
        raise ManualEvidenceError("manual_reason_too_long", "人工理由最多 4000 字", field=current["field"])
    direct = []
    for item in text_items:
        text = str(item.get("text") or "").strip()
        source = str(item.get("source_description") or "").strip()
        if not text or len(text) > MAX_TEXT_CHARS or not source or len(source) > 200:
            raise ManualEvidenceError("manual_text_invalid", "文字证据和来源说明不能为空，文字最多 2 万字", field=current["field"])
        direct.append({"id": uuid.uuid4().hex, "kind": "text", "text": text,
                       "source_description": source, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                       "size": len(text.encode()), "ai_read_status": "not_read"})
    files = [item for item in row.items or [] if item.get("kind") != "text"]
    if len(files) + len(direct) > MAX_ITEMS:
        raise ManualEvidenceError("manual_evidence_limit", "单个字段最多 5 项人工证据", field=current["field"])
    row.reason = reason.strip()
    row.items = [*files, *direct]
    row.no_evidence_reason = "" if row.items else no_evidence_reason.strip()
    row.evidence_version = (row.evidence_version or 1) + 1
    session.flush()
    return public_record(row, changed=True)


def _file_type(filename: str, raw: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if b"%PDF-" not in raw[:1024]:
            raise ManualEvidenceError("manual_file_invalid", "PDF 文件内容无效")
        try:
            with pymupdf.open(stream=raw, filetype="pdf") as pdf:
                if not pdf.is_pdf or pdf.is_encrypted or pdf.page_count < 1:
                    raise ManualEvidenceError("manual_file_invalid", "只支持未加密且包含页面的 PDF")
        except (RuntimeError, ValueError, OSError) as exc:
            raise ManualEvidenceError("manual_file_invalid", "PDF 文件内容无效") from exc
        return "pdf", "application/pdf"
    if suffix in {".txt", ".md"}:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManualEvidenceError("manual_file_invalid", "文本证据必须是 UTF-8") from exc
        if "\x00" in text:
            raise ManualEvidenceError("manual_file_invalid", "文本证据含无效字符")
        return "text_file", "text/plain; charset=utf-8"
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ManualEvidenceError("manual_file_invalid", "截图不是有效图片") from exc
    media_type = IMAGE_FORMATS.get(str(image_format))
    matching_suffixes = {"PNG": {".png"}, "JPEG": {".jpg", ".jpeg"}, "WEBP": {".webp"}}
    if media_type is None or suffix not in matching_suffixes[str(image_format)]:
        raise ManualEvidenceError("manual_file_invalid", "只支持 PNG/JPEG/WebP、TXT/MD 或 PDF")
    return "image", media_type


def file_path(row_id: str, item_id: str) -> Path:
    if not all(len(value) == 32 and all(ch in "0123456789abcdef" for ch in value) for value in (row_id, item_id)):
        raise ManualEvidenceError("manual_file_not_found", "人工证据不存在", status=404)
    return settings.sc_wiki_data_dir / "manual_evidence" / row_id / item_id


def add_file(session, snapshot: dict, baseline: dict, item_key: str, actor_id: int,
             *, filename: str, raw: bytes, source_description: str, actor_name: str | None = None) -> dict[str, Any]:
    row, current = _ensure(session, snapshot, baseline, item_key, actor_id, actor_name)
    name = Path(filename).name[:200]
    source = source_description.strip() or name
    if not source or len(source) > 200:
        raise ManualEvidenceError("manual_source_invalid", "请填写人工证据的来源说明", field=current["field"])
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise ManualEvidenceError("manual_file_size", "单份人工证据最大 10 MiB", field=current["field"], status=413)
    items = list(row.items or [])
    if len(items) >= MAX_ITEMS:
        raise ManualEvidenceError("manual_evidence_limit", "单个字段最多 5 项人工证据", field=current["field"])
    kind, media_type = _file_type(name, raw)
    item_id = uuid.uuid4().hex
    path = file_path(row.id, item_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        items.append({"id": item_id, "kind": kind, "filename": name, "media_type": media_type,
                      "source_description": source, "sha256": hashlib.sha256(raw).hexdigest(),
                      "size": len(raw), "ai_read_status": "not_read"})
        row.items = items
        row.no_evidence_reason = ""
        row.evidence_version = (row.evidence_version or 1) + 1
        session.flush()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return public_record(row, changed=True)


def file_entry(session, snapshot: dict, item_key: str, item_id: str) -> tuple[ScientificManualEvidence, dict, Path]:
    query = select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == snapshot["target"],
        ScientificManualEvidence.target_id == str(snapshot["target_id"]),
        ScientificManualEvidence.item_key == item_key,
    )
    for row in session.scalars(query):
        entry = next((item for item in row.items or [] if item.get("id") == item_id and item.get("kind") != "text"), None)
        if entry:
            path = file_path(row.id, item_id)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ManualEvidenceError("manual_file_unavailable", "人工证据文件不可用", status=409)
            return row, entry, path
    raise ManualEvidenceError("manual_file_not_found", "人工证据不存在", status=404)


def remove_file(session, snapshot: dict, item_key: str, item_id: str, actor_id: int) -> Path:
    row, _, path = file_entry(session, snapshot, item_key, item_id)
    if row.status != "draft" or row.actor_user_id != actor_id:
        raise ManualEvidenceError("manual_file_forbidden", "已提交或非本人提供的证据不能删除", status=403)
    row.items = [item for item in row.items if item.get("id") != item_id]
    row.evidence_version = (row.evidence_version or 1) + 1
    session.flush()
    return path


def validate_submission(session, snapshot: dict, baseline: dict) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for record, _ in changed_records(snapshot, baseline):
        row = _current(session, snapshot, record)
        if row is None or not row.reason.strip():
            issues.append({"field": record["field"], "code": "manual_reason_required", "message": "人工修改后请填写判断理由"})
        elif not row.items and not row.no_evidence_reason.strip():
            issues.append({"field": record["field"], "code": "manual_evidence_absence_reason_required", "message": "未提供证据时请说明原因"})
    return issues


def complete_keys(session, snapshot: dict, baseline: dict) -> set[str]:
    ready = set()
    for record, _ in changed_records(snapshot, baseline):
        row = _current(session, snapshot, record)
        if row and row.reason.strip() and (row.items or row.no_evidence_reason.strip()):
            ready.add(record["key"])
    return ready


def current_ids(session, snapshot: dict, baseline: dict) -> dict[str, dict[str, Any]]:
    return {record["key"]: {"id": row.id, "version": row.evidence_version}
            for record, _ in changed_records(snapshot, baseline)
            if (row := _current(session, snapshot, record)) is not None and row.status == "draft"}


def review_context(session, snapshot: dict) -> dict[str, dict[str, Any]]:
    """审核 AI 使用独立人工来源，不把上传内容并入论文片段。"""
    context: dict[str, dict[str, Any]] = {}
    image_bytes = 0
    image_index = 0
    for record in snapshot.get("records") or []:
        query = select(ScientificManualEvidence).where(
            ScientificManualEvidence.target == snapshot["target"],
            ScientificManualEvidence.target_id == str(snapshot["target_id"]),
            ScientificManualEvidence.item_key == record["item_key"],
            ScientificManualEvidence.value_hash == record["content_hash"],
            ScientificManualEvidence.source_hash == record["source_hash"],
            ScientificManualEvidence.status != "historical",
        )
        if snapshot["target"] == "paper":
            query = query.where(ScientificManualEvidence.paper_revision == int(snapshot.get("review_state", [None, None, 1])[2] or 1))
        rows = list(session.scalars(query.order_by(ScientificManualEvidence.created_at, ScientificManualEvidence.id)))
        if not rows:
            continue
        items: list[dict[str, Any]] = []
        images: list[dict[str, str]] = []
        pdf_refs: list[dict[str, str]] = []
        for row in rows:
            for item in row.items or []:
                visible = {"kind": item["kind"], "source_description": item["source_description"],
                           "submitted_by_user_id": row.actor_user_id, "sha256": item["sha256"]}
                if item["kind"] == "text":
                    visible["content"] = str(item.get("text") or "")[:MAX_TEXT_CHARS]
                else:
                    path = file_path(row.id, item["id"])
                    if not path.is_file():
                        visible["read_status"] = "not_read"
                    else:
                        raw = path.read_bytes()
                        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                            visible["read_status"] = "not_read"
                        elif item["kind"] == "text_file":
                            visible["content"] = raw.decode("utf-8")[:MAX_TEXT_CHARS]
                        elif item["kind"] == "pdf":
                            try:
                                with pymupdf.open(stream=raw, filetype="pdf") as pdf:
                                    if pdf.is_encrypted or pdf.page_count > MAX_REVIEW_PDF_PAGES:
                                        visible["read_status"] = "not_read"
                                    else:
                                        pages = [page.get_text("text").strip() for page in pdf]
                                        content = "\n".join(page for page in pages if page)
                                        if content and len(content) <= MAX_TEXT_CHARS:
                                            visible["content"] = content
                                            pdf_refs.append({"row_id": row.id, "item_id": item["id"]})
                                        else:
                                            visible["read_status"] = "not_read"
                            except (RuntimeError, ValueError, OSError):
                                visible["read_status"] = "not_read"
                        elif item["kind"] == "image":
                            if image_bytes + len(raw) > MAX_REVIEW_IMAGE_BYTES:
                                visible["read_status"] = "not_read"
                            else:
                                image_bytes += len(raw)
                                image_index += 1
                                visible["image_index"] = image_index
                                images.append({"row_id": row.id, "item_id": item["id"],
                                               "data_url": f"data:{item['media_type']};base64,{base64.b64encode(raw).decode()}"})
                items.append(visible)
        context[record["key"]] = {
            "decisions": [{"reason": row.reason, "no_evidence_reason": row.no_evidence_reason,
                           "submitted_by_user_id": row.actor_user_id} for row in rows],
            "items": items, "images": images, "pdf_refs": pdf_refs,
        }
    return context


def mark_ai_read(session, refs: list[dict[str, str]], *, read: bool) -> None:
    for ref in refs:
        row = session.get(ScientificManualEvidence, ref["row_id"], with_for_update=True)
        if row is None:
            continue
        items = copy.deepcopy(row.items or [])
        matched = False
        for item in items:
            if item.get("id") == ref["item_id"] and item.get("kind") in {"image", "pdf"}:
                item["ai_read_status"] = "read" if read else "not_read"
                matched = True
        if matched:
            row.items = items
            row.evidence_version = (row.evidence_version or 1) + 1
    session.flush()


def transfer_to_paper(session, snapshot: dict, baseline: dict, paper_id: int, revision: int,
                      persisted_snapshot: dict | None = None) -> None:
    persisted = _by_item(persisted_snapshot or {})
    for record, _ in changed_records(snapshot, baseline):
        row = _current(session, snapshot, record, for_update=True)
        if row is None or not row.reason.strip() or (not row.items and not row.no_evidence_reason.strip()):
            raise ManualEvidenceError("manual_evidence_incomplete", "人工修改依据已变化，请补齐后重新提交",
                                      field=record["field"], status=409)
        mapped = persisted.get(record["item_key"])
        if persisted_snapshot is not None and (mapped is None or mapped.get("content_hash") != record.get("content_hash")):
            raise ManualEvidenceError("manual_evidence_transfer_failed", "人工证据对应的正式字段已变化，原草稿已保留",
                                      field=record["field"], status=409)
        row.target, row.target_id = "paper", str(paper_id)
        row.paper_id, row.paper_revision, row.status = paper_id, revision, "submitted"
        if mapped is not None:
            row.value_hash = str(mapped["content_hash"])
            row.source_hash = str(mapped["source_hash"])
    session.flush()


def cleanup_unsubmitted(session, task_id: str) -> list[Path]:
    if not table_available(session):
        return []
    roots = []
    for row in session.scalars(select(ScientificManualEvidence).where(
        ScientificManualEvidence.target == "upload",
        ScientificManualEvidence.target_id == task_id,
    )):
        roots.append(file_path(row.id, "0" * 32).parent)
        session.delete(row)
    session.flush()
    return roots


def remove_file_roots(roots: list[Path]) -> None:
    for path in roots:
        shutil.rmtree(path, ignore_errors=True)
