"""四路共用的真实模型提取和证据核验；参考答案不进入本模块。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from dotenv import load_dotenv

# 现有契约模块会导入数据库模型；仅读取现有进程配置，不连接或写入数据库。
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

from backend.ingest.domain_extraction import DOMAIN_SYSTEM_PROMPT, Extraction, SourceQuote, normalize_extraction
from backend.ingest.document_ir import DocumentIR
from backend.ingest.claim_evidence import EvidenceLocator, locate_evidence
from .parsers import write_json

ARMS = ("docling", "mineru", "marker", "complementary")
MAX_CHARS = 500000


class StructureObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material: str
    phase: str | None = None
    pressure_value_gpa: float | None = None
    cell_parameters: dict[str, float] = Field(default_factory=dict)
    atomic_positions: list[dict[str, JsonValue]] = Field(default_factory=list)
    coordinate_mode: str = "unknown"
    missing_information: list[str] = Field(default_factory=list)
    evidences: list[SourceQuote] = Field(min_length=1)


class DemoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction: Extraction
    paper: dict[str, JsonValue]
    paper_evidences: dict[str, list[SourceQuote]] = Field(default_factory=dict)
    structure_observations: list[StructureObservation] = Field(default_factory=list)
    conflicts: list[dict[str, JsonValue]] = Field(default_factory=list)


SYSTEM_PROMPT = DOMAIN_SYSTEM_PROMPT.split("Response must conform exactly to this JSON schema:")[0] + """
The output envelope contains extraction (the scientific contract above), paper, paper_evidences,
structure_observations, and conflicts. Do not output extraction fields at the top level.
The input contains all main and supplementary files, with compact IR blocks. IDs are real source IDs.
Table cells are given once in tables.cells; they are evidence blocks too. Their metadata includes spans.
Some input blocks are spatial alternatives from different engines; spatial overlap does NOT prove semantic
identity. Preserve uncertainty. Never use majority voting or one engine's priority as proof of a value.
If same-condition scientific values conflict, retain their separate candidates with their own quotes and
add a conflicts entry explaining the exact difference and source IDs; never silently choose a number.
Use the supplied file role. Bibliographic metadata belongs to the main paper, not to supplementary headers.
paper should use SC-Wiki fields: title, doi, authors (list of names), journal, year, volume, issue_number,
pages, abstract, paper_type, superconductor_kind, material_families, summary, keywords_tags, methodology,
key_finding, research_motivation, knowledge_graph_title. Unknown values stay null or empty.
Only use published information. Preserve authors/abstract/title; generated summary/methodology/key_finding/
research_motivation/knowledge_graph_title are English. Summary is 3-5 numbered conclusions, one per line.
paper_evidences maps each nonempty paper field to actual exact source quotes. No invented classifications.
Keep crystal cell parameters and reported atomic positions in structure_observations, NOT property_modules.
Report separate phases/pressures and explain missing lattice/coordinate information. Do not infer symmetry
completion or create CIFs. Keep unsupported scientific quantities as coverage exclusions, with their values
and locations in the reason if relevant. A figure's caption is not digitized curve data.
CRITICAL FORM STRUCTURE CHECK BEFORE RESPONDING:
- Always omit is_representative (default false). Representative designation is left to later human review;
  non-Tc properties MUST NOT have is_representative=true, which the actual form validator rejects.
- Each distinct phase AND pressure needs its own material_states entry. Do NOT put records for several
  pressures into one state with null pressure or with the pressure of only the first record. Put the known
  pressure in state.pressure_value_gpa and phase in state.reported_space_group_symbol.
- For every predicted_tc record, payload MUST contain a calculation_conditions OBJECT (even if empty).
  Numerical model parameters belong to the sibling payload.parameters OBJECT. Never flatten these fields
  into payload itself. A valid shape is payload={"calculation_conditions":{},"parameters":{}}.
- Use payload.parameters.lambda_ep, .omega_log, .mu_star for those reported quantities; never omega_log_k.
  Use payload.calculation_conditions.calculation_code, .exchange_correlation, .pseudopotential,
  .energy_cutoff, .k_grid, .q_grid, .smearing for explicitly reported computational settings.
- For a parameter RANGE, preserve the stated range as text/extra detail; do not take an endpoint or pretend
  the current numeric widget represents the whole range. Report the form-expression limitation in conflicts.
