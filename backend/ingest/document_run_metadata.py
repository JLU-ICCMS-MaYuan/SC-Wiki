"""记录解析运行身份与实测耗时；不保存密钥或模型内部思维链。"""
import hashlib
from pathlib import Path

from .document_ir import content_hash


def save_run_metadata(task_id, state, config, *, latency, cpu):
    from .upload_tasks import artifact_directory
    from .upload_jobs import _atomic_write_json
    directory = Path(__file__).parent
    # 文件指纹覆盖未提交工作区，不将其误报为某个 Git commit。
    fingerprint = content_hash({name:hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("upload_jobs.py", "domain_extraction.py", "document_claims.py", "claim_evidence.py",
                     "coverage_audit.py", "document_parsers.py", "structured_pdf.py")})
    _atomic_write_json(artifact_directory(task_id) / "run-metadata.json", {
        "task_id":task_id, "parser_profile":state.get("parser_profile", "legacy"),
        "pipeline_revision":"sha256:" + fingerprint, "provider":config.provider, "model":config.model,
        "status":state.get("status"), "resources":{"latency_seconds":latency, "cpu_seconds":cpu},
        "cpu_scope":"worker_process_only",
    })
