"""定向修复待审标题误用末页引用；默认只预览，应用前备份原记录。"""

from __future__ import annotations

import argparse
import copy
import json
import os
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend import models
from backend.database import SessionLocal
from backend.rag.config import settings
from . import property_evidence as evidence
from .pdf_front_matter import verified_title_source
from .pdf_source_pages import current_pdf_results


def _old_citation(source, title, file_id):
    if not isinstance(source, dict) or str(source.get("file_id")) != file_id:
        return False
    quote = str(source.get("quote") or "")
    return quote.casefold().startswith("how to cite this article:") and " ".join(title.split()).casefold() in " ".join(quote.split()).casefold()


def _remove_old_history(result, title, file_id):
    result = copy.deepcopy(result)
    history = []
    for entry in result.get("history") or []:
        if not isinstance(entry, dict):
            history.append(entry)
            continue
        sources = entry.get("evidences") or []
        kept = [item for item in sources if not _old_citation(item, title, file_id)]
        if sources and not kept:
            continue
        entry = {**entry, "evidences": kept}
        history.append(entry)
    if "history" in result:
        result["history"] = history
    return result


def _snapshot(session, target, target_id):
    if target == "upload":
        from .upload_tasks import get_state
        state = get_state(target_id) or {}
        if state.get("paper_id") or not state.get("user_id"):
            return None
        try:
            return evidence.upload_snapshot(target_id, int(state["user_id"]))
        except Exception:
            return None
    if target == "revision":
        from backend.services.paper_revisions import revision_snapshot
        draft = session.scalar(select(models.PaperRevisionDraft).where(
            models.PaperRevisionDraft.revision_id == target_id))
        if draft is None or draft.submitted_revision is not None:
            return None
        try:
            return revision_snapshot(session, target_id, draft.owner_id)
        except Exception:
            return None
    if target == "paper" and target_id.isdigit():
        paper = session.get(models.Paper, int(target_id))
        if paper is not None and paper.review_status == "pending":
            return evidence.paper_snapshot(session, paper.id, 0, "", check_access=False)
    return None


def _repair_target(session, target, target_id):
    if target == "paper" and target_id.isdigit():
        session.scalar(select(models.Paper).where(models.Paper.id == int(target_id)).with_for_update())
    elif target == "revision":
        paper_id = session.scalar(select(models.PaperRevisionDraft.paper_id).where(
            models.PaperRevisionDraft.revision_id == target_id))
        if paper_id is not None:
            session.scalar(select(models.Paper).where(models.Paper.id == paper_id).with_for_update())
    snapshot = _snapshot(session, target, target_id)
    if snapshot is None:
        return []
    title = next((item for item in snapshot["records"] if item["field"] == "paper.title"), None)
    source = verified_title_source(session, snapshot) if title else None
    if source is None:
        return []
    changes = []
    rows = list(session.scalars(select(models.ScientificEvidenceCheck).where(
        models.ScientificEvidenceCheck.target == target,
        models.ScientificEvidenceCheck.target_id == target_id,
        models.ScientificEvidenceCheck.item_key == title["item_key"]).with_for_update()))
    for row in rows:
        old = row.result or {}
        if not any(_old_citation(item, source["quote"], source["file_id"])
                   for item in old.get("evidences") or []) and not any(
                any(_old_citation(item, source["quote"], source["file_id"])
                    for item in (entry.get("evidences") or []))
                for entry in old.get("history") or [] if isinstance(entry, dict)):
            continue
        repaired = current_pdf_results(session, snapshot, {title["key"]: old})[title["key"]]
        repaired = _remove_old_history(repaired, source["quote"], source["file_id"])
        changes.append({"table": "scientific_evidence_checks", "id": row.id, "before": old,
                        "after": repaired, "row": row})
    if target == "paper":
        for row in session.scalars(select(models.ScientificEvidenceSource).where(
            models.ScientificEvidenceSource.paper_id == int(target_id),
            models.ScientificEvidenceSource.item_key == title["item_key"]).with_for_update()):
            old = row.result or {}
            if any(_old_citation(item, source["quote"], source["file_id"])
                   for item in old.get("evidences") or []):
                repaired = _remove_old_history(current_pdf_results(session, snapshot,
                    {title["key"]: old})[title["key"]], source["quote"], source["file_id"])
                changes.append({"table": "scientific_evidence_sources", "id": row.id,
                                "before": old, "after": repaired, "row": row})
        for row in session.scalars(select(models.PaperEvidence).where(
            models.PaperEvidence.paper_id == int(target_id),
            models.PaperEvidence.paper_revision == snapshot["review_state"][2],
            models.PaperEvidence.field_path == "paper.title").join(
                models.PaperChunk, models.PaperChunk.id == models.PaperEvidence.paper_chunk_id).where(
                models.PaperChunk.paper_file_id == int(source["file_id"])).with_for_update()):
            if _old_citation({"file_id": source["file_id"], "quote": row.quote}, source["quote"], source["file_id"]):
                changes.append({"table": "paper_evidences", "id": row.id,
                                "before": {"quote": row.quote, "page_start": row.page_start},
                                "after": None, "row": row})
        for row in session.scalars(select(models.PaperHistoryEvent).where(
            models.PaperHistoryEvent.paper_id == int(target_id),
            models.PaperHistoryEvent.paper_revision == snapshot["review_state"][2]).with_for_update()):
            old = row.classification_snapshot
            if not isinstance(old, dict) or not isinstance(old.get("evidence_review"), list):
                continue
            repaired = copy.deepcopy(old)
            for entry in repaired["evidence_review"]:
                if entry.get("field") != "paper.title":
                    continue
                entry["evidences"] = [item for item in entry.get("evidences") or []
                                      if not _old_citation(item, source["quote"], source["file_id"])]
                if not entry["evidences"]:
                    entry["evidences"] = [source]
            if repaired != old:
                changes.append({"table": "paper_history_events", "id": row.id,
                                "before": old, "after": repaired, "row": row})
    return changes


