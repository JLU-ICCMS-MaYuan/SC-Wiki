#!/usr/bin/env python3
"""只重建指定上传草稿的解析诊断，可选核实出版年；默认只读，写入受哈希保护。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def signature(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--expected-main-sha256", required=True)
    parser.add_argument("--expected-year", type=int)
    parser.add_argument("--verify-publication-year", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.parsing_diagnostics import annotate_differences, read_pdf_regions
    from backend.ingest.publication_year import verify_document_year
    from backend.ingest.grobid_document import apply_bibliography
    from backend.rag.config import settings
    from backend.storage.paths import resolve_file, clear_namespace, object_mode

    client = tasks.redis_client()
    before = client.get(tasks.draft_key(args.task_id))
    state_raw = client.get(tasks.task_key(args.task_id))
    if not before or not state_raw:
        raise ValueError("任务或草稿不存在")
    state, draft = json.loads(state_raw), json.loads(before)
    if state.get("status") != "ready" or state.get("paper_id"):
        raise ValueError("仅处理尚未提交的ready草稿")
    files = state.get("files") or []
    main_file = next(f for f in files if f.get("role") == "main")
    if main_file["sha256"] != args.expected_main_sha256:
        raise ValueError("正文身份不匹配")
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / "before-state.json", state)
    dump(args.output / "before-draft.json", draft)
    root = tasks.artifact_directory(args.task_id)
    artifact_source = tasks.available_published_path(args.task_id, tasks.artifact_path(args.task_id))
    artifact_before = artifact_source.read_bytes()
    (args.output / "before-artifact.json").write_bytes(artifact_before)
    docs, paths = {}, {}
    namespace = "diagnostics-" + uuid4().hex
    updated = deepcopy(draft)
    verification = None
    try:
        for file in files:
            fid = file["file_id"]
            ir_path = tasks.available_published_path(args.task_id, root / "document_ir" / f"{fid}.json")
            if ir_path.is_file():
                docs[fid] = DocumentIR.model_validate_json(ir_path.read_text())
                if docs[fid].source_sha256 != file["sha256"]:
                    raise ValueError("IR与来源文件摘要不一致")
                paths[fid] = resolve_file(file["stored_path"], size=file["size"], sha256=file["sha256"], namespace=namespace) if object_mode() else Path(file["stored_path"])
        if args.verify_publication_year:
            if args.expected_year is None or draft["paper"].get("year") != args.expected_year:
                raise ValueError("当前年份与预期旧值不符，停止覆盖")
            document = docs[main_file["file_id"]].coverage["grobid"]
            extracted = next((e.get("extracted_value") for e in draft.get("bibliography_conflicts", []) if e.get("field") == "year"), None)
            verification = verify_document_year(document, {**draft["paper"], "year": extracted}, source_pdf=paths[main_file["file_id"]])
            dump(args.output / "publication-verification.json", verification)
            if not verification or verification.get("status") != "verified":
                raise ValueError("出版资料未通过身份/年份核验，未改草稿")
            patch = {"paper": deepcopy(draft["paper"])}
            apply_bibliography(patch, document, main_ir=docs[main_file["file_id"]], publication_verification=verification)
            new_year = patch["paper"]["year"]
            updated["paper"]["year"] = new_year
            fields = updated.setdefault("bibliography_sources", {}).setdefault("fields", {})
            old = deepcopy(fields.get("year"))
            fields["year"] = patch["bibliography_sources"]["fields"]["year"]
            fields["year"]["correction_history"] = [*(old or {}).get("correction_history", []), {
                "before": draft["paper"].get("year"), "after": new_year, "origin": "verified_publication_metadata",
                "occurred_at": datetime.now(timezone.utc).isoformat(), "previous_source": old}]
            for item in updated.get("bibliography_conflicts") or []:
                if item.get("field") == "year":
                    item["selected_value"] = new_year
        updated = annotate_differences(updated, docs, files, pdf_regions=read_pdf_regions(docs, paths))
    finally:
        clear_namespace(namespace)
    from collections import Counter
    summary = {"task_id": args.task_id, "applied": False, "rule_version": "parsing-triage-v1",
               "regions": len(updated.get("parsing_conflicts", [])), "bibliography": len(updated.get("bibliography_conflicts", [])),
               "categories": dict(Counter(r["triage"]["category"] for r in updated.get("parsing_conflicts", []))),
               "statuses": dict(Counter(r["triage"]["status"] for r in updated.get("parsing_conflicts", []))),
               "year_before": draft["paper"].get("year"), "year_after": updated["paper"].get("year"),
               "publication_verification": verification, "before_draft_sha256": signature(before)}
    # 只允许诊断、年份和其出处变化；其余科学数据严格保持。
    a, b = deepcopy(draft), deepcopy(updated)
    for value in (a, b):
        value["paper"].pop("year", None)
        for field in ("parsing_conflicts", "bibliography_conflicts", "bibliography_sources"):
            value.pop(field, None)
    assert a == b, "诊断重建不得改动其他科学字段"
    dump(args.output / "candidate.json", updated)
    dump(args.output / "report.json", summary)
    if args.apply:
        with tasks.upload_task_lock(args.task_id):
            current = client.get(tasks.draft_key(args.task_id))
            current_state = json.loads(client.get(tasks.task_key(args.task_id)) or "{}")
            if (current != before or current_state.get("status") != "ready" or current_state.get("paper_id")
                    or current_state.get("files") != files):
                raise ValueError("诊断期间草稿、文件或任务状态变化，未覆盖当前内容")
            latest = tasks.available_published_path(args.task_id, tasks.artifact_path(args.task_id))
            if latest.read_bytes() != artifact_before:
                raise ValueError("AI初稿期间发生变化，停止写回")
            artifact = json.loads(artifact_before)
            ai = artifact.setdefault("ai_values", {})
            for field in ("parsing_conflicts", "bibliography_conflicts", "bibliography_sources"):
                ai[field] = deepcopy(updated.get(field))
            if verification:
                ai.setdefault("paper", {})["year"] = updated["paper"]["year"]
            tasks.save_draft(args.task_id, updated, value_origin="model")
            destination = tasks.artifact_path(args.task_id)
            temporary = destination.with_suffix(".diagnostics.tmp")
            dump(temporary, artifact)
            temporary.replace(destination)
            if object_mode():
                tasks.update_state(args.task_id, artifact_manifest=tasks.publish_artifact_path(args.task_id))
        restored = tasks.get_draft(args.task_id)
        assert restored["paper"]["year"] == updated["paper"]["year"]
        assert restored["material_states"] == updated["material_states"]
        summary.update(applied=True, scientific_values_preserved=True)
        dump(args.output / "restored.json", restored)
        dump(args.output / "report.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
