"""定向重算所有受影响的未提交上传草稿；默认仅盘点。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import select

from backend.database import SessionLocal
from backend.ingest import property_evidence as evidence
from backend.services.citation_graph import extract_references_from_pdf
from backend.ingest.document_roles import assess_roles
from backend.ingest.domain_extraction import SUMMARY_BOUNDARY
from backend.ingest.keyword_extraction import select_keywords, task_sources as keyword_sources
from backend.ingest.legacy_scientific_assembly import assemble_legacy_candidates
from backend.ingest.paper_summary import choose_summary, valid_summary
from backend.ingest.research_motivation import choose_motivation, task_chunks, valid_motivation
from backend.ingest.scientific_evidence import load_results, save_results
from backend.ingest.theoretical_subtype import assess_candidate, classify, task_sources as subtype_sources
from backend.ingest.upload_jobs import SUMMARY_SYSTEM_PROMPT, _summary_classification_candidates
from backend.ingest.upload_tasks import (
    artifact_path, data_path, get_draft, get_state, redis_client, save_draft,
    update_state, upload_task_lock,
)
from backend.models import ScientificEvidenceCheck, ScientificUploadDraft
from backend.rag.llm import complete_json
from backend.rag.llm_context import get_llm_config
from backend.storage.paths import object_mode, resolve_file


FIELDS = ("summary", "research_motivation", "keywords_tags", "theoretical_subtype",
          "material_families", "paper_type", "key_finding", "methodology",
          "knowledge_graph_title", "research_materials", "superconductor_kind")


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _source_file(task_id: str, item: dict) -> Path:
    path = str(item.get("stored_path") or "")
    if object_mode():
        return resolve_file(path, size=int(item.get("size") or 0),
                            sha256=str(item.get("sha256") or ""),
                            media_type=str(item.get("media_type") or "application/pdf"),
                            namespace=task_id)
    return Path(path)


def _cached_candidates(task_id: str, roles: dict[str, str]) -> list[dict]:
    root = data_path("review_artifacts") / task_id / "chunks"
    candidates = []
    for path in sorted(root.glob("*/*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        source = item.get("_source") or {}
        file_id = str(source.get("file_id") or path.parent.name)
        if roles.get(file_id) not in {"main", "supplementary"}:
            continue
        item["_source"] = {**source, "file_id": file_id, "file_role": roles[file_id]}
        candidates.append(item)
    return _summary_classification_candidates(candidates)


def _snapshot(task_id: str) -> tuple[dict, dict, dict, set[str], list[dict]]:
    with upload_task_lock(task_id):
        state, draft = copy.deepcopy(get_state(task_id)), copy.deepcopy(get_draft(task_id))
        if not state or not draft or state.get("status") != "ready" or state.get("paper_id"):
            raise ValueError("不是可编辑的未提交 ready 草稿")
        result_path = artifact_path(task_id)
        artifact = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
        if not isinstance(artifact.get("ai_values"), dict):
            raise ValueError("缺少原 AI 基线，不能安全覆盖")
        for item in state.get("files") or []:
            path = _source_file(task_id, item)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
                raise ValueError("来源文件哈希不一致")
        with SessionLocal() as session:
            checks = list(session.scalars(
                select(ScientificEvidenceCheck).where(
                    ScientificEvidenceCheck.target == "upload", ScientificEvidenceCheck.target_id == task_id)))
            manual = {str((row.result or {}).get("field") or "") for row in checks
                      if (row.result or {}).get("decision") or row.resolutions}
            check_backup = [{"item_key": row.item_key, "content_hash": row.content_hash,
                             "source_hash": row.source_hash, "rule_version": row.rule_version,
                             "result": row.result, "resolutions": row.resolutions} for row in checks]
        return state, draft, artifact, manual, check_backup


def _role_result(task_id: str, state: dict) -> tuple[dict, dict[str, str]]:
    root = data_path("parsed_markdown") / task_id
    texts = {str(item["file_id"]): (root / f"{item['file_id']}.md").read_text(encoding="utf-8")
             for item in state.get("files") or [] if (root / f"{item['file_id']}.md").is_file()}
    assessment = assess_roles(state.get("files") or [], texts)
    if assessment["status"] != "resolved":
        raise ValueError("正文身份不能高置信确定")
    roles = {item["file_id"]: item["effective_role"] for item in assessment["files"]}
    return assessment, roles


def _generate(task_id: str, state: dict, roles: dict[str, str]) -> tuple[dict, dict]:
    corrected = copy.deepcopy(state)
    for item in corrected["files"]:
        item["role"] = roles[item["file_id"]]
    root = data_path("parsed_markdown")
    chunks = task_chunks(task_id, corrected, root)
    candidates = _cached_candidates(task_id, roles)
    if not chunks or not candidates:
        raise ValueError("缺少可读取的本文来源或分段候选")
    context, remaining = [], 16000
    for chunk in chunks:
        if chunk.get("file_role") != "main" or remaining <= 0:
            continue
        content = str(chunk.get("content") or "")[:remaining]
        context.append({"file_id": chunk.get("file_id"), "chunk_index": chunk.get("chunk_index"),
                        "page_start": chunk.get("page_start"), "content": content})
        remaining -= len(content)
    raw = complete_json(SUMMARY_SYSTEM_PROMPT + SUMMARY_BOUNDARY,
                        json.dumps({"candidates": candidates, "paper_context": context}, ensure_ascii=False))
    paper = raw.get("paper") or {}
    abstract = paper.get("abstract") or ""
    summary, summary_error = choose_summary(paper.get("summary"), abstract, candidates,
        lambda prompt, payload: complete_json(prompt, json.dumps(payload, ensure_ascii=False)))
    motivation, motivation_error, motivation_origin = choose_motivation(
        paper.get("research_motivation"), paper.get("research_motivation_evidences"), chunks)
    subtype = None
    if paper.get("paper_type") == "theoretical":
        sources = subtype_sources(task_id, corrected, root)
        subtype = assess_candidate(sources, {"value": paper.get("theoretical_subtype"),
            "reason": paper.get("theoretical_subtype_reason"),
            "evidences": paper.get("theoretical_subtype_evidences")}, model=get_llm_config().model)
        if subtype["status"] != "completed":
            subtype = classify(sources, model=get_llm_config().model)
    keywords = select_keywords(keyword_sources(task_id, corrected, root),
        initial_values=paper.get("keywords_tags"), initial_evidences=paper.get("keywords_evidences"),
        initial_reason=str(paper.get("keywords_reason") or ""))
    science, science_issues = assemble_legacy_candidates(candidates)
    values = {**paper, "summary": summary, "research_motivation": motivation,
              "keywords_tags": keywords["values"],
              "theoretical_subtype": subtype.get("value") if subtype else None}
    return values, {"summary_error": summary_error, "motivation_error": motivation_error,
                    "motivation_origin": motivation_origin, "subtype": subtype,
                    "keywords": keywords, "scientific_states": science,
                    "scientific_issues": science_issues}


def _quality(field: str, value, generated: dict) -> bool:
    if field == "summary":
        return not generated["summary_error"] and valid_summary(value, "")
    if field == "research_motivation":
        return not generated["motivation_error"] and valid_motivation(value)
    if field == "keywords_tags":
        return generated["keywords"]["status"] == "completed"
    if field == "theoretical_subtype":
        return bool(generated["subtype"] and generated["subtype"]["status"] == "completed")
    # 其余字段缺少逐字段可靠性证明时，只记录候选而不自动覆盖旧草稿。
    return False


def rebuild(task_id: str, *, apply: bool, force_proposals: bool = False) -> dict:
    state, draft, artifact, manual, check_backup = _snapshot(task_id)
    assessment, roles = _role_result(task_id, state)
    model_path = data_path("review_artifacts") / task_id / "run-metadata.json"
    metadata = json.loads(model_path.read_text(encoding="utf-8")) if model_path.is_file() else {}
    current_model = get_llm_config()
    if (metadata.get("model"), metadata.get("provider")) != (current_model.model, current_model.provider):
        raise ValueError("原模型或提供方当前不可用，未切换配置重算")
    role_changed = any(item.get("role") != roles[item["file_id"]] for item in state["files"])
    previous_rebuild = state.get("issue135_rebuild") or {}
    if (not role_changed and not force_proposals
            and previous_rebuild.get("source_hash") == assessment["source_hash"]):
        return {"task_id": task_id, "status": "review_pending",
                "reason": "本来源版本已重算，未通过质量门的字段保留待审；再次生成须显式指定"}
    old_paper = draft.get("paper") or {}
    needs = role_changed or not old_paper.get("summary") or not old_paper.get("research_motivation") \
        or (old_paper.get("paper_type") == "theoretical" and not old_paper.get("theoretical_subtype"))
    proposal_only = force_proposals and not role_changed
    if not needs and not force_proposals:
        return {"task_id": task_id, "status": "unchanged", "reason": "当前 AI 草稿无需重算"}
    if not apply:
        return {"task_id": task_id, "status": "eligible", "role_changed": role_changed,
                "manual_fields": sorted(manual)}
    version, original_hash = int(state.get("revision") or 0), _digest(draft)
    new_paper, generation = _generate(task_id, state, roles)
    ai_paper = (artifact.get("ai_values") or {}).get("paper") or {}
    changed, skipped = [], []
    updated = copy.deepcopy(draft)
    for field in FIELDS:
        current, original, proposed = old_paper.get(field), ai_paper.get(field), new_paper.get(field)
        if proposal_only:
            skipped.append({"field": field, "reason": "已纠正角色；只保存新候选供人工比较"})
            continue
        if f"paper.{field}" in manual or current != original:
            skipped.append({"field": field, "reason": "人工修改或 AI 基线不同"})
            continue
        if not _quality(field, proposed, generation):
            skipped.append({"field": field, "reason": "新候选仍缺可靠质量依据"})
            continue
        old_invalid = ((field == "research_motivation" and not valid_motivation(current))
                       or (field == "summary" and not valid_summary(current, "")))
        if current not in (None, "", [], {}) and field not in {"keywords_tags"} and not old_invalid:
            skipped.append({"field": field, "reason": "首值仍存在，无法证明新候选严格更好"})
            continue
        if current != proposed:
            updated["paper"][field] = copy.deepcopy(proposed)
            changed.append(field)
    if "research_motivation" in changed:
        updated["research_motivation"] = updated["paper"]["research_motivation"]
        updated["research_motivation_error"] = None
    if "summary" in changed:
        updated["summary_error"] = None
    if "keywords_tags" in changed:
        updated["keyword_assessment"] = generation["keywords"]
    if "theoretical_subtype" in changed:
        updated["theoretical_subtype_assessment"] = generation["subtype"]
    skipped.append({"field": "material_states", "reason": "旧科学记录含条件/方法，候选未证明严格改善"})
    files = [{**item, "declared_role": item.get("declared_role") or item.get("role"),
              "role": roles[item["file_id"]]} for item in state["files"]]
    main = next(item for item in files if item["role"] == "main")
    citation = (extract_references_from_pdf(_source_file(task_id, main))
                if role_changed and str(main.get("kind") or "").lower() == "pdf" else None)
    if citation is not None:
        updated["citation_extraction"] = citation
    issues = [item for item in updated.get("generation_issues") or [] if item.get("code") != "conflict"]
    proposals = []
    for item in skipped:
        field = item["field"]
        proposed = new_paper.get(field) if field != "material_states" else generation["scientific_states"]
        current = old_paper.get(field) if field != "material_states" else draft.get("material_states")
        if proposed != current:
            field_path = f"paper.{field}" if field != "material_states" else field
            issues.append({"field": field_path, "code": "conflict", "message": item["reason"],
                           **({"candidate": proposed} if field != "material_states" else {})})
            proposals.append({"field": field_path, "candidate": proposed, "reason": item["reason"]})
    updated["generation_issues"] = issues
    report = {"task_id": task_id, "status": "updated", "role_changed": role_changed,
              "changed": changed, "skipped": skipped,
              "science_candidates": len(generation["scientific_states"]),
              "science_issues": generation["scientific_issues"]}
    backup_root = data_path("backups") / "issue135-rebuild"
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_root.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_root / f"{task_id}-{stamp}.json"
    with upload_task_lock(task_id):
        current_state, current_draft = get_state(task_id), get_draft(task_id)
        if not current_state or int(current_state.get("revision") or 0) != version or _digest(current_draft) != original_hash:
            raise ValueError("模型调用期间草稿或任务版本变化，未写入")
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       "w", encoding="utf-8") as output:
            json.dump({"state": state, "draft": draft, "artifact": artifact,
                       "evidence_checks": check_backup, "proposals": proposals,
                       "scientific_candidates": generation["scientific_states"]},
                      output, ensure_ascii=False, indent=2)
        corrected = {**assessment, "status": "resolved"}
        update_state(task_id, files=files, role_assessment=corrected,
                     filename=main.get("original_filename"), file_kind=main.get("kind"),
                     file_path=main.get("stored_path"), source_file_path=main.get("source_file_path"),
                     file_sha256=main.get("sha256"), file_size=main.get("size"),
                     **({"citation_extraction_status": citation.get("status"),
                         "citation_extraction_error": citation.get("error_message"),
                         "citation_reference_count": len(citation.get("references") or [])}
                        if citation is not None else {}))
        save_draft(task_id, updated)
        for field in changed:
            artifact["ai_values"].setdefault("paper", {})[field] = copy.deepcopy(updated["paper"][field])
        if "research_motivation" in changed:
            artifact["ai_values"]["research_motivation"] = updated["paper"]["research_motivation"]
        if citation is not None:
            artifact["ai_values"]["citation_extraction"] = citation
        result_path = artifact_path(task_id)
        temporary = result_path.with_suffix(".json.issue135.tmp")
        temporary.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(result_path)
        update_state(task_id, issue135_rebuild={"source_hash": assessment["source_hash"],
                     "model": current_model.model, "provider": current_model.provider,
                     "completed_at": stamp})
    report["backup"] = str(backup)
    fresh = get_draft(task_id)
    assert all(fresh["paper"].get(field) == updated["paper"].get(field) for field in FIELDS)
    if proposal_only:
        report["recheck_status"] = "existing_checks_preserved"
        return report
    owner = int(state["user_id"])
    review_fields = {f"paper.{field}" for field in changed}
    review_fields.update(item["field"] for item in issues if str(item.get("field") or "").startswith("paper."))
    try:
        snapshot = evidence.upload_snapshot(task_id, owner, parsing_draft=fresh)
        available = {record["field"] for record in snapshot["records"]}
        review_fields &= available
        checks = (evidence.generate_upload_suggestions(task_id, fresh, owner,
                  skip_auto_fill=review_fields, requested_fields=review_fields) if review_fields else {})
    except Exception as exc:
        report["recheck_status"] = "failed"
        report["recheck_error"] = type(exc).__name__
    else:
        report["recheck_status"] = "partial" if role_changed else "completed"
        report["rechecked_fields"] = len(checks)
        report["supported_fields"] = sum(result.get("status") == "supported" for result in checks.values())
        if role_changed:
            report["pending_recheck"] = "未改变的字段与旧科学记录仍需按新正文来源核对"
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="写入已通过保护检查的受影响草稿")
    parser.add_argument("--force-proposals", action="store_true", help="已纠正角色的草稿也重新生成待审候选")
    args = parser.parse_args()
    with SessionLocal() as session:
        task_ids = [row.task_id for row in session.scalars(select(ScientificUploadDraft))]
    report = []
    for task_id in task_ids:
        try:
            report.append(rebuild(task_id, apply=args.apply, force_proposals=args.force_proposals))
        except Exception as exc:
            report.append({"task_id": task_id, "status": "skipped", "reason": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
