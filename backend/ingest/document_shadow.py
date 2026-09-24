"""Shadow 使用独立任务、文件快照和产物，不进入用户任务列表或正式提交。"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import time
from uuid import uuid4

from .document_ir import content_hash


def enqueue_shadow(parent_id, config):
    from .upload_tasks import upload_task_lock
    with upload_task_lock(parent_id):
        return _enqueue_shadow_locked(parent_id, config)


def _enqueue_shadow_locked(parent_id, config):
    from rq.job import Callback
    from . import upload_tasks as tasks
    from .upload_jobs import process_upload_task, sha256_file

    parent = tasks.get_state(parent_id)
    if not parent or not parent.get("shadow_profile") or parent.get("shadow_task_id"):
        return
    shadow_id = uuid4().hex
    directory = tasks.task_directory(shadow_id)
    try:
        files = []
        sources = parent.get("files") or [{"file_id":"main", "role":"main", "kind":parent.get("file_kind"),
            "original_filename":parent.get("filename"), "stored_path":parent.get("file_path"), "sha256":parent.get("file_sha256")}]
        for source in sources:
            original = Path(source["stored_path"])
            if sha256_file(original) != source["sha256"]:
                raise ValueError("Shadow 来源文件摘要已变化")
            destination = directory / original.name
            shutil.copyfile(original, destination)
            if sha256_file(destination) != source["sha256"]:
                raise ValueError("Shadow 文件快照不一致")
            files.append({**source, "stored_path":str(destination),
                          "source_file_path":f"upload_PDFs/{shadow_id}/{destination.name}"})
        if not files or not any(item.get("kind") == "pdf" for item in files):
            shutil.rmtree(directory)
            return
        main = next(item for item in files if item["role"] == "main")
        now = int(time.time())
        shadow = dict(task_id=shadow_id, user_id=parent["user_id"], is_shadow=True, parent_task_id=parent_id,
            files=files, filename=main["original_filename"], file_kind=main["kind"], file_path=main["stored_path"],
            file_sha256=main["sha256"], source_file_path=main["source_file_path"],
            parser_profile=parent["shadow_profile"], parser_runs=[], reading_state=None,
            status="queued", stage="saving_file", stage_index=1, stage_total=5,
            processing_status="processing", state_schema_version=1, revision=1,
            created_at=now, updated_at=now, cleanup_at=None)
        # 不调用 create_task，避免进入用户任务索引和占用用户可编辑任务额度。
        tasks.redis_client().set(tasks.task_key(shadow_id), json.dumps(shadow))
        tasks.save_llm_config(shadow_id, config)
        tasks.update_state(parent_id, shadow_task_id=shadow_id, shadow_status="queued")
        job = tasks.upload_queue().enqueue(process_upload_task, shadow_id, job_timeout=1800,
            result_ttl=tasks.TASK_TTL, failure_ttl=tasks.TASK_TTL, on_failure=Callback(shadow_failure))
        tasks.update_state(shadow_id, job_id=job.id)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        tasks.redis_client().delete(tasks.task_key(shadow_id), tasks.llm_config_key(shadow_id))
        raise


def shadow_failure(job, connection, exc_type, exc_value, traceback):
    from .upload_tasks import handle_upload_job_failure, delete_llm_config
    handle_upload_job_failure(job, exc_type, exc_value, traceback)
    delete_llm_config(job.args[0])


def _scientific_records(draft):
    records = []
    for state in draft.get("material_states", []):
        conditions = {key:state.get(key) for key in ("material", "material_name", "pressure_value_gpa",
            "pressure_min_gpa", "pressure_max_gpa", "state_kind", "reported_space_group_number",
            "temperature_value_k", "magnetic_field_t", "note")}
        for module in state.get("property_modules", []):
            for record in module.get("records", []):
                values = {key:record.get(key) for key in ("record_type", "property_code", "name_raw",
                    "value_kind", "value_number", "value_min", "value_max", "value_text", "value_boolean",
                    "method_code", "method_raw", "criterion_code", "criterion_raw", "canonical_unit", "payload")}
                records.append({"state":conditions, "record":values})
    return records


def refresh_comparison(task_id):
    """读取不可编辑的 AI 初始产物，不把人工编辑后的用户草稿当作旧链路输出。"""
    from . import upload_tasks as tasks

    state = tasks.get_state(task_id)
    if not state:
        return
    parent_id = state.get("parent_task_id") if state.get("is_shadow") else task_id
    parent = tasks.get_state(parent_id)
    if not parent or not parent.get("shadow_task_id"):
        return
    shadow_id = parent["shadow_task_id"]
    shadow = tasks.get_state(shadow_id)
    if not shadow:
        return
    # 与父任务提交/清理锁协调；不改动父任务主阶段、草稿或科学数据库。
    with tasks.upload_task_lock(parent_id):
        parent = tasks.get_state(parent_id)
        if not parent:
            return
        rows = {}
        for name, identifier, current in (("legacy", parent_id, parent), ("new", shadow_id, shadow)):
            path = tasks.artifact_path(identifier)
            artifact = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            rows[name] = {"task_id":identifier, "status":current["status"], "error_code":current.get("error_code"),
                "parser_profile":current["parser_profile"], "records":_scientific_records(artifact.get("ai_values") or {})}
        from .scientific_evidence import canonical
        baseline = Counter(content_hash(canonical(record)) for record in rows["legacy"]["records"])
        candidate = Counter(content_hash(canonical(record)) for record in rows["new"]["records"])
        report = {"comparison_version":"1", "sources":[{"file_id":f["file_id"], "sha256":f["sha256"]} for f in shadow["files"]],
            "runs":rows, "legacy_records":sum(baseline.values()), "new_records":sum(candidate.values()),
            "same_records":sum((baseline & candidate).values()), "legacy_only":sum((baseline-candidate).values()),
            "new_only":sum((candidate-baseline).values()),
            "has_both_outputs": all(tasks.artifact_path(i).is_file() for i in (parent_id, shadow_id))}
        from .upload_jobs import _atomic_write_json
        _atomic_write_json(tasks.artifact_directory(parent_id) / "shadow-comparison.json", report)
        tasks.update_state(parent_id, shadow_status=shadow["status"])


def parent_cancelled(state):
    from .upload_tasks import get_state
    if not state.get("is_shadow"):
        return False
    parent = get_state(state["parent_task_id"])
    return not parent or parent.get("status") in {"cancelled", "cancelling"}
