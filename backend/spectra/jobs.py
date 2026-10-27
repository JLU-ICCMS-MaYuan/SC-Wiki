"""复用上传 RQ 的独立谱任务；数值结果持久化，凭据仅在短期 Redis 保存。"""
from __future__ import annotations
from dataclasses import asdict
import io
import json
import logging
from sqlalchemy import select
from PIL import Image
import numpy as np
from backend import models
from backend.database import SessionLocal
from backend.services import spectra as service
from backend.spectra.contracts import fingerprint, panel_identity

log = logging.getLogger(__name__)


def enqueue(session, ctx, *, expected_version, config, row=None, calibration=None, expected_collection_version=None):
    service.assert_version(ctx["version"], expected_version)
    if row is None:
        row = service.collection(session, ctx, "__all__", "__discovery__", dict(source_version=ctx["version"]))
        calibration = dict(discovery_version=ctx["version"], model_name=config.model)
        state = None
    else:
        service.assert_version(row.version, expected_collection_version)
        from .contracts import PanelCalibration
        calibration = PanelCalibration.model_validate(calibration).model_dump()
        state = next((s for s in ctx["states"] if s["state_key"] == calibration.get("state_key")), None)
        if calibration.get("state_key") and state is None:
            service.fail("spectra_state_invalid", "材料状态不属于当前草稿", 422)
    run, pending = service.new_run(session, row, calibration, state, model_name=config.model)
    service.activate(row, run, state)
    session.flush()
    if not pending or run.status == "running":
        return dict(job_id=run.id, cached=not pending)
    from backend.ingest.upload_tasks import save_llm_config
    save_llm_config("spectra-" + run.id, config)
    # 调用者提交事务后再派发，避免 Worker 看不到运行记录。
    return dict(job_id=run.id, dispatch=True, version=ctx["version"], target=ctx["target"], target_id=ctx["target_id"])


def dispatch(job, user_id):
    if not job.get("dispatch"):
        return
    from backend.ingest.upload_tasks import upload_queue
    try:
        upload_queue().enqueue(run_job, job["job_id"], job["target"], job["target_id"], user_id,
                               job["version"], job_timeout="30m", result_ttl=3600)
    except Exception:
        with SessionLocal.begin() as session:
            row = session.get(models.SpectrumRun, job["job_id"])
            if row:
                row.status, row.error_code, row.error_message = "failed", "spectra_queue_unavailable", "谱任务未能入队，请重试"
        raise


def store_figure(figure, file_id, source_name):
    from backend.storage import create_storage
    ref = create_storage().put("spectra/images/" + figure["image_sha256"] + ".png",
                               io.BytesIO(figure["image"]), "image/png")
    return {**{k: v for k, v in figure.items() if k not in {"image", "text"}},
            "file_id": str(file_id), "source_name": source_name, "image": asdict(ref)}


def read_image(source):
    from backend.storage import FileRef, create_storage
    with create_storage().open(FileRef(**source["image"])) as image:
        return np.asarray(Image.open(image).convert("RGB"))


def run_job(run_id, target, target_id, user_id, expected_version):
    from backend.ingest.upload_tasks import load_llm_config, delete_llm_config
    from backend.rag.llm_context import set_llm_config, reset_llm_config
    config = load_llm_config("spectra-" + run_id)
    token = set_llm_config(config) if config else None
    try:
        with SessionLocal.begin() as session:
            user = session.get(models.User, user_id)
            ctx = service.context(session, target, target_id, user, write=True)
            service.assert_version(ctx["version"], expected_version)
            run = session.get(models.SpectrumRun, run_id, with_for_update=True)
            if not run or run.status == "succeeded" or run.status == "running":
                return
            row = session.get(models.SpectrumCollection, run.collection_id)
            if row.current_run_id != run.id:
                service.fail("spectra_run_superseded", "已有更新的谱任务")
            run.status = "running"
            calibration, source, discovery = run.calibration_json, row.source_json, row.panel_key == "__discovery__"
        if discovery:
            result = discover(ctx, user_id, expected_version)
        else:
            from .engine import extract_panel
            from .context import references_for, primitive_for, composition_for
            state = next((s for s in ctx["states"] if s["state_key"] == calibration.get("state_key")), None)
            result = extract_panel(read_image(source), calibration, references=references_for(state),
                                   primitive=primitive_for(state, ctx["draft"]), composition=composition_for(state))
        with SessionLocal.begin() as session:
            ctx_now = service.context(session, target, target_id, session.get(models.User, user_id), write=True)
            service.assert_version(ctx_now["version"], expected_version)
            run = session.get(models.SpectrumRun, run_id, with_for_update=True)
            row = session.get(models.SpectrumCollection, run.collection_id)
            if row.current_run_id != run.id:
                service.fail("spectra_run_superseded", "已有更新的谱任务")
            service.complete_run(run, result)
    except Exception as exc:
        log.warning("谱任务失败 run=%s type=%s", run_id, type(exc).__name__)
        detail = getattr(exc, "detail", {})
        with SessionLocal.begin() as session:
            run = session.get(models.SpectrumRun, run_id)
            if run and run.status != "succeeded":
                run.status = "failed"
                run.error_code = detail.get("code", "spectra_extraction_failed") if isinstance(detail, dict) else "spectra_extraction_failed"
                run.error_message = (detail.get("message", "谱提取失败，原图与此前运行已保留，请重试")
                                     if isinstance(detail, dict) else "谱提取失败，原图已保留")
    finally:
        if token is not None:
            reset_llm_config(token)
        delete_llm_config("spectra-" + run_id)


