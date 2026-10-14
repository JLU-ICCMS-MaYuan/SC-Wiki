"""通过正式四工具适配器重跑案例，保存真实来源和同一科学契约结果。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
from backend.ingest.document_parsers import DocumentSource, ParseOptions, parse_with_profile
from backend.ingest.domain_extraction import structured_chunks, normalize_extraction, COMPLEMENTARY_SYSTEM_PROMPT, merge_scientific_candidates
from backend.rag.llm import complete_json
from .parsers import write_json
from .run import validate_case, snapshot


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--extract", action="store_true")
    cli.add_argument("--resume-dir", type=Path)
    cli.add_argument("--reuse-extraction", type=Path, help="仅复用相同输入的真实原模型响应，重做当前校验并记录来源")
    args = cli.parse_args()
    case = validate_case(args.case)
    root = args.output / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "baseline.json", snapshot(root))
    write_json(root / "case.json", case)
    print(f"OUTPUT={root.resolve()}", flush=True)
    candidates = []
    for item in case["files"]:
        source = DocumentSource(Path(item["path"]), item["file_id"], item["role"], item["sha256"])
        previous = args.resume_dir / (item["file_id"]+".ir.json") if args.resume_dir else None
        if previous and previous.is_file():
            from backend.ingest.document_ir import DocumentIR
            from types import SimpleNamespace
            ir = DocumentIR.model_validate_json(previous.read_text())
            if ir.source_sha256 != source.sha256 or ir.source_file_id != source.file_id:
                raise ValueError("复用 IR 身份不符")
            run = SimpleNamespace(reused_from=str(previous), status="reused")
        else:
            ir, run = parse_with_profile(source, ParseOptions(profile="complementary", parser_options={"artifact_directory": str(root / item["file_id"])}))
        (root / (item["file_id"]+".ir.json")).write_text(ir.model_dump_json(indent=2), encoding="utf-8")
        write_json(root / (item["file_id"]+".run.json"), {**run.__dict__, "components": ir.coverage["component_runs"]})
        chunks = structured_chunks(ir)
        print(item["file_id"], "components", ir.coverage["component_runs"], "chunks", [len(c.content) for c in chunks], flush=True)
        if args.extract:
            for chunk in chunks:
                context = json.loads(chunk.content)
                directory = root / "extraction" / item["file_id"] / str(chunk.chunk_index)
                write_json(directory / "input.json", context)
                previous_extraction = args.reuse_extraction / "extraction" / item["file_id"] / str(chunk.chunk_index) if args.reuse_extraction else None
                if previous_extraction and (previous_extraction / "raw.json").is_file():
                    if json.loads((previous_extraction / "input.json").read_text()) != context:
                        raise ValueError("模型响应复用的原始输入不一致")
                    raw = json.loads((previous_extraction / "raw.json").read_text())
                    write_json(directory / "reuse.json", {"raw_from":str(previous_extraction / "raw.json"), "inference_reused":True})
                else:
                    raw = complete_json(COMPLEMENTARY_SYSTEM_PROMPT, chunk.content, read_timeout=600, retries=0,
                                        on_partial=lambda text: (directory / "response.txt").write_text(text, encoding="utf-8"))
                write_json(directory / "raw.json", raw)
                value = normalize_extraction(raw,
                    allowed_blocks={(context["file_id"], b["pdf_page"], b["block_id"]) for p in context["pages"] for b in p["blocks"]},
                    allowed_tables={(context["file_id"], t["table_id"]): t["row_count"] for p in context["pages"] for t in p["tables"]},
                    allowed_pages={(context["file_id"], p["geometry"]["pdf_page"]) for p in context["pages"]}, form_parameters=True,
                    allowed_quote_text={(context["file_id"], b["pdf_page"], b["block_id"]): b["text"] for p in context["pages"] for b in p["blocks"]})
                value["_source"] = {"file_id": item["file_id"]}
                write_json(directory / "normalized.json", value)
                from backend.ingest.document_claims import claims_from_candidates
                claims = claims_from_candidates(value, {ir.source_file_id: ir})
                write_json(directory / "claims.json", [claim.model_dump(mode="json") for claim in claims])
                if any(claim.status != "validated" for claim in claims):
                    raise ValueError("真实科学候选仍有无法定位的原文来源")
                candidates.append(value)
    if candidates:
        states = merge_scientific_candidates(candidates)
        write_json(root / "scientific.json", {"material_states": states})
        print("STATES", [(s["material"], s.get("reported_space_group_symbol"), s.get("pressure_value_gpa")) for s in states], flush=True)


if __name__ == "__main__":
    main()
