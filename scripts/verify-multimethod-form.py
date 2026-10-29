#!/usr/bin/env python3
"""＃176：原 PDF 表格的多方法定向提取；预期答案只用于输出验收，不进入提示词。"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    config = read_config(ROOT); validate_local(config, ROOT); os.environ.update(config)
    from backend.ingest.document_parsers import PyMuPDFParser, DocumentSource, ParseOptions
    from backend.ingest.domain_extraction import COMPLEMENTARY_SYSTEM_PROMPT, structured_chunks, normalize_extraction
    from backend.ingest.state_optimization import assemble_candidates
    from backend.ingest.scientific_form_filling import fill_scientific_forms, form_sources
    from backend.ingest.document_claims import claims_from_candidates
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.ingest import upload_tasks as tasks
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import get_llm_config
    args.output.mkdir(parents=True, exist_ok=False)
    def dump(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+"\n")
    model = get_llm_config()
    report = {"passed": False, "source": str(args.pdf), "sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
              "model": {"provider": model.provider, "model": model.model}, "scope": "ThH10 100 GPa 表格及上下文",
              "source_commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "source_hashes": {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [ROOT/"backend/ingest/scientific_form_filling.py",
                                          ROOT/"backend/ingest/domain_extraction.py"]}}
    try:
        ir = PyMuPDFParser().parse(DocumentSource(args.pdf, "main"), ParseOptions())
        dump("document-ir.json", ir.model_dump(mode="json"))
        contexts = [json.loads(c.content) for c in structured_chunks(ir)]
        system = COMPLEMENTARY_SYSTEM_PROMPT + (
            "\nFIELD SCOPE: Extract all reported predicted Tc methods/results for ThH10 at 100 GPa, "
            "including common lambda, omega_log, each mu_star and its corresponding Tc, from the "
            "table and its footnote plus relevant body/Methods. Do not extract other pressures/materials. "
            "Do not read values from curves. Use the normal schema. No expected answer is supplied.")
        prompt = json.dumps({"source_documents": contexts}, ensure_ascii=False)
        dump("input.json", {"system_prompt": system, "prompt": prompt})
        quotes = {(c["file_id"], b["pdf_page"], b["block_id"]): b["text"]
                  for c in contexts for p in c["pages"] for b in p["blocks"]}
        error = ""
        for attempt in range(2):
            raw = complete_json(system, prompt + ("\nCorrect this validation error: "+error if error else ""))
            dump(f"raw-{attempt}.json", raw)
            try:
                extracted = normalize_extraction(raw, allowed_blocks=set(quotes), allowed_quote_text=quotes, form_parameters=True,
                    allowed_tables={(c["file_id"],t["table_id"]):int(t.get("row_count") or 0) for c in contexts for p in c["pages"] for t in p.get("tables",[])},
                    allowed_pages={(c["file_id"],p["geometry"]["pdf_page"]) for c in contexts for p in c["pages"]})
                break
            except Exception as exc:
                error = str(exc)
                if attempt == 1: raise
        dump("extracted.json", extracted)
        filled, audit = fill_scientific_forms(assemble_candidates([extracted]),
            form_sources({"main": ir}, [{"file_id":"main","file_role":"main","content":""}]), complete_json,
            on_attempt=lambda a: dump("filling.json", a))
        dump("filled.json", filled)
        assert audit["status"] == "completed"
        claims = claims_from_candidates({"material_states": filled}, {"main": ir})
        dump("claims.json", [c.model_dump(mode="json") for c in claims])
        assert all(c.status == "validated" for c in claims)
        draft = _normalize_draft({"paper":{"title":"Isolated ThH10 field validation"},"material_states":filled})
        client = tasks.redis_client(); key = uuid4().hex
        keys = [tasks.task_key(key),tasks.draft_key(key)]
        assert client.set(keys[0],json.dumps({"task_id":key,"is_shadow":True,"status":"ready"}),ex=300,nx=True)
        try:
            saved = tasks.save_draft(key,deepcopy(draft)); restored = tasks.get_draft(key)
            assert saved == restored
            dump("restored.json",restored)
        finally:
            client.delete(*keys)
        records = [r for s in restored["material_states"] for m in s["property_modules"] for r in m["records"]]
        assert len(records) == 6
        actual = {(r["method_code"],r["value_number"],r["payload"]["parameters"].get("mu_star")) for r in records}
        assert {("mcmillan",176.8,.1),("mcmillan",160.3,.15),("allen_dynes",221.1,.1),("allen_dynes",193.9,.15)} <= actual
        eliashberg = [r for r in records if r["method_code"] not in {"mcmillan","allen_dynes"}]
        assert {(r["value_number"],r["payload"]["parameters"].get("mu_star")) for r in eliashberg} == {(241.2,.1),(220,.15)}
        assert len({r["payload"]["tc_group"]["method_key"] for r in records}) == 3
        assert len({r["payload"]["tc_group"]["group_key"] for r in records}) == 1
        assert all(r["payload"]["parameters"].get("lambda_ep")==2.5 and r["payload"]["parameters"].get("omega_log")==1073 for r in records)
        report.update(passed=True,records=sorted(actual),roundtrip=True,source_locations_valid=True,
                      source_unchanged=hashlib.sha256(args.pdf.read_bytes()).hexdigest()==report["sha256"])
    except Exception as exc:
        report["error"]={"type":type(exc).__name__,"message":str(exc)}
        raise
    finally:
        dump("report.json",report)
        print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    main()