def discover(ctx, user_id, version):
    from backend.storage.paths import resolve_file
    from .vision import verify_image_capability
    from .discovery import pdf_figures, calibrate
    from .engine import extract_panel
    from .context import references_for, primitive_for, composition_for
    states = {s["state_key"]: s for s in ctx["states"]}
    try:
        supported = verify_image_capability()
    except Exception:
        supported = False
    count, extracted, curve_count, issues = 0, 0, 0, []
    for source in ctx["files"]:
        path = resolve_file(source["stored_path"], size=int(source.get("size") or 0),
                            sha256=str(source.get("sha256") or ""), media_type="application/pdf", namespace=ctx["target_id"])
        if not path.is_file() or fingerprint_bytes(path) != source.get("sha256"):
            issues.append(dict(file_id=source["file_id"], code="source_hash_mismatch", reason="原 PDF 缺失或摘要变化"))
            continue
        ir = None
        if ctx["target"] == "upload":
            from backend.ingest.upload_tasks import artifact_directory, available_published_path
            from backend.storage import FileNotFound
            try:
                ir_path = available_published_path(ctx["target_id"], artifact_directory(ctx["target_id"]) / "document_ir" / (str(source["file_id"])+".json"))
            except (FileNotFoundError, FileNotFound):
                # IR 是可选定位提示；旧任务可能只有已持久化的原 PDF。
                ir_path = None
            if ir_path is not None and ir_path.is_file():
                ir = json.loads(ir_path.read_text())
        elif ctx.get("paper"):
            with SessionLocal() as session:
                parser = session.scalar(select(models.PaperDocumentParserRun).where(
                    models.PaperDocumentParserRun.paper_id == ctx["paper"].id,
                    models.PaperDocumentParserRun.paper_revision == ctx["paper_revision"],
                    models.PaperDocumentParserRun.paper_file_id == int(source["file_id"])).order_by(
                        models.PaperDocumentParserRun.id.desc()))
                if parser:
                    ir = parser.document_json
        for figure in pdf_figures(path, ir=ir):
            source_info = store_figure(figure, source["file_id"], source.get("original_filename") or "")
            source_key = fingerprint([source_info["source_sha256"], source_info["pdf_page"], source_info["bbox_pdf_pt"]])
            panels, panel_issues = [], []
            if supported:
                try:
                    panels, panel_issues = calibrate(figure, ctx["states"])
                except Exception as exc:
                    status_code = getattr(exc, "status_code", None)
                    status_text = f"HTTP {status_code}，" if status_code else ""
                    panel_issues = [f"自动标定失败：{status_text}{type(exc).__name__}；待重试"]
            else:
                panel_issues = ["当前模型读图校验未成功（能力或服务可用性未证实），谱待处理；其他解析不受影响"]
            issues.extend(dict(file_id=source["file_id"], page=figure["pdf_page"], reason=str(issue)) for issue in panel_issues)
            if not panels and panel_issues:
                panels = [None]
            for panel in panels:
                state = states.get(panel.get("state_key")) if panel else None
                result = (extract_panel(np.asarray(Image.open(io.BytesIO(figure["image"])).convert("RGB")), panel,
                            references=references_for(state), primitive=primitive_for(state, ctx["draft"]), composition=composition_for(state)) if panel else
                          dict(curves=[], candidates={}, quality=dict(limitations=panel_issues), failures=panel_issues))
                with SessionLocal.begin() as session:
                    fresh = service.context(session, ctx["target"], ctx["target_id"], session.get(models.User, user_id), write=True)
                    service.assert_version(fresh["version"], version)
                    row = service.collection(session, fresh, source_key,
                        panel_identity(panel) if panel else "__unavailable__", source_info)
                    from backend.rag.llm_context import get_llm_config
                    run, pending = service.new_run(session, row, panel or dict(issues=panel_issues), state,
                                                   model_name=get_llm_config().model)
                    if pending:
                        service.complete_run(run, result)
                    service.activate(row, run, state)
                    count += 1
                    if result.get("curves"):
                        extracted += 1
                        curve_count += len(result["curves"])
    return dict(collections=count, extracted_collections=extracted, curve_count=curve_count,
                issues=issues, image_capability_verified=supported,
                status="needs_review" if issues or not supported else "completed")


def fingerprint_bytes(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enqueue_upload(task_id):
    """上传 ready 后调用；独立失败不能覆盖论文的成功状态。"""
    from backend.ingest.upload_tasks import get_state, load_llm_config
    try:
        state = get_state(task_id)
        if not state or state.get("is_shadow"):
            return
        config = load_llm_config(task_id)
        if config is None:
            from backend.rag.llm_context import get_llm_config
            config = get_llm_config()
        with SessionLocal.begin() as session:
            if not service.available(session):
                return  # 部署迁移前旧上传仍可使用；谱API会明确说明缺迁移。
            ctx = service.context(session, "upload", task_id, session.get(models.User, state["user_id"]), write=True)
            job = enqueue(session, ctx, expected_version=ctx["version"], config=config)
            from backend.ingest.scientific_evidence import persist_upload
            persist_upload(session, task_id, state, ctx["draft"])
        dispatch(job, state["user_id"])
    except Exception as exc:
        log.warning("上传谱任务未能启动 task=%s type=%s", task_id, type(exc).__name__)
