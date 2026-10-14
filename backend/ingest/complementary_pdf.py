"""四工具默认解析器：MinerU 主干、GROBID 题录引用和按页补强。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from .document_parsers import ParseOptions, ParserDecision, ParserError, package_version
from .structured_pdf import run_parser_worker, convert_docling, convert_mineru
from .marker_pdf import convert_marker
from .complementary_ir import repair_pages, compose
from .grobid_document import extract_document


class ComplementaryPdfParser:
    name = "complementary"
    version = "1"

    def can_parse(self, source, capabilities):
        supported = source.media_type == "application/pdf" and "mineru" in capabilities.installed
        return ParserDecision(supported, "complementary", "ocr", "MinerU 主干；补强依赖按内容检查", ("mineru",))

    def parse(self, source, options):
        if source.media_type != "application/pdf":
            raise ParserError("parser_unsupported_media", "四工具流程只处理 PDF", profile=options.profile, parser=self.name)
        if options.parser_options.get("artifact_directory"):
            root = Path(options.parser_options["artifact_directory"])
        elif options.task_id:
            from .upload_tasks import artifact_directory
            root = artifact_directory(options.task_id) / "four_tools" / source.file_id
        else:
            root = Path(tempfile.mkdtemp(prefix="scwiki-four-tools-"))
        # 重试留存旧运行，不能覆盖此前原始结果。
        from uuid import uuid4
        root = root / uuid4().hex
        root.mkdir(parents=True, exist_ok=False)
        ledger = {"rule_version": "1", "source_sha256": source.resolved_sha256(), "file_id": source.file_id, "runs": []}

        def component(engine, pages=None):
            directory = root / engine
            settings = {**options.parser_options, "artifact_directory": str(directory), "pages": pages}
            scoped = ParseOptions(profile=engine, task_id=options.task_id, parser_options=settings, cancelled=options.cancelled)
            record = {"engine": engine, "requested_pages": pages, "status": "running"}
            ledger["runs"].append(record)
            try:
                raw = run_parser_worker(engine, source.path, scoped)
                version = raw.get("version") or package_version(engine)
                converter = {"mineru": convert_mineru, "docling": convert_docling, "marker": convert_marker}[engine]
                ir = converter(raw, source, scoped, version)
                (directory / "ir.json").write_text(ir.model_dump_json(indent=2), encoding="utf-8")
                record.update(status="succeeded", version=version, pages=[p.pdf_page for p in ir.pages],
                              raw_sha256=hashlib.sha256((directory / "raw.json").read_bytes()).hexdigest())
                return ir
            except Exception as exc:
                record.update(status="failed", error_code=getattr(exc, "code", "parser_invalid_output"))
                raise

        try:
            documents = {"mineru": component("mineru")}
            plan = repair_pages(documents["mineru"])
            ledger["repair_plan"] = plan
            for engine in ("docling", "marker"):
                if plan[engine]:
                    documents[engine] = component(engine, plan[engine])
                else:
                    ledger["runs"].append({"engine": engine, "status": "not_needed", "requested_pages": []})
            if options.cancelled and options.cancelled():
                raise ParserError("parser_cancelled", "解析已取消", profile=options.profile, parser=self.name)
            grobid = extract_document(source, root / "grobid")
            ledger["runs"].append({"engine": "grobid", "status": grobid["status"], "version": grobid["parser_version"],
                                   "elapsed_seconds": grobid["elapsed_seconds"]})
            if options.cancelled and options.cancelled():
                raise ParserError("parser_cancelled", "解析已取消", profile=options.profile, parser=self.name)
            result = compose(documents)
            result.coverage.update(grobid=grobid, component_runs=ledger["runs"])
            return result
        finally:
            (root / "pipeline.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