- Do not reconstruct a damaged multiplication symbol into a clean grid unless supported by another supplied
  block. Missing symbols stay uncertain. Quotes MUST be actual continuous substrings of the referenced block,
  preserving damaged symbols. Use multiple quotes instead of ellipses or concatenated cell contents.
Respond with a complete JSON object, without markdown fences. Schema:
""" + json.dumps(DemoResponse.model_json_schema(), ensure_ascii=False)


def compact_document(ir, role):
    """只省略可由父文档恢复的重复元数据，不截断正文或表格单元。"""
    tables = {t.block_id: t for t in ir.tables}
    pages = []
    for page in ir.pages:
        blocks = []
        for block in ir.blocks:
            if block.pdf_page != page.pdf_page or block.block_type == "table_cell":
                continue
            row = {"block_id": block.block_id, "kind": str(block.block_type), "text": block.text,
                   "bbox": block.bbox, "engine": block.metadata.get("engine", ir.parser["name"])}
            if block.block_id in tables:
                table = tables[block.block_id]
                row["table"] = {"table_id": table.table_id, "rows": table.row_count, "columns": table.column_count,
                                "cells": [{"block_id": c.block_id, "row": c.row_index, "column": c.column_index,
                                           "text": c.text, "bbox": c.bbox,
                                           "row_span": ir.block(c.block_id).metadata.get("row_span", 1),
                                           "column_span": ir.block(c.block_id).metadata.get("column_span", 1)} for c in table.cells]}
                # 父块文本并不保证等同于单元文本：仅在确实重复时省去。
                if " ".join(block.text.split()) == " ".join(" ".join(c.text for c in table.cells).split()):
                    row["text"] = ""
            for key in ("routing_groups", "selection_role"):
                if key in block.metadata:
                    row[key] = block.metadata[key]
            blocks.append(row)
        pages.append({"pdf_page": page.pdf_page, "blocks": blocks})
    return {"file_id": ir.source_file_id, "role": role, "source_sha256": ir.source_sha256, "pages": pages}


def evidence_rows(value, path=""):
    if isinstance(value, dict):
        if {"file_id", "pdf_page", "block_id", "quote"} <= value.keys():
            yield path, value
        else:
            for key, item in value.items():
                yield from evidence_rows(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from evidence_rows(item, f"{path}/{index}")


def validate_sources(raw, documents, originals):
    allowed = {(ir.source_file_id, b.block_id): b for ir in documents.values() for b in ir.blocks}
    checks = []
    for path, quote in evidence_rows(raw):
        block = allowed.get((quote["file_id"], quote["block_id"]))
        entry = {"path": path, **quote, "valid": False}
        if block is None:
            entry["reason"] = "引用了当前输入之外的块"
        else:
            engine = block.metadata.get("engine")
            original = originals[(engine, quote["file_id"])]
            try:
                locator = EvidenceLocator(**quote, parser=engine, parser_version=original.parser["version"],
                                          source_kind=block.metadata["source_kind"])
                found, reason = locate_evidence(locator, original)
                entry.update(valid=found is not None, reason=reason, engine=engine,
                             bbox=list(found.bbox) if found and found.bbox else None)
            except (ValueError, KeyError) as exc:
                entry["reason"] = type(exc).__name__
        checks.append(entry)
    return checks


def coverage_rows(documents, checks, exclusions):
    quoted = {(c["file_id"], c["block_id"]) for c in checks if c["valid"]}
    exclusions_by_block = {(e.get("file_id"), e.get("block_id")): e for e in exclusions if e.get("block_id")}
    rows = []
    for ir in documents.values():
        for block in ir.blocks:
            if block.block_type == "table_cell":
                continue
            exclusion = exclusions_by_block.get((ir.source_file_id, block.block_id))
            status = "quoted_candidate" if (ir.source_file_id, block.block_id) in quoted else "model_excluded" if exclusion else "unreviewed"
            rows.append({"file_id": ir.source_file_id, "pdf_page": block.pdf_page, "block_id": block.block_id,
                         "kind": str(block.block_type), "status": status, "reason": exclusion.get("reason") if exclusion else None,
                         "text": block.text, "bbox": block.bbox, "engine": block.metadata.get("engine")})
        for table in ir.tables:
            for index in range(table.row_count):
                cells = [c for c in table.cells if c.row_index == index]
                exclusion = next((e for e in exclusions if e.get("file_id") == ir.source_file_id and
                                  e.get("table_id") == table.table_id and e.get("row_index") == index), None)
                rows.append({"file_id": ir.source_file_id, "pdf_page": table.pdf_page, "table_id": table.table_id,
                             "row_index": index, "kind": "table_row", "block_id": table.block_id,
                             "text": " | ".join(c.text for c in cells),
                             "status": "quoted_candidate" if any((ir.source_file_id, c.block_id) in quoted for c in cells)
                             else "model_excluded" if exclusion else "unreviewed", "reason": exclusion.get("reason") if exclusion else None})
    return rows


def form_issues(form):
    """检查科学记录契约以外、当前表单实际不可表达的候选，不改写候选值。"""
    issues = []
    paper = form.get("paper", {})
    if paper.get("paper_type") not in (None, "", "theoretical", "experimental", "review"):
        issues.append({"field": "paper.paper_type", "code": "invalid_paper_type", "message": "论文类型不属于当前表单枚举"})
    if paper.get("superconductor_kind") not in (None, "", "conventional", "unconventional", "unknown"):
        issues.append({"field": "paper.superconductor_kind", "code": "invalid_superconductor_kind",
                       "message": "当前表单只接受 conventional/unconventional/unknown，不能把 predicted 当超导体类别"})
    for si, state in enumerate(form.get("material_states", [])):
        for mi, module in enumerate(state.get("property_modules", [])):
            for ri, record in enumerate(module.get("records", [])):
                parameters = record.get("payload", {}).get("parameters", {})
                if not isinstance(parameters, dict):
                    issues.append({"field": f"material_states.{si}.property_modules.{mi}.records.{ri}.payload.parameters",
                                   "code": "invalid_parameters", "message": "参数必须是对象"})
                    continue
                for name in ("lambda_ep", "omega_log", "mu_star"):
                    value = parameters.get(name)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                        issues.append({"field": f"material_states.{si}.property_modules.{mi}.records.{ri}.payload.parameters.{name}",
                                       "code": "numeric_parameter_not_representable",
                                       "message": "当前数值参数控件不能表达该值；保留原始候选，不擅自取范围端点"})
    return issues


def call_model(directory, user_prompt, config):
    from openai import OpenAI
    started = time.monotonic()
    request = {"model": config.model, "temperature": 0.1, "max_tokens": 32768,
               "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
               "input_chars": len(SYSTEM_PROMPT) + len(user_prompt), "max_input_chars": MAX_CHARS,
               "provider": config.provider, "started_at": datetime.now(timezone.utc).isoformat()}
    extra = {"thinking": {"type": "disabled"}} if config.model.startswith("deepseek-") else {}
    request["extra_body"] = extra
    if request["input_chars"] > MAX_CHARS:
        raise ValueError("document_input_too_large")
    write_json(directory / "request.json", request)
    (directory / "system.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (directory / "input.json").write_text(user_prompt, encoding="utf-8")
    parts, usage, finish = [], None, None
    client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=600, max_retries=0)
    try:
        stream = client.chat.completions.create(model=config.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
            temperature=0.1, max_tokens=32768, response_format={"type": "json_object"}, stream=True,
            stream_options={"include_usage": True}, extra_body=extra)
        with (directory / "response.txt").open("w", encoding="utf-8") as response:
            for chunk in stream:
                if chunk.usage:
                    usage = chunk.usage.model_dump()
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    finish = chunk.choices[0].finish_reason or finish
                    if delta:
                        parts.append(delta)
                        response.write(delta)
                        response.flush()
        if finish != "stop":
            raise ValueError(f"incomplete_response:{finish}")
        return json.loads("".join(parts))
    finally:
        client.close()
        write_json(directory / "call.json", request | {"elapsed_seconds": round(time.monotonic() - started, 3),
                   "usage": usage, "finish_reason": finish, "output_chars": sum(map(len, parts))})


def extract_arm(run, manifest, arm, config, originals):
    from .run import snapshot
    root = run / "extractions" / arm
    root.mkdir(parents=True, exist_ok=True)
    # 明确的重跑记录；旧响应和旧表单永远保留。
    attempts = [p for p in root.glob("attempt-*") if p.is_dir()]
    output = root / f"attempt-{len(attempts) + 1:03d}"
    output.mkdir(exist_ok=False)
    write_json(output / "baseline.json", snapshot(output))
    documents = {item["file_id"]: DocumentIR.model_validate_json((run / arm / item["file_id"] / "ir.json").read_text())
                 for item in manifest["case"]["files"]}
    user_prompt = json.dumps({"documents": [compact_document(documents[f["file_id"]], f["role"]) for f in manifest["case"]["files"]]},
                            ensure_ascii=False, separators=(",", ":"))
    result = {"arm": arm, "status": "failed", "attempt": output.name, "validation": {}}
    try:
        raw = call_model(output, user_prompt, config)
        write_json(output / "raw.json", raw)
        result["raw"] = raw
        parsed = DemoResponse.model_validate(raw).model_dump(mode="json")
        extraction = parsed["extraction"]
        checks = validate_sources(parsed, documents, originals)
        structures = [{"candidate_id": f"demo-structure-{i}", "status": "needs_review", "material_state_ref": None,
                       "source_kind": "pdf_reported", "reported_structure": observation,
                       "validation": {"ase_valid": False, "code": "reported_parameters_not_validated_structure"},
                       "sources": observation["evidences"]} for i, observation in enumerate(parsed["structure_observations"])]
        result.update(paper=parsed["paper"], paper_evidences=parsed["paper_evidences"],
                      material_states=[s for s in extraction["material_states"] if s["scope"] == "current_paper"],
                      referenced_states=[s for s in extraction["material_states"] if s["scope"] != "current_paper"],
                      structure_candidates=structures, conflicts=parsed["conflicts"],
                      coverage=coverage_rows(documents, checks, extraction["coverage_exclusions"]), evidence_checks=checks)
        normalized = normalize_extraction(extraction,
            allowed_blocks={(ir.source_file_id, b.pdf_page, b.block_id) for ir in documents.values() for b in ir.blocks},
            allowed_tables={(ir.source_file_id, t.table_id): t.row_count for ir in documents.values() for t in ir.tables},
            allowed_pages={(ir.source_file_id, p.pdf_page) for ir in documents.values() for p in ir.pages})
        result["material_states"] = [s for s in normalized["material_states"] if s["scope"] == "current_paper"]
        issues = form_issues(result)
        result["validation"] = {"record_contract_valid": True, "contract_valid": not issues, "form_issues": issues,
                                "evidence_total": len(checks), "evidence_invalid": sum(not c["valid"] for c in checks),
                                "semantic_status": "unreviewed", "production_ready": False}
        result["status"] = "needs_review"
    except Exception as exc:
        # 原始候选已经落盘，不能删掉出错字段再计为契约通过。
        result["validation"].update(contract_valid=False, error_type=type(exc).__name__)
        if hasattr(exc, "issues"):
            result["validation"]["issues"] = [{"field": i.field, "code": i.code, "message": i.message} for i in exc.issues]
        if isinstance(exc, ValueError):
            result["validation"]["error"] = str(exc)
        else:
            result["validation"]["error"] = "模型调用失败；检查本机连接或供应商响应"
    write_json(output / "form.json", result)
    write_json(root / "latest.json", {"attempt": output.name})
    print(f"{arm}: {result['status']} {result['validation']}", flush=True)
    return result


def extract_all(run, manifest):
    from backend.rag.llm_context import get_llm_config
    from .run import snapshot
    config = get_llm_config()
    if not config.api_key:
        raise ValueError("默认模型没有可用凭据")
    baseline = run / "extraction-baselines" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_json(baseline / "baseline.json", snapshot(baseline))
    originals = {(engine, f["file_id"]): DocumentIR.model_validate_json((run / engine / f["file_id"] / "ir.json").read_text())
                 for engine in ARMS[:3] for f in manifest["case"]["files"]}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(extract_arm, run, manifest, arm, config, originals) for arm in ARMS]
        results = [future.result() for future in futures]
    write_json(run / "extraction-summary.json", [{k: r[k] for k in ("arm", "status", "attempt", "validation")} for r in results])
    if any(r["status"] == "failed" for r in results):
        raise SystemExit("部分模型提取未通过；可以继续生成报告查看错误")
