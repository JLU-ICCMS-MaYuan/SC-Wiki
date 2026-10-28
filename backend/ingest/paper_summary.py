"""论文级结论总结的生成规则与最小格式校验。"""

from __future__ import annotations

import re
import hashlib
import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from .language_contract import GeneratedFieldLanguageError, validate_draft_generated_english


SUMMARY_RULES = """
paper.summary 是读者配合原文 abstract 阅读的论文核心总结，不是 abstract 的复制或翻译。
综合本文各部分的研究对象、关键方法、重要结果和结论，写 3–5 条英文编号结论；
每条独占一行，以 "1. "、"2. " 依次编号，每条只写一个完整句子。
原摘要达到 70 个英文词时，总结总词数应略多于摘要且不超过约 1.5 倍；短摘要无需机械凑字数。
优先补充关键数值的材料、相、压力或测量条件；不堆砌背景、
不复写摘要的句子，不把参考文献或前人工作的结果写成本文结论。
原文缺少依据时不补造事实；不能形成可靠总结时返回空字符串。
"""


RETRY_PROMPT = """你是超导论文编辑。只重新生成 paper.summary，不修改其他字段。
从输入的摘要与全文分段候选判断本文最重要的 3–5 项结论；来源中的引文与前人工作不是本文结果。
返回 JSON {"summary":"1. ...\\n2. ...\\n3. ..."}。
""" + SUMMARY_RULES


