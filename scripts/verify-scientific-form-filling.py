#!/usr/bin/env python3
"""＃176 从已核对原 PDF 文本真实重提，正式整理并隔离保存；不写原任务。"""
from pathlib import Path
import argparse
from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    config = read_config(ROOT)
    validate_local(config, ROOT)
    os.environ.update(config)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.domain_extraction import COMPLEMENTARY_SYSTEM_PROMPT, structured_chunks, normalize_extraction
    from backend.ingest.state_optimization import assemble_candidates
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    from backend.ingest.document_claims import claims_from_candidates, missing_tc_after_filling
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import get_llm_config
    from backend.rag.config import settings
    client = tasks.redis_client()
    original_state = client.get(tasks.task_key(args.task_id))
    original_draft = client.get(tasks.draft_key(args.task_id))
    state = json.loads(original_state)
    root = settings.sc_wiki_data_dir / "review_artifacts" / args.task_id
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"passed": False, "task": args.task_id, "started": time.time(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "reused": ["已核对原 PDF 文字与 IR"], "rerun": ["科学字段 AI 提取", "模型整理与查缺", "来源定位", "隔离草稿保存重读"],
              "not_run": ["原任务写入", "整篇 PDF 工具重跑", "整篇业务提交"]}
    model = get_llm_config()
    report["model"] = {"provider": model.provider, "model": model.model}
    report["source_hashes"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [ROOT / "backend/ingest/scientific_form_filling.py", ROOT / "backend/ingest/domain_extraction.py",
                                       ROOT / "backend/ingest/document_claims.py"]}
    try:
        contexts, documents, chunks, source_info = [], {}, [], []
        for file in state["files"]:
            if file["role"] not in {"main", "supplementary"}:
                continue
            path = root / "document_ir" / (file["file_id"] + ".json")
            ir = DocumentIR.model_validate_json(path.read_text())
            assert ir.source_sha256 == file["sha256"]
            pages = {p.pdf_page for p in ir.pages} if file["role"] == "main" else {1, 2, 3, 19}
            chosen = ir.model_copy(deep=True)
            chosen.pages = [p for p in chosen.pages if p.pdf_page in pages]
            chosen.blocks = [b for b in chosen.blocks if b.pdf_page in pages]
            chosen.tables = [t for t in chosen.tables if t.pdf_page in pages]
            documents[file["file_id"]] = chosen
            for chunk in structured_chunks(chosen):
                contexts.append(json.loads(chunk.content))
            # 查缺可读取全部已核对 SI，不局限于首轮提取页。
            for chunk in structured_chunks(ir):
                chunks.append({"file_id": file["file_id"], "file_role": file["role"], "content": chunk.content})
            source_info.append({"file_id": file["file_id"], "sha256": file["sha256"], "pages_reextracted": sorted(pages),
                                "ir_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        system = COMPLEMENTARY_SYSTEM_PROMPT + (
            "\nFIELD VALIDATION: Extract the reported Tc results, their parameters/conditions and adjacent "
            "band_gap/dos_fermi results from these main/SI pages. Do not digitize curves. "
            "Do not invent missing numbers; use the normal extraction schema. No prefilled answers are supplied.")
        prompt = json.dumps({"source_documents": contexts}, ensure_ascii=False)
        dump(args.output / "extraction-input.json", {"system": system, "prompt": prompt, "sources": source_info})
        quotes = {(c["file_id"], b["pdf_page"], b["block_id"]): b["text"]
                  for c in contexts for p in c["pages"] for b in p["blocks"]}
        error = None
        for attempt in range(2):
            raw = complete_json(system, prompt + ("\nCorrect the prior response using these errors: " + error if error else ""))
            dump(args.output / f"extraction-{attempt}.json", raw)
            try:
                extracted = normalize_extraction(raw, allowed_blocks=set(quotes), allowed_quote_text=quotes,
                    allowed_tables={(c["file_id"], t["table_id"]): int(t.get("row_count") or 0)
                                    for c in contexts for p in c["pages"] for t in p.get("tables", [])},
                    allowed_pages={(c["file_id"], p["geometry"]["pdf_page"]) for c in contexts for p in c["pages"]},
                    form_parameters=True)
                break
            except Exception as exc:
                error = str(exc)
                if attempt == 1:
                    raise
        dump(args.output / "extracted.json", extracted)
        before = assemble_candidates([extracted])
        filled, audit = fill_scientific_forms(before, chunks, complete_json,
            on_attempt=lambda a: dump(args.output / "filling.json", a))
        dump(args.output / "filled.json", filled)
        if audit["status"] != "completed":
            raise AssertionError("模型整理未完成；失败报告已保留")
        # 完整原 IR 验证最终查缺来源；不能只检查初次选页。
        all_documents = {f["file_id"]: DocumentIR.model_validate_json(
            (root / "document_ir" / (f["file_id"] + ".json")).read_text())
            for f in state["files"] if f["role"] in {"main", "supplementary"}}
        initial = claims_from_candidates({"material_states": before}, all_documents)
        final = claims_from_candidates({"material_states": filled}, all_documents)
        dump(args.output / "claims.json", [c.model_dump(mode="json") for c in final])
        assert all(c.status == "validated" for c in final), "最终来源未全部定位"
        assert not missing_tc_after_filling(initial, final, input_states=before, output_states=filled,
            filling_report=audit, documents=all_documents)
        draft = _normalize_draft({"paper": {"title": "Isolated field validation"}, "material_states": filled})
        shadow = uuid4().hex
        keys = [tasks.task_key(shadow), tasks.draft_key(shadow)]
        assert client.set(keys[0], json.dumps({"task_id": shadow, "is_shadow": True, "status": "ready"}), ex=300, nx=True)
        try:
            saved = tasks.save_draft(shadow, deepcopy(draft))
            restored = tasks.get_draft(shadow)
            assert saved == restored
            dump(args.output / "restored.json", restored)
        finally:
            client.delete(*keys)
        target = [s for s in restored["material_states"] if s.get("material") == "CaH6" and s.get("pressure_value_gpa") == 150]
        assert len(target) == 1
        records = [r for m in target[0]["property_modules"] for r in m["records"] if r["property_code"] == "tc"]
        assert len(records) == 2, "150 GPa 不应重复保存范围或图注"
        assert {(r["value_number"], r["payload"]["parameters"].get("mu_star")) for r in records} == {(220, .13), (235, .1)}
        assert all(r["payload"]["parameters"].get("lambda_ep") == 2.69 and not r["payload"]["parameters"].get("omega_log") for r in records)
        assert len({r["payload"]["tc_group"]["group_key"] for r in records}) == 1
        report.update(passed=True, sources=source_info, disposition_count=len(audit["candidate_dispositions"]),
                      record_count=sum(len(m["records"]) for s in filled for m in s["property_modules"]),
                      roundtrip_equal=True)
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["original_state_unchanged"] = client.get(tasks.task_key(args.task_id)) == original_state
        report["original_draft_unchanged"] = client.get(tasks.draft_key(args.task_id)) == original_draft
        report["elapsed_seconds"] = time.time() - report["started"]
        dump(args.output / "report.json", report)
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
