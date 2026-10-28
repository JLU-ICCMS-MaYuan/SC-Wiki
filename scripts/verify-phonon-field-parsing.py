#!/usr/bin/env python3
"""#172 字段验证：只读原任务，重放或从指定原文页重新提取，隔离保存重读。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def records(value):
    return [r for s in value["material_states"] for m in s["property_modules"] for r in m["records"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--response", type=Path, help="固定失败响应 raw.json；读取旁边的 input.json")
    parser.add_argument("--source", action="append", default=[], help="真实读取 file_id:页码,页码；包含必要正文/SI")
    parser.add_argument("--live", action="store_true", help="明确启用真实模型调用")
    parser.add_argument("--output", type=Path, required=True, help="必须是尚不存在的隔离目录")
    args = parser.parse_args()
    if bool(args.response) == args.live or (args.live and not args.source):
        parser.error("请选择 --response 重放，或 --live 配合 --source 重新提取")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.domain_extraction import (
        COMPLEMENTARY_SYSTEM_PROMPT, structured_chunks, normalize_extraction, merge_scientific_candidates,
    )
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.rag.config import settings

    client = tasks.redis_client()
    state_raw = client.get(tasks.task_key(args.task_id))
    if not state_raw:
        raise RuntimeError("原任务不存在；不创建或恢复原任务")
    state = json.loads(state_raw)
    root = settings.sc_wiki_data_dir / "review_artifacts" / args.task_id
    args.output.mkdir(parents=True, exist_ok=False)
    contexts, sources, before = [], [], {}
    report = {"mode": "fresh_field_extraction" if args.live else "saved_response_replay",
              "source_task": args.task_id, "started_at": time.time(), "passed": False,
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_hashes": {str(p.relative_to(ROOT)): digest(p) for p in [
                  ROOT / "backend/ingest/domain_extraction.py", ROOT / "backend/ingest/property_extensions.py",
                  ROOT / "backend/ingest/calculation_methods.py", ROOT / "backend/ingest/condition_rules.py"]},
              "reused": ["PDF 文字提取和 IR"],
              "not_run": ["整篇 PDF 工具解析", "无关字段提取", "全篇覆盖门", "业务任务重新排队", "MySQL 正式提交"]}
    try:
        if args.response:
            before[args.response] = digest(args.response)
            input_path = args.response.parent / "input.json"
            before[input_path] = digest(input_path)
            original = json.loads(input_path.read_text())
            prompt = original["prompt"]
            # 契约重试的原提示在来源 JSON 后附加错误反馈；只解码首个来源对象。
            context, _ = json.JSONDecoder().raw_decode(prompt[prompt.index("{"):])
            contexts = context.get("source_documents", [context])
            raw = json.loads(args.response.read_text())
            report["response_path"] = str(args.response)
            report["model"] = original.get("model")
        else:
            for selection in args.source:
                file_id, pages = selection.split(":", 1)
                selected_pages = {int(page) for page in pages.split(",")}
                file = next(f for f in state["files"] if f["file_id"] == file_id)
                ir_path = root / "document_ir" / f"{file_id}.json"
                before[ir_path] = digest(ir_path)
                ir = DocumentIR.model_validate_json(ir_path.read_text())
                if ir.source_sha256 != file["sha256"]:
                    raise RuntimeError("IR 与上传 PDF 的 SHA-256 不一致")
                ir = ir.model_copy(deep=True)
                ir.pages = [p for p in ir.pages if p.pdf_page in selected_pages]
                if {p.pdf_page for p in ir.pages} != selected_pages:
                    raise RuntimeError("指定页码不完整")
                ir.blocks = [b for b in ir.blocks if b.pdf_page in selected_pages]
                ir.tables = [t for t in ir.tables if t.pdf_page in selected_pages]
                contexts.extend(json.loads(chunk.content) for chunk in structured_chunks(ir))
                sources.append({"file_id": file_id, "filename": file["original_filename"],
                                "role": file["role"], "pdf_sha256": ir.source_sha256,
                                "ir_sha256": digest(ir_path), "pages": sorted(selected_pages)})
            from backend.rag.llm import complete_json
            from backend.rag.llm_context import get_llm_config
            config = get_llm_config()
            report["model"] = {"provider": config.provider, "model": config.model}
            # 只缩小本次验证的输出范围，不提供预填科学答案；仍使用正式提取契约。
            system = COMPLEMENTARY_SYSTEM_PROMPT + "\nFIELD REGRESSION SCOPE: From these original main/SI pages, extract only ONE representative predicted Tc record for CaH6 with its reported material/pressure and evidences, and ONLY these calculation conditions: phonon_method, calculation_code, exchange_correlation_functional. Keep the necessary Tc/method context from the source; do not extract other materials or unrelated properties/parameters. Include the source blocks for every condition. Other software/stages must not justify QE settings. Do not supply an answer absent from the provided source."
            prompt = json.dumps({"source_documents": contexts}, ensure_ascii=False)
            dump(args.output / "input.json", {"system_prompt": system, "prompt": prompt, "sources": sources})
            raw = complete_json(system, prompt,
                on_call=lambda event: dump(args.output / f"call-{event['attempt']}.json", event))
        dump(args.output / "raw.json", raw)
        # 区分格式整理保留候选与原文检查剔除候选，不能把缺证误报成格式丢值。
        from backend.ingest.property_extensions import normalize_extracted_conditions
        shaped = deepcopy(raw)
        for record in records(shaped):
            normalize_extracted_conditions(record)
        report["phonon_candidates_before_source_check"] = [
            e for r in records(shaped) for e in r.get("payload", {}).get("calculation_conditions", {}).get("extensions", [])
            if e.get("key") == "electron_phonon.phonon_method"]
        quotes = {(c["file_id"], b["pdf_page"], b["block_id"]): b["text"]
                  for c in contexts for p in c["pages"] for b in p["blocks"]}
        normalized = normalize_extraction(raw, allowed_blocks=set(quotes),
            allowed_quote_text=quotes, form_parameters=True,
            allowed_tables={(c["file_id"], t["table_id"]): int(t.get("row_count") or 0)
                            for c in contexts for p in c["pages"] for t in p.get("tables", [])},
            allowed_pages={(c["file_id"], p["geometry"]["pdf_page"]) for c in contexts for p in c["pages"]})
        dump(args.output / "normalized.json", normalized)
        draft = _normalize_draft({"material_states": merge_scientific_candidates([normalized])})
        shadow = uuid4().hex
        report["shadow_task"] = shadow
        keys = [tasks.task_key(shadow), tasks.draft_key(shadow)]
        if not client.set(keys[0], json.dumps({"task_id": shadow, "is_shadow": True,
                "created_at": int(time.time()), "status": "ready"}), ex=300, nx=True):
            raise RuntimeError("隔离验证键冲突")
        try:
            saved = tasks.save_draft(shadow, deepcopy(draft))
            restored = tasks.get_draft(shadow)
            if restored != saved:
                raise AssertionError("正式草稿保存重读不一致")
            dump(args.output / "restored.json", restored)
        finally:
            client.delete(*keys)
        conditions = [r["payload"].get("calculation_conditions", {}) for r in records(restored)]
        methods = [e for c in conditions for e in c.get("extensions", [])
                   if e.get("key") == "electron_phonon.phonon_method"]
        if args.live:
            if not methods:
                raise AssertionError("本次重新提取未得到有依据的声子方法，不能宣布通过")
            if not any("espresso" in str(c.get("calculation_code", "")).lower() for c in conditions):
                raise AssertionError("本次字段重跑未保留明确的软件归属")
            if any(c.get("exchange_correlation_functional") or any(
                    e.get("key") in {"exchange_correlation_functional", "electron_phonon.exchange_correlation_functional"}
                    and (e.get("value_raw") or e.get("value_text")) for e in c.get("extensions", []))
                   for c in conditions if "espresso" in str(c.get("calculation_code", "")).lower()):
                raise AssertionError("CaH6 来源未明确 QE 泛函，不允许填入")
        if any(digest(p) != sha for p, sha in before.items()):
            raise AssertionError("只读输入发生变化")
        report.update(passed=True, sources=sources, original_files_unchanged=True,
                      saved_roundtrip_equal=True, record_count=len(records(restored)),
                      phonon_methods=methods, conditions=conditions,
                      input_hashes={str(p): sha for p, sha in before.items()})
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["elapsed_seconds"] = round(time.time() - report["started_at"], 3)
        dump(args.output / "report.json", report)
        print(json.dumps({k: report.get(k) for k in ("mode", "passed", "model", "record_count", "phonon_methods", "elapsed_seconds", "error")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
