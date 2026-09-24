"""在本机服务批量执行固定论文清单，并从实际 AI 产物导出离线评测输入。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit

import httpx

from .document_ir import DocumentIR, content_hash
from .pdf_benchmark import Corpus, Prediction, Record, Region, Resources, Run


def export_prediction(paper_id, state, artifact_root):
    task_id = state["task_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise ValueError("非法任务标识")
    directory = Path(artifact_root) / task_id
    sources = {item["file_id"]:item["sha256"] for item in state["files"]}
    metadata_path = directory / "run-metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    status = state["status"]
    if status not in {"ready", "failed", "cancelled", "timeout"}:
        raise ValueError("只导出已收敛的原始上传任务")
    records = []
    if status == "ready":
        if metadata.get("task_id") != task_id or metadata.get("parser_profile") != state["parser_profile"]:
            raise ValueError("运行元数据缺失或方案不一致")
        artifact = json.loads((directory / "result.json").read_text())
        if artifact.get("task_id") != task_id:
            raise ValueError("任务产物身份不一致")
        documents = {}
        for file_id, sha in sources.items():
            if not re.fullmatch(r"[\w-]+", file_id):
                raise ValueError("非法来源文件标识")
            path = directory / "document_ir" / f"{file_id}.json"
            if path.is_file():
                document = DocumentIR.model_validate_json(path.read_text())
                if document.source_file_id != file_id or document.source_sha256 != sha:
                    raise ValueError("导出 IR 与实际上传来源不一致")
                documents[file_id] = document
        for state_index, material in enumerate(artifact["ai_values"]["material_states"]):
            for module in material.get("property_modules", []):
                for index, record in enumerate(module["records"]):
                    fields = {key:record.get(key) for key in ("record_type", "property_code", "name_raw", "value_kind",
                        "value_number", "value_min", "value_max", "value_text", "value_boolean", "canonical_unit",
                        "method_code", "method_raw", "criterion_code", "criterion_raw", "uncertainty")}
                    fields.update(material=material.get("material"), material_name=material.get("material_name"))
                    conditions = {key:material.get(key) for key in ("pressure_value_gpa", "pressure_min_gpa", "pressure_max_gpa",
                        "temperature_value_k", "magnetic_field_t", "state_kind", "reported_space_group_number")}
                    conditions["payload"] = record.get("payload") or {}
                    evidences = []
                    for evidence in [*(record.get("evidences") or []), *([record["evidence"]] if record.get("evidence") else [])]:
                        document = documents.get(str(evidence.get("file_id")))
                        if document is None:
                            continue  # 旧链路没有区域；保留定位失败，不伪造 bbox。
                        from .document_claims import _locators
                        from .claim_evidence import locate_evidence
                        locators = _locators([evidence], {document.source_file_id:document})
                        if not locators:
                            raise ValueError("科学记录的区域来源无法验证")
                        for locator in locators:
                            located, error = locate_evidence(locator, document)
                            if error:
                                raise ValueError("科学记录的区域来源校验失败")
                            if not located.bbox:
                                continue
                            page = next(p for p in document.pages if p.pdf_page == located.pdf_page)
                            x0,y0,x1,y1 = located.bbox
                            if x0 == x1 or y0 == y1:
                                continue
                            evidences.append(Region(file_sha256=document.source_sha256, pdf_page=page.pdf_page,
                                bbox=(x0/page.width,y0/page.height,x1/page.width,y1/page.height), quote=located.quote))
                    records.append(Record(record_id=f"{state_index}/{module['module_code']}/{index}",
                        fields=fields, conditions=conditions, evidences=evidences))
    return Prediction(paper_id=paper_id, source_sha256s=list(sources.values()), status=status,
                      records=records, resources=Resources.model_validate(metadata.get("resources") or {})), metadata


def run_corpus(client, corpus, sources, *, profile, artifact_root, timeout=1800, sleep=time.sleep, on_progress=None):
    """上传与排队走公开 API，不绕过 Worker；不会提交、审核或发布论文。"""
    expected_ids = {paper.paper_id for paper in corpus.papers}
    if set(sources) != expected_ids:
        raise ValueError("本机文件映射必须与固定评测清单完全一致")
    for paper in corpus.papers:
        hashes, mains = [], []
        for item in sources[paper.paper_id]:
            path = Path(item["path"])
            with path.open("rb") as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            hashes.append(sha)
            if item["role"] == "main": mains.append(sha)
        if len(hashes) != len(set(hashes)) or set(hashes) != set(paper.source_sha256s) or mains != [paper.main_sha256]:
            raise ValueError("本机文件内容或正文归属与标注清单不一致")
    predictions, identities = [], set()
    for paper in corpus.papers:
        files = sources[paper.paper_id]
        response = client.post("/api/upload-tasks", json={"parser_profile":profile, "files":[{
            "client_id":str(index), "filename":Path(item["path"]).name, "role":item["role"],
            "size":Path(item["path"]).stat().st_size} for index,item in enumerate(files)]})
        response.raise_for_status()
        state = response.json()["data"]
        task_id = state["task_id"]
        if not re.fullmatch(r"[0-9a-f]{32}", task_id) or state["parser_profile"] != profile:
            raise ValueError("服务端返回的任务身份或解析方案不一致")
        for item, declared in zip(files, state["files"]):
            with Path(item["path"]).open("rb") as stream:
                response = client.put(f"/api/upload-tasks/{task_id}/files/{declared['file_id']}",
                    files={"file":(Path(item["path"]).name, stream)})
            response.raise_for_status()
        deadline = time.monotonic() + timeout
        while True:
            response = client.get(f"/api/upload-tasks/{task_id}")
            response.raise_for_status()
            state = response.json()["data"]
            if state["status"] in {"ready", "failed", "cancelled"}:
                break
            if state["status"] == "duplicate":
                raise ValueError("样本已存在于正式论文库，不能用历史结果充当本轮解析；请使用隔离评测实例")
            if time.monotonic() >= deadline:
                client.post(f"/api/upload-tasks/{task_id}/cancel").raise_for_status()
                state["status"] = "timeout"
                break
            sleep(1)
        # Worker 先设置 ready，再原子保存运行元数据；允许短暂的文件可见性延迟。
        for _ in range(10):
            if state["status"] != "ready" or (Path(artifact_root)/task_id/"run-metadata.json").exists(): break
            sleep(.1)
        prediction, metadata = export_prediction(paper.paper_id, state, artifact_root)
        if set(prediction.source_sha256s) != set(paper.source_sha256s):
            raise ValueError("实际上传文件与人工标注摘要不一致")
        if metadata:
            identities.add((metadata["pipeline_revision"], metadata["model"]))
        if len(identities) > 1:
            raise ValueError("评测中途更换了实现或模型，已完成结果保持原样")
        predictions.append(prediction)
        if on_progress:
            revision, model = next(iter(identities), ("unavailable", "unavailable"))
            on_progress(Run(schema_version="1", run_id=content_hash([p.model_dump(mode="json") for p in predictions]),
                pipeline_revision=revision, parser_profile=profile, model=model, papers=list(predictions)))
    if len(identities) != 1:
        raise ValueError("评测运行缺少源码/模型身份，或中途更换了实现/模型")
    revision, model = identities.pop()
    return Run(schema_version="1", run_id=content_hash([p.model_dump(mode="json") for p in predictions]),
               pipeline_revision=revision, parser_profile=profile, model=model, papers=predictions)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corpus", "sources", "artifact-root", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--profile", choices=["legacy","text","layout","ocr","native_pdf_llm"], required=True)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args(argv)
    url = urlsplit(args.base_url)
    if url.scheme not in {"http","https"} or url.hostname not in {"localhost","127.0.0.1","::1"} or url.username or url.path not in {"", "/"} or url.query or url.fragment:
        parser.error("评测仅连接本机服务根地址")
    if not 0 < args.timeout <= 7200:
        parser.error("单篇超时必须大于 0 且不超过 7200 秒")
    token = os.environ.get("SCWIKI_BENCHMARK_TOKEN")
    if not token:
        parser.error("请在本机设置 SCWIKI_BENCHMARK_TOKEN，不将凭据写入报告")
    corpus = Corpus.model_validate_json(args.corpus.read_text())
    sources = json.loads(args.sources.read_text())
    inputs = {args.corpus.resolve(), args.sources.resolve(), *(Path(f["path"]).resolve() for files in sources.values() for f in files)}
    if args.output.resolve() in inputs:
        parser.error("输出不能覆盖标注或源文件")
    def save_progress(result):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(result.model_dump_json(indent=2) + "\n")
        try:
            temporary.replace(args.output)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"已保存 {len(result.papers)}/{len(corpus.papers)} 篇运行结果", flush=True)
    with httpx.Client(base_url=args.base_url, headers={"Authorization":"Bearer "+token}, timeout=120, trust_env=False) as client:
        run_corpus(client, corpus, sources, profile=args.profile, artifact_root=args.artifact_root,
                   timeout=args.timeout, on_progress=save_progress)


if __name__ == "__main__":
    main()