def run(*, apply=False, target_id=None, backup_root=None):
    with SessionLocal() as session:
        targets = {(row.target, row.target_id) for row in session.scalars(select(models.ScientificEvidenceCheck))}
        targets.update(("paper", str(row.paper_id)) for row in session.scalars(
            select(models.ScientificEvidenceSource).join(models.Paper,
                models.Paper.id == models.ScientificEvidenceSource.paper_id).where(
                models.Paper.review_status == "pending")))
    targets = sorted((target, identifier) for target, identifier in targets
                     if target in {"upload", "revision", "paper"} and (target_id is None or target_id == identifier))
    total = 0
    for target, identifier in targets:
        if target == "upload":
            from .upload_tasks import upload_task_lock
            lock = upload_task_lock(identifier)
        else:
            lock = nullcontext()
        with lock, SessionLocal.begin() as session:
            changes = _repair_target(session, target, identifier)
            if not changes:
                continue
            total += len(changes)
            print(json.dumps({"target": target, "target_id": identifier,
                              "changes": [{"table": item["table"], "id": item["id"]} for item in changes]}, ensure_ascii=False))
            if not apply:
                session.rollback()
                continue
            root = backup_root or settings.sc_wiki_data_dir / "backups" / "issue109-pdf-evidence" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            root.mkdir(parents=True, exist_ok=True)
            backup = root / f"{target}-{identifier}.json"
            descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump([{key: value for key, value in item.items() if key != "row"} for item in changes],
                          stream, ensure_ascii=False, indent=2, default=str)
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps({"backup": str(backup)}, ensure_ascii=False))
            for item in changes:
                if item["after"] is None:
                    session.delete(item["row"])
                else:
                    if item["table"] == "paper_history_events":
                        item["row"].classification_snapshot = item["after"]
                    else:
                        item["row"].result = item["after"]
    print(json.dumps({"mode": "apply" if apply else "dry_run", "changed_rows": total}, ensure_ascii=False))
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="在生成逐目标备份后应用修复")
    parser.add_argument("--target-id", help="只处理指定上传任务、返修草稿或待审论文")
    args = parser.parse_args()
    run(apply=args.apply, target_id=args.target_id)