def _plain(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def valid_summary(value: Any, abstract: str | None) -> bool:
    """拒绝摘要复写与明显不符合单句编号格式的生成文本。"""
    if not isinstance(value, str):
        return False
    lines = [line.strip() for line in value.strip().splitlines() if line.strip()]
    if not 3 <= len(lines) <= 5:
        return False
    try:
        validate_draft_generated_english({"paper": {"summary": value}})
    except GeneratedFieldLanguageError:
        return False
    for index, line in enumerate(lines, start=1):
        match = re.fullmatch(rf"{index}\.\s+(.+)", line)
        if not match:
            return False
        sentence = match.group(1).strip()
        if not sentence.endswith((".", "!", "?")) or len(sentence.split()) < 6:
            return False
        if re.search(r"[.!?]\s+[A-Z][a-z]", sentence[:-1]):
            return False
    normalized_abstract = _plain(abstract or "")
    normalized_summary = _plain(" ".join(re.sub(r"^\d+\.\s*", "", line) for line in lines))
    abstract_words = len((abstract or "").split())
    summary_words = len(" ".join(re.sub(r"^\d+\.\s*", "", line) for line in lines).split())
    if abstract_words >= 70 and not abstract_words < summary_words <= 1.5 * abstract_words:
        return False
    if normalized_abstract and SequenceMatcher(None, normalized_abstract, normalized_summary).ratio() >= 0.88:
        return False
    abstract_sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", abstract or "") if len(item.split()) >= 6]
    return not any(SequenceMatcher(None, _plain(re.sub(r"^\d+\.\s*", "", line)), _plain(sentence)).ratio() >= 0.9
                   for line in lines for sentence in abstract_sentences)


def choose_summary(initial: Any, abstract: str | None, candidates: Any,
                   complete: Callable[..., dict[str, Any]], *,
                   on_attempt: Callable[[dict], None] | None = None) -> tuple[str, str | None]:
    """先用全文汇总结果；无效时只重新调用一次总结模型。"""
    first = initial.strip() if isinstance(initial, str) else ""
    words = len((abstract or "").split())
    requirements = {"numbered_single_sentence_lines": "3-5", "abstract_word_count": words,
                    "summary_min_words": words + 1 if words >= 70 else None,
                    "summary_max_words": int(1.5 * words) if words >= 70 else None}
    def record(attempt, value):
        if on_attempt:
            on_attempt({"attempt": attempt, "summary": value, "requirements": requirements,
                        "valid": valid_summary(value, abstract)})
    record("initial", initial)
    if valid_summary(initial, abstract):
        return first, None
    try:
        retry_prompt = RETRY_PROMPT
        if words >= 70:
            retry_prompt += (f"\nFor this retry return {{\"conclusions\":[five complete English sentences]}} instead of a summary string. "
                             f"Each sentence must contain {(words + 5) // 5}–{int(1.5 * words) // 5} whitespace-separated words; "
                             f"aim for {max(1, int(1.2 * words) // 5)} words per sentence. The server adds numbering. "
                             "Use only supported facts, rewrite rather than copying the failed previous summary.")
        retry = complete(retry_prompt, {"abstract": abstract or "", "candidates": candidates,
                         "previous_summary": first, "requirements": requirements,
                         "validation_feedback": "上一总结未满足格式、字数或摘要重复限制，请按明确的上下界重新组织结论，不补造事实。"})
        text = retry.get("summary") if isinstance(retry, dict) else None
        if isinstance(retry, dict) and isinstance(retry.get("conclusions"), list) and all(
                isinstance(point, str) for point in retry["conclusions"]):
            text = "\n".join(f"{index}. {point.strip()}" for index, point in enumerate(retry["conclusions"], 1))
    except Exception:
        return first, "retry_failed"
    record("retry", text)
    if valid_summary(text, abstract):
        return text.strip(), None
    return first, "invalid_summary"


def rerun_ready_upload(task_id: str, *, expected_filename: str, expected_main_sha256: str,
                       generated_summary: str | None = None) -> dict[str, Any]:
    """对一份已完成、未人工改写的上传草稿定向重算总结和核对。"""
    from sqlalchemy import select

    from backend.database import SessionLocal
    from backend.ingest import property_evidence as evidence, scientific_evidence as science
    from backend.ingest.keyword_extraction import task_sources
    from backend.ingest.upload_tasks import (artifact_path, available_published_path, data_path,
                                             get_draft, get_state, publish_artifact_path,
                                             save_draft, update_state, upload_task_lock)
    from backend.storage.paths import object_mode, resolve_file
    from backend.manual_evidence_models import ScientificManualEvidence
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import get_llm_config

    def inspect_current() -> tuple[dict, dict, dict, dict, dict, str]:
        state, draft = get_state(task_id), get_draft(task_id)
        if not state or not draft or state.get("stage") != "ready" or state.get("processing_status") != "succeeded":
            raise ValueError("目标不是可编辑的已完成上传草稿")
        if state.get("filename") != expected_filename:
            raise ValueError("目标文件名不匹配")
        files = state.get("files") or []
        main = [item for item in files if item.get("role") == "main"]
        if len(main) != 1 or main[0].get("sha256") != expected_main_sha256:
            raise ValueError("正文文件身份不匹配")
        for item in files:
            if object_mode():
                source = resolve_file(str(item.get("stored_path") or ""),
                                      size=int(item.get("size") or 0), sha256=str(item.get("sha256") or ""),
                                      media_type=str(item.get("media_type") or "application/octet-stream"),
                                      namespace=task_id)
            else:
                source = Path(str(item.get("stored_path") or ""))
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item.get("sha256"):
                raise ValueError("来源文件内容已变化")
        path = available_published_path(task_id, artifact_path(task_id))
        artifact = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        original = ((artifact.get("ai_values") or {}).get("paper") or {}).get("summary")
        current = (draft.get("paper") or {}).get("summary")
        if not isinstance(original, str) or current != original:
            raise ValueError("总结可能已经人工改写，停止覆盖")
        snapshot = evidence.upload_snapshot(task_id, int(state["user_id"]))
        record = next(row for row in snapshot["records"] if row["field"] == "paper.summary")
        with SessionLocal() as session:
            from backend.ingest.manual_evidence import table_available
            if table_available(session) and session.scalar(select(ScientificManualEvidence.id).where(
                ScientificManualEvidence.target == "upload", ScientificManualEvidence.target_id == task_id,
                ScientificManualEvidence.item_key == record["item_key"]).limit(1)) is not None:
                raise ValueError("总结存在人工修改记录，停止覆盖")
        fingerprint = hashlib.sha256(json.dumps(
            [(item.get("file_id"), item.get("sha256")) for item in files],
            ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return state, draft, artifact, snapshot, record, fingerprint

    with upload_task_lock(task_id):
        state, draft, artifact, baseline, _, fingerprint = inspect_current()
        owner = int(state["user_id"])
        sources = task_sources(task_id, state, data_path("parsed_markdown"))
        abstract = str((draft.get("paper") or {}).get("abstract") or "")

    if generated_summary is not None and not valid_summary(generated_summary, abstract):
        raise ValueError("已有生成候选未通过当前摘要的格式检查")
    summary, error = choose_summary(generated_summary or "", abstract, sources,
        lambda prompt, payload: complete_json(prompt, json.dumps(payload, ensure_ascii=False)))
    if error:
        raise ValueError(f"模型未生成可靠总结：{error}")
    updated = json.loads(json.dumps(draft, ensure_ascii=False))
    updated["paper"]["summary"] = summary
    updated["summary_error"] = None
    updated["generation_issues"] = [item for item in updated.get("generation_issues") or []
                                    if not isinstance(item, dict) or item.get("field") != "paper.summary"]
    candidate_snapshot = evidence.upload_snapshot(task_id, owner, parsing_draft=updated)
    record = next(row for row in candidate_snapshot["records"] if row["field"] == "paper.summary")
    candidates, errors = [], []
    for batch in evidence.source_batches(candidate_snapshot["chunks"]):
        result = evidence.evaluate_batch([record], batch, purpose="check")[0]
        candidates.append(result)
        errors.extend(result.get("location_errors") or [])
    checked = evidence.aggregate_candidates([record], {record["key"]: candidates},
                                            {record["key"]: errors}, get_llm_config().model)[record["key"]]

    with upload_task_lock(task_id):
        _, current, latest_artifact, latest, _, latest_fingerprint = inspect_current()
        if latest["version"] != baseline["version"] or latest_fingerprint != fingerprint or current != draft:
            raise ValueError("生成期间草稿或来源已变化，停止覆盖")
        backup_dir = data_path("issue120-backups")
        backup = backup_dir / f"{task_id}-summary-before.json"
        if backup.exists():
            raise ValueError("定向总结备份已存在，停止重复覆盖")
        previous = {}
        with SessionLocal() as session:
            previous = science.load_results(session, latest, owner, include_stale=True).get(record["key"], {})
        backup_payload = json.dumps({"state": state, "draft": draft, "summary_check": previous,
                                     "artifact_summary": ((latest_artifact.get("ai_values") or {}).get("paper") or {}).get("summary")},
                                    ensure_ascii=False, indent=2)
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
            output.write(backup_payload)
        save_draft(task_id, updated)
        with SessionLocal.begin() as session:
            science.save_results(session, {**candidate_snapshot, "records": [record]},
                                 {record["key"]: checked}, owner)
        latest_artifact.setdefault("ai_values", {}).setdefault("paper", {})["summary"] = summary
        latest_artifact["ai_values"]["summary_error"] = None
        latest_artifact["ai_values"]["generation_issues"] = updated["generation_issues"]
        (artifact_path(task_id).parent / "summary_recovery.json").write_text(json.dumps({
            "summary": summary, "review_model": get_llm_config().model, "source_fingerprint": fingerprint,
            "selection": "existing_generated_candidate" if generated_summary is not None else "regenerated",
            "status": checked["status"], "reason": checked.get("reason"),
            "evidences": checked.get("evidences"), "backup": str(backup),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary = artifact_path(task_id).with_suffix(".json.summary.tmp")
        temporary.write_text(json.dumps(latest_artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(artifact_path(task_id))
        if object_mode():
            update_state(task_id, artifact_manifest=publish_artifact_path(task_id))

    final = evidence.upload_snapshot(task_id, owner)
    with SessionLocal() as session:
        saved = science.load_results(session, final, owner)
    final_record = next(row for row in final["records"] if row["field"] == "paper.summary")
    return {"summary": summary, "status": saved[final_record["key"]]["status"],
            "reason": saved[final_record["key"]]["reason"], "evidences": saved[final_record["key"]]["evidences"],
            "backup": str(backup)}
