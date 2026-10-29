#!/usr/bin/env python3
"""#181：从同哈希原PDF/IR重新提取方法字段，正式后处理与隔离保存，不恢复旧任务。"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source-task", required=True, help="只读获取同哈希原文件的位置，不修改该任务")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    config = read_config(ROOT); validate_local(config, ROOT); os.environ.update(config)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.domain_extraction import COMPLEMENTARY_SYSTEM_PROMPT, structured_chunks, normalize_extraction
    from backend.ingest.state_optimization import resolve_candidates, assemble_candidates
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import get_llm_config
    from backend.storage.paths import resolve_file, clear_namespace
    args.output.mkdir(parents=True, exist_ok=False)
    def dump(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    client = tasks.redis_client()
    original = {key:client.get(key) for key in (tasks.task_key(args.source_task), tasks.draft_key(args.source_task))}
    source_state = json.loads(original[tasks.task_key(args.source_task)] or "{}")
    archived = json.loads((args.archive / "run-6-ready/state.json").read_text())
    shadow = uuid4().hex
    namespace = "methods-" + shadow
    model = get_llm_config()
    report = {"passed":False,"started":time.time(),"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "model":{"provider":model.provider,"model":model.model},
        "reused":["已核对同源IR文字，未更改文字提取"],"rerun":["受影响字段AI提取","结构工作流关联","正式科学整理","正式组装归一化","隔离草稿保存重读"],
        "not_run":["原任务恢复或业务写入","旧47项核查","全文OCR","论文提交批准"],"sources":[],
        "source_hashes":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
            "backend/ingest/domain_extraction.py","backend/ingest/calculation_methods.py","backend/ingest/state_optimization.py",
            "backend/ingest/scientific_form_filling.py","backend/ingest/material_state_contract.py")}}
    keys=[tasks.task_key(shadow),tasks.draft_key(shadow)]
    created=False
    try:
        contexts=[];documents={};chunks=[];files=[]
        for f in archived["files"]:
            if f["role"] not in {"main","supplementary"}:
                continue
            ir_path=args.archive/"document_ir"/(f["file_id"]+".json")
            ir=DocumentIR.model_validate_json(ir_path.read_text())
            assert ir.source_sha256==f["sha256"]
            alternate=next((r for r in source_state.get("files",[]) if r.get("sha256")==f["sha256"]),f)
            source=args.archive/"main-source.pdf" if f["role"]=="main" else resolve_file(
                alternate["stored_path"],size=alternate["size"],sha256=alternate["sha256"],namespace=namespace)
            assert hashlib.sha256(source.read_bytes()).hexdigest()==ir.source_sha256
            import pymupdf
            with pymupdf.open(source) as pdf:
                assert len(pdf)==len(ir.pages)
            pages={p.pdf_page for p in ir.pages} if f["role"]=="main" else {1,2,3,4,5,9,10,19}
            selected=ir.model_copy(deep=True)
            selected.pages=[p for p in ir.pages if p.pdf_page in pages]
            selected.blocks=[b for b in ir.blocks if b.pdf_page in pages]
            selected.tables=[t for t in ir.tables if t.pdf_page in pages]
            documents[f["file_id"]]=selected
            contexts.extend(json.loads(c.content) for c in structured_chunks(selected))
            for chunk in structured_chunks(ir):
                chunks.append({"file_id":f["file_id"],"file_role":f["role"],"sha256":f["sha256"],"content":chunk.content})
            files.append({**f,"stored_path":alternate["stored_path"]})
            report["sources"].append({"role":f["role"],"sha256":ir.source_sha256,"file_id":f["file_id"],
                "ir_sha256":hashlib.sha256(ir_path.read_bytes()).hexdigest(),"reextracted_pages":sorted(pages),"pdf_checked":True})
        quotes={(c["file_id"],b["pdf_page"],b["block_id"]):b["text"] for c in contexts for p in c["pages"] for b in p["blocks"]}
        system=COMPLEMENTARY_SYSTEM_PROMPT+(
            "\nFIELD SCOPE: Re-extract explicitly reported electronic band gaps and Fermi-level electronic DOS of calcium hydrides, "
            "their electronic methods, and adjacent reported Tc/EPC conditions. Read the original Methods, table/figure captions, "
            "phase/pressure and SI context. Separate electronic theory, phonon technique, vibration treatment and actual geometry "
            "optimization. Do not digitize curves or invent values. Use only these original sources and the normal schema; no expected answers are supplied.")
        prompt=json.dumps({"source_documents":contexts},ensure_ascii=False)
        dump("input.json",{"system":system,"prompt":prompt})
        error=""
        for attempt in range(3):
            raw=complete_json(system,prompt+("\nCorrect the previous response: "+error if error else ""),
                on_call=lambda event:dump("extraction-call-"+str(attempt)+"-"+str(event["attempt"])+".json",event))
            dump("extraction-"+str(attempt)+".json",raw)
            try:
                extracted=normalize_extraction(raw,allowed_blocks=set(quotes),allowed_quote_text=quotes,
                    allowed_tables={(c["file_id"],t["table_id"]):int(t.get("row_count") or 0) for c in contexts for p in c["pages"] for t in p.get("tables",[])},
                    allowed_pages={(c["file_id"],p["geometry"]["pdf_page"]) for c in contexts for p in c["pages"]},form_parameters=True)
                break
            except Exception as exc:
                error=str(exc)
                if attempt==2:raise
        dump("extracted.json",extracted)
        source_texts=[]
        for fid,ir in documents.items():
            source_texts.append({"file_id":fid,"content":"\n\n".join(b.text for b in ir.blocks)})
        optimization=[]
        resolved,issues=resolve_candidates([extracted],source_texts,complete_json,on_response=lambda r:optimization.append(r))
        dump("optimization.json",{"responses":optimization,"issues":issues})
        assert not issues,issues
        states=assemble_candidates(resolved)
        filled,filling=fill_scientific_forms(states,chunks,complete_json,on_attempt=lambda r:dump("filling.json",r),max_rounds=3)
        assert filling["status"]=="completed",filling.get("issues")
        normalized=_normalize_draft({"paper":{},"material_states":filled})
        dump("normalized.json",normalized)
        assert client.set(keys[0],json.dumps({"task_id":shadow,"is_shadow":True,"status":"ready","created_at":int(time.time()),"files":files}),nx=True,ex=300)
        created=True
        saved=tasks.save_draft(shadow,deepcopy(normalized),value_origin="model")
        restored=tasks.get_draft(shadow)
        assert saved==restored
        dump("restored.json",restored)
        rows=[{"material":s.get("material"),"pressure":s.get("pressure_value_gpa"),"optimization":s.get("structure_optimization"),
               "code":r["property_code"],"value":r.get("value_number"),"name":r.get("name_raw"),
               "conditions":r.get("payload",{}).get("calculation_conditions"),"sources":len(r.get("evidences") or [])}
              for s in restored["material_states"] for m in s["property_modules"] for r in m["records"]]
        report["rows"] = rows
        assert any(r["material"]=="CaH2" and r["pressure"]==0 and r["code"]=="band_gap" and abs(r["value"]-3.05)<1e-8 for r in rows)
        assert any(r["material"]=="CaH2" and r["pressure"]==150 and r["code"]=="band_gap" and abs(r["value"]-.48)<1e-8 for r in rows)
        assert any(r["material"]=="CaH4" and r["code"]=="dos_fermi" and r["pressure"] in (None,50) for r in rows)
        assert all(r["sources"] for r in rows)
        from backend.ingest.calculation_methods import validate_extracted_methods
        validate_extracted_methods(restored)
        assert all(client.get(k)==v for k,v in original.items())
        report.update(passed=True,rows=rows,roundtrip_equal=True,source_task_unchanged=True)
    except Exception as exc:
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
        raise
    finally:
        if created:client.delete(*keys)
        clear_namespace(namespace)
        report["elapsed_seconds"]=time.time()-report["started"]
        dump("report.json",report)
        print(json.dumps({k:report.get(k) for k in ("passed","model","elapsed_seconds","error")},ensure_ascii=False))


if __name__=="__main__":
    main()
