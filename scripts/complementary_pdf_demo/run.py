"""可恢复的独立三引擎实验入口；只写 demo 产物。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4

from .parsers import write_json, to_ir

ROOT = Path(__file__).resolve().parents[2]
ENGINES = ("docling", "mineru", "marker")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_case(path):
    import pymupdf
    path = Path(path).resolve()
    case = read_json(path)
    identifiers = set()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", case["case_id"]):
        raise ValueError("case_id 不能用作目录名")
    for item in case["files"]:
        identifier = item["file_id"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", identifier) or identifier in identifiers:
            raise ValueError("file_id 非法或重复")
        identifiers.add(identifier)
        if item["role"] not in {"main", "supplementary"}:
            raise ValueError("文件角色必须是 main/supplementary")
        source = (path.parent / item["path"]).resolve()
        actual = digest(source)
        if item.get("sha256") and item["sha256"] != actual:
            raise ValueError(f"输入哈希不符：{identifier}")
        with pymupdf.open(source) as pdf:
            if pdf.needs_pass or not len(pdf):
                raise ValueError("PDF 不可读")
            item["pages"] = len(pdf)
        item.update(path=str(source), sha256=actual)
    if sum(f["role"] == "main" for f in case["files"]) != 1:
        raise ValueError("必须且只能有一份正文")
    return case


def snapshot(run):
    files = [*Path("scripts/complementary_pdf_demo").rglob("*.py"),
             *Path("backend/ingest").glob("*.py"), Path("backend/data/form_definitions.v1.json"),
             Path("backend/rag/llm.py"), Path("backend/rag/llm_context.py")]
    result = {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "files": {str(p): digest(p) for p in files}}
    # 保存相关源码的实际字节，避免未提交工作树只有哈希而不能复现。
    for path in files:
        destination = run / "code" / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    return result


def parse_one(engine, item, run, python, timeout):
    from backend.ingest.document_parsers import DocumentSource
    output = run / engine / item["file_id"]
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = {"engine": engine, "file_id": item["file_id"], "sha256": item["sha256"], "status": "running",
              "started_at": datetime.now(timezone.utc).isoformat(), "python": str(python), "timeout_seconds": timeout}
    record["baseline"] = snapshot(output)
    write_json(output / "run.json", record)
    env = {**os.environ, "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false",
           "MINERU_CONFIG": str(output / "mineru.yaml"), "SURYA_INFERENCE_BACKEND": "llamacpp",
           "SURYA_INFERENCE_KEEP_ALIVE": "0", "SURYA_INFERENCE_PARALLEL": "2",
           "HF_ENDPOINT": "https://hf-mirror.com", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
           "HF_HUB_ETAG_TIMEOUT": "15", "HF_HUB_DOWNLOAD_TIMEOUT": "60"}
    # 仅改变子进程 PATH，不修改用户 shell 或系统安装。
    llama = list((ROOT / ".local/issue136-llama").rglob("llama-server"))
    if llama:
        env["PATH"] = str(llama[0].parent) + os.pathsep + env.get("PATH", "")
    (output / "mineru.yaml").write_text("{}", encoding="utf-8")
    try:
        with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
            command = [str(python), "-u", "-m", "scripts.complementary_pdf_demo.parsers", engine, item["path"], str(output)]
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            record["pid"] = process.pid
            write_json(output / "run.json", record)
            try:
                code = process.wait(timeout=timeout)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        record["exit_code"] = code
        if code:
            raise RuntimeError(f"parser_exit_{code}")
        if digest(item["path"]) != item["sha256"]:
            raise ValueError("解析过程中来源发生改变")
        raw = read_json(output / "raw.json")
        ir = to_ir(engine, raw, DocumentSource(Path(item["path"]), item["file_id"], item["role"], item["sha256"]))
        if len(ir.pages) != item["pages"]:
            raise ValueError("解析缺页")
        write_json(output / "ir.json", ir.model_dump(mode="json"))
        record.update(status="succeeded", runtime=raw["runtime"], blocks=len(ir.blocks), tables=len(ir.tables),
                      ir_sha256=digest(output / "ir.json"), raw_sha256=digest(output / "raw.json"))
    except BaseException as exc:
        record.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(output / "run.json", record)
    print(f"{engine}/{item['file_id']}: {record['status']} ({record['elapsed_seconds']}s)", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "demo/complementary-pdf")
    parser.add_argument("--stage", choices=["parse", "extract", "report", "all"], default="all")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--marker-python", type=Path, default=ROOT / ".local/issue136-marker/bin/python")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--resume-parsing", action="store_true", help="保留已有成功产物，只重跑失败或未执行的解析")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout 必须为正数")
    if args.run_dir:
        run = args.run_dir.resolve()
        manifest = read_json(run / "manifest.json")
        if args.stage in {"parse", "all"} and not args.resume_parsing:
            parser.error("重跑解析必须创建新运行；已有运行只允许 extract/report")
        for item in manifest["case"]["files"]:
            if digest(item["path"]) != item["sha256"]:
                raise ValueError("来源已改变，拒绝续跑")
    else:
        if not args.case or args.stage not in {"parse", "all"}:
            parser.error("新运行需要 --case 和 --stage parse/all")
        case = validate_case(args.case)
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        run = args.output.resolve() / "runs" / identifier
        run.mkdir(parents=True, exist_ok=False)
        manifest = {"schema_version": 1, "run_id": identifier, "case": case, "baseline": snapshot(run), "parses": []}
        write_json(run / "manifest.json", manifest)
    print(f"RUN_DIR={run}", flush=True)
    if args.stage in {"parse", "all"}:
        records = []
        for engine in ENGINES:
            for item in manifest["case"]["files"]:
                # 不能 resolve venv 的 python 符号链接，否则会绕过隔离环境。
                python = args.marker_python.absolute() if engine == "marker" else Path(sys.executable)
                directory = run / engine / item["file_id"]
                record_path = directory / "run.json"
                previous = read_json(record_path) if record_path.exists() else None
                if args.resume_parsing and previous and previous["status"] == "succeeded":
                    if (previous["sha256"] != item["sha256"] or digest(directory / "ir.json") != previous["ir_sha256"]
                            or digest(directory / "raw.json") != previous["raw_sha256"]):
                        raise ValueError("成功产物摘要改变，拒绝复用")
                    record = {**previous, "reused_from": str(directory.relative_to(run))}
                else:
                    if directory.exists():
                        archive = run / "failed-attempts" / engine / item["file_id"] / uuid4().hex[:12]
                        archive.parent.mkdir(parents=True, exist_ok=True)
                        directory.rename(archive)
                    record = parse_one(engine, item, run, python, args.timeout)
                records.append(record)
                manifest["parses"] = records
                write_json(run / "manifest.json", manifest)
        if not all(p["status"] == "succeeded" for p in manifest["parses"]):
            raise SystemExit("解析未全部通过，原始结果和失败日志已保留")
        from .complement import build_complementary
        build_complementary(run, manifest)
    if args.stage in {"extract", "all"}:
        from .extraction import extract_all
        extract_all(run, manifest)
    if args.stage in {"report", "all"}:
        from .report import build_report
        build_report(run, manifest)


if __name__ == "__main__":
    main()
