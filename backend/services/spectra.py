"""谱集合的权限、版本和数据库事实；不信任客户端数值或质量报告。"""
from __future__ import annotations
import copy
import math
from datetime import datetime, timezone
import uuid
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, inspect
from backend import models
from backend.spectra.contracts import fingerprint, state_signature, ALGORITHM_VERSION, conventional_structure_text


def fail(code, message, status=409):
    raise HTTPException(status, detail=dict(code=code, message=message))


def available(session):
    schema = inspect(session.get_bind())
    return all(schema.has_table(name) for name in ("spectrum_collections", "spectrum_runs"))


def require_tables(session):
    if not available(session):
        fail("spectra_migration_required", "谱存储尚未迁移，请完成 #137 数据库迁移后重试", 503)


def admin(user):
    return bool(user and user.role in {"admin", "superadmin"} and user.is_approved)


def context(session, target, target_id, user, *, write=False):
    """先鉴权再读取 PDF 清单；公开调用不允许查看草稿。"""
    require_tables(session)
    paper = None
    if target == "upload":
        from backend.ingest.upload_tasks import get_state, get_draft
        state = get_state(target_id)
        if not state or state.get("is_shadow"):
            fail("spectra_target_missing", "上传任务不存在", 404)
        if not user or (int(state.get("user_id") or 0) != user.id and not admin(user)):
            fail("spectra_forbidden", "无权访问该谱草稿", 403)
        if state.get("status") == "submitted" or state.get("paper_id"):
            fail("spectra_target_submitted", "任务已提交，请打开正式论文")
        draft = get_draft(target_id)
        if draft is None:
            fail("spectra_draft_not_ready", "论文草稿尚未准备完成")
        files = state.get("files") or [dict(file_id="main", kind=state.get("file_kind"), role="main",
            stored_path=state.get("file_path"), sha256=state.get("file_sha256"), size=state.get("file_size"))]
        owner_id = int(state["user_id"])
    else:
        if target == "revision":
            saved = session.scalar(select(models.PaperRevisionDraft).where(models.PaperRevisionDraft.revision_id == target_id))
            if not saved or not saved.draft:
                fail("spectra_target_missing", "返修草稿不存在", 404)
            paper = session.get(models.Paper, saved.paper_id)
            if not user or user.id != saved.owner_id:
                fail("spectra_forbidden", "无权访问该返修谱", 403)
            if saved.base_revision != paper.content_revision:
                fail("spectra_revision_stale", "论文版本已变化，请重新打开返修草稿")
            draft, owner_id = saved.draft, saved.owner_id
        elif target == "paper" and str(target_id).isdigit():
            paper = session.get(models.Paper, int(target_id))
            if paper is None:
                fail("spectra_target_missing", "论文不存在", 404)
            privileged = bool(user and (admin(user) or user.id == paper.uploaded_by_user_id))
            public = paper.review_status == "approved" and paper.approved_revision == paper.content_revision
            if not privileged and not public:
                fail("spectra_forbidden", "无权访问该论文谱", 403)
            if write and not admin(user):
                fail("spectra_revision_required", "请通过上传或返修草稿修正谱；正式论文由审核者编辑", 403)
            from backend.services.paper_revisions import current_draft
            draft = current_draft(session, paper)
            owner_id = paper.uploaded_by_user_id or (user.id if user else 0)
        else:
            fail("spectra_target_invalid", "谱目标无效", 422)
        files = [dict(file_id=str(f.id), role=f.role, stored_path=f.stored_path, sha256=f.sha256,
                      size=f.size, kind="pdf", media_type=f.media_type, original_filename=f.original_filename)
                 for f in session.scalars(select(models.PaperFile).where(models.PaperFile.paper_id == paper.id,
                              models.PaperFile.paper_revision == paper.content_revision))
                 if f.original_filename.lower().endswith(".pdf")]
    states = jsonable_encoder(draft.get("material_states") or [])
    for i, s in enumerate(states):
        s["state_key"] = s.get("state_key") or f"state-{i+1}"
        s["_spectrum_structure_hashes"] = structure_dependencies(draft, i)
    files = [f for f in files if f.get("role") in {"main", "supplementary"} and f.get("kind") == "pdf"]
    identity = dict(target=target, target_id=target_id, states=states,
                    files=[{k: f.get(k) for k in ("file_id", "sha256", "role")} for f in files],
                    paper_revision=paper.content_revision if paper else None)
    return dict(**{**identity, "files": files}, owner_id=owner_id, version=fingerprint(identity),
                paper=paper, draft=draft, privileged=(target != "paper" or bool(user and (admin(user) or user.id == owner_id))),
                can_edit=(target != "paper" or admin(user)), can_review=(target == "paper" and admin(user)))


def structure_dependencies(draft, index):
    hashes=[]
    for candidate in draft.get("structure_candidates") or []:
        if candidate.get("confirmation")!="confirmed" or candidate.get("material_state_ref")!=f"material_states[{index}]":
            continue
        text=conventional_structure_text(candidate)
        text=text or candidate.get("original_text")
        if text:
            hashes.append(fingerprint(text))
    return sorted(set(hashes))


def assert_version(actual, expected):
    if actual != expected:
        fail("spectra_version_conflict", "内容或谱版本已变化，请刷新后重试；当前结果已保留")


def collection(session, ctx, source_key, panel_key, source):
    row = session.scalar(select(models.SpectrumCollection).where(
        models.SpectrumCollection.target == ctx["target"], models.SpectrumCollection.target_id == ctx["target_id"],
        models.SpectrumCollection.source_key == source_key, models.SpectrumCollection.panel_key == panel_key).with_for_update())
    if row is None:
        row = models.SpectrumCollection(id=uuid.uuid4().hex, target=ctx["target"], target_id=ctx["target_id"],
            owner_id=ctx["owner_id"], paper_id=ctx["paper"].id if ctx.get("paper") else None,
            paper_revision=ctx.get("paper_revision"), source_key=source_key, panel_key=panel_key,
            source_json=source, state_signature=state_signature(None), review_json={}, version=1)
        session.add(row); session.flush()
    return row


def incomplete_result(result):
    payload = result or {}
    return bool(payload.get("status") == "needs_review" or
                (payload.get("issues") and "collections" in payload) or
                (payload.get("failures") and not payload.get("curves")))


def new_run(session, row, calibration, state, *, model_name=None):
    key = fingerprint(dict(source=row.source_json, calibration=calibration,
                           state=state_signature(state), algorithm=ALGORITHM_VERSION))
    run = session.scalar(select(models.SpectrumRun).where(models.SpectrumRun.collection_id == row.id,
                                                           models.SpectrumRun.input_hash == key))
    if run and run.status == "succeeded" and not incomplete_result(run.result_json):
        return run, False
    if run is None:
        run = models.SpectrumRun(id=uuid.uuid4().hex, collection_id=row.id, input_hash=key,
            algorithm_version=ALGORITHM_VERSION, status="queued", calibration_json=calibration, model_name=model_name)
        session.add(run); session.flush()
    elif run.status not in {"queued", "running"}:
        run.status, run.error_code, run.error_message = "queued", None, None
    return run, True


def activate(row, run, state):
    if row.current_run_id != run.id:
        row.version += 1
        row.review_json = {}
    row.current_run_id = run.id
    row.state_key = state.get("state_key") if state else None
    row.state_signature = state_signature(state)


def complete_run(run, result):
    run.result_json = jsonable_encoder(result)
    incomplete = incomplete_result(result)
    run.status = "needs_review" if incomplete else "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    run.error_code = "spectra_extraction_incomplete" if incomplete else None
    run.error_message = "谱标定或提取未完成，请查看待处理原因后重试" if incomplete else None


def mask_public(payload, reviews):
    """公开谱仅返回已采纳曲线和有效频段；候选及点表同步裁剪。"""
    output = copy.deepcopy(payload)
    selected = []
    for curve in output.get("curves") or []:
        decision = reviews.get(curve["id"], {})
        if decision.get("status") not in {"accepted", "accepted_limited"}:
            continue
        intervals = decision.get("frequency_intervals_thz") or []
        if decision["status"] == "accepted_limited":
            curve["points"] = [p for p in curve["points"] if any(lo <= p["frequency_thz"] <= hi for lo, hi in intervals)]
        curve["acceptance"] = decision
        selected.append(curve)
    output["curves"] = selected
    ids = {c["id"] for c in selected}
    output["quality"]["curves"] = {k: v for k, v in output["quality"].get("curves", {}).items() if k in ids}
    if not any(c["kind"] == "cumulative_lambda" for c in selected):
        output["quality"].pop("cumulative_moment", None)
        output["quality"].pop("cumulative_endpoint", None)
    else:
        moment = output["quality"].get("cumulative_moment", {})
        moment.pop("monotone_frequency_thz", None)
        moment.pop("monotone_cumulative", None)
    # 未经采纳的其他谱不能经候选数组或标定对象泄露。
    output["calibration"]["curves"] = [c for c in output["calibration"]["curves"] if c["id"] in ids]
    alpha = next((c for c in selected if c["kind"] == "alpha2f"), None)
    dos = [c for c in selected if c["kind"] == "phonon_dos"]
    if alpha is None:
        for k in ("zero_baseline", "joint"):
            output["candidates"].pop(k, None)
        for k in ("integrals", "comparisons", "frequency_bins", "joint_validation", "one_pixel_sensitivity"):
            output["quality"].pop(k, None)
    else:
        frequencies = {p["frequency_thz"] for p in alpha["points"]}
        for key in ("zero_baseline", "joint"):
            candidate = output["candidates"].get(key, {})
            f = candidate.get("frequency_thz") or []
            keep = [i for i, v in enumerate(f) if v in frequencies]
            for name, values in list(candidate.items()):
                if isinstance(values, list) and len(values) == len(f) and f:
                    candidate[name] = [values[i] for i in keep]
        if reviews.get(alpha["id"], {}).get("status") == "accepted_limited":
            output["quality"]["metric_domain_note"] = "质量指标描述原提取运行的完整频域；已采纳数值仅限标注频段"
    norm = output["candidates"].get("dos_normalization", {})
    if norm:
        frequencies=norm.get("frequency_thz") or []
        components={}
        for curve in dos:
            key=curve["projection"] or curve["id"]
            values=norm.get("components",{}).get(key)
            if values is not None:
                allowed={p["frequency_thz"] for p in curve["points"]}
                components[key]=[v if f in allowed else None for f,v in zip(frequencies,values)]
        norm["components"]=components
        norm.pop("total",None)  # 不能通过总谱泄露未采纳分波或频段。
        if not components:
            output["candidates"].pop("dos_normalization")
    output["failures"] = []
    return output


def listing(session, ctx):
    rows = list(session.scalars(select(models.SpectrumCollection).where(
        models.SpectrumCollection.target == ctx["target"], models.SpectrumCollection.target_id == ctx["target_id"])))
    states = {s["state_key"]: s for s in ctx["states"]}
    result, jobs = [], []
    for row in rows:
        if row.panel_key.startswith("history-"):
            continue
        if ctx["target"] == "paper" and row.paper_revision != ctx["paper_revision"]:
            continue
        run = session.get(models.SpectrumRun, row.current_run_id) if row.current_run_id else None
        status = ("needs_review" if run and run.status == "succeeded" and incomplete_result(run.result_json)
                  else run.status if run else None)
        if row.panel_key == "__discovery__":
            if ctx["privileged"] and run:
                jobs.append(dict(id=run.id, status=status, error_code=run.error_code,
                    error_message=run.error_message, detail=run.result_json))
            continue
        if not run:
            continue
        source_stale = ("files" in ctx and row.source_json.get("source_sha256") not in
                        {f.get("sha256") for f in ctx["files"]})
        stale = source_stale or row.state_signature != state_signature(states.get(row.state_key))
        reviews = {} if stale else row.review_json or {}
        payload = run.result_json or dict(curves=[], candidates={}, quality={}, failures=[])
        # 排队或失败的新运行也保留其真实标定，供按谱类型导航；不生成数值曲线。
        if not payload.get("calibration") and (run.calibration_json or {}).get("curves"):
            payload = {**payload, "calibration": copy.deepcopy(run.calibration_json)}
        if stale:
            payload = copy.deepcopy(payload)
            for comparisons in payload.get("quality", {}).get("comparisons", {}).values():
                for comparison in comparisons.values():
                    comparison.update(status="unavailable", reason="材料条件或论文参考已变化，旧比较失效",
                                      signed_difference=None, absolute_difference=None, relative_difference_pct=None)
        if not ctx["privileged"]:
            if run.status != "succeeded" or not payload.get("curves"):
                continue
            payload = mask_public(payload, reviews)
            if not payload["curves"]:
                continue
        result.append(dict(id=row.id, version=row.version, state_key=row.state_key, stale=stale,
            source=row.source_json, run=dict(id=run.id, status=status, error_code=run.error_code,
                error_message=run.error_message, algorithm_version=run.algorithm_version, model_name=run.model_name),
            result=payload, review=reviews))
    return dict(items=result, jobs=jobs, version=ctx["version"], can_edit=ctx["can_edit"], can_review=ctx["can_review"])


def checked_row(session, ctx, row_id, version):
    row = session.scalar(select(models.SpectrumCollection).where(models.SpectrumCollection.id == row_id).with_for_update())
    if row is None or row.target != ctx["target"] or row.target_id != ctx["target_id"]:
        fail("spectra_collection_missing", "谱集合不属于当前目标", 404)
    assert_version(row.version, version)
    return row


def review_curve(session, ctx, row, curve_id, status, intervals, reason, user):
    if not ctx["can_review"]:
        fail("spectra_review_forbidden", "只有已批准的审核者可采纳正式谱", 403)
    state = next((s for s in ctx["states"] if s["state_key"] == row.state_key), None)
    source_stale = ("files" in ctx and row.source_json.get("source_sha256") not in
                    {f.get("sha256") for f in ctx["files"]})
    if source_stale or state is None or row.state_signature != state_signature(state):
        fail("spectra_review_stale", "来源或材料条件已变化，或材料尚未分配；请核对并重提取后审核")
    run = session.get(models.SpectrumRun, row.current_run_id)
    if not run or run.status != "succeeded":
        fail("spectra_not_ready", "谱提取尚未完成")
    curve = next((c for c in run.result_json.get("curves", []) if c["id"] == curve_id), None)
    if curve is None:
        fail("spectra_curve_missing", "曲线不存在", 404)
    if status == "accepted_limited" and (not intervals or not reason.strip()):
        fail("spectra_limited_reason_required", "限定采纳须填写有效频段和理由", 422)
    if any(not math.isfinite(v) for pair in intervals for v in pair):
        fail("spectra_interval_invalid", "有效频段必须为有限数值", 422)
    f = [p["frequency_thz"] for p in curve["points"]]
    if any(not f[0] <= lo < hi <= f[-1] for lo, hi in intervals):
        fail("spectra_interval_invalid", "有效频段超出所提取曲线", 422)
    data = copy.deepcopy(row.review_json or {})
    data[curve_id] = dict(status=status, frequency_intervals_thz=intervals if status == "accepted_limited" else [],
        reason=reason, reviewer_id=user.id, reviewed_at=datetime.now(timezone.utc).isoformat(), run_id=run.id)
    row.review_json = data
    row.version += 1


async def bind_to_paper(session, paper, draft, *, target=None, target_id=None):
    """原提交/返修事务内关联当前状态；保持历史运行，条件变化撤回采纳。"""
    if not await session.run_sync(available):
        return
    states = {s.state_key: s for s in (await session.scalars(select(models.MaterialState).where(
        models.MaterialState.paper_id == paper.id, models.MaterialState.paper_revision == paper.content_revision))).all()}
    from backend.services.paper_revisions import current_draft
    actual = await session.run_sync(lambda s: current_draft(s, paper))
    by_key = {s.get("state_key") or f"state-{i+1}": {**s, "_spectrum_structure_hashes": structure_dependencies(actual,i)}
              for i, s in enumerate(actual["material_states"])}
    if target and target_id:
        query = select(models.SpectrumCollection).where(models.SpectrumCollection.target == target,
            models.SpectrumCollection.target_id == target_id)
    else:
        query = select(models.SpectrumCollection).where(models.SpectrumCollection.target == "paper",
            models.SpectrumCollection.paper_id == paper.id,
            ~models.SpectrumCollection.panel_key.startswith("history-"))
    files = (await session.scalars(select(models.PaperFile).where(models.PaperFile.paper_id == paper.id))).all()
    for row in (await session.scalars(query)).all():
        if target in {"upload", "revision"}:
            conflict = await session.scalar(select(models.SpectrumCollection).where(
                models.SpectrumCollection.target == "paper", models.SpectrumCollection.target_id == str(paper.id),
                models.SpectrumCollection.source_key == row.source_key,
                models.SpectrumCollection.panel_key == row.panel_key))
            if conflict and conflict.id != row.id:
                conflict.panel_key = "history-" + conflict.id
                await session.flush()
        row.target, row.target_id = "paper", str(paper.id)
        row.paper_id, row.paper_revision = paper.id, paper.content_revision
        row.material_state_id = states[row.state_key].id if row.state_key in states else None
        source = row.source_json or {}
        matched = next((f for f in files if f.sha256 == source.get("source_sha256")), None)
        row.paper_file_id = matched.id if matched else None
        signature = state_signature(by_key.get(row.state_key))
        if row.state_signature != signature or target in {"upload", "revision"}:
            row.review_json = {}
        # 旧数值不能通过绑定新状态签名被“洗成”有效；变化后必须重新提取。
        row.version += 1


async def copy_to_revision(session, paper, revision_id):
    if not await session.run_sync(available):
        return
    rows = (await session.scalars(select(models.SpectrumCollection).where(
        models.SpectrumCollection.target == "paper", models.SpectrumCollection.paper_id == paper.id,
        models.SpectrumCollection.paper_revision == paper.content_revision))).all()
    for original in rows:
        if original.panel_key == "__discovery__" or original.panel_key.startswith("history-"):
            continue
        row = models.SpectrumCollection(id=uuid.uuid4().hex, target="revision", target_id=revision_id,
            owner_id=original.owner_id, paper_id=paper.id, paper_revision=paper.content_revision,
            paper_file_id=original.paper_file_id, material_state_id=original.material_state_id,
            state_key=original.state_key, state_signature=original.state_signature,
            source_key=original.source_key, panel_key=original.panel_key,
            source_json=copy.deepcopy(original.source_json), review_json={}, version=1)
        session.add(row); await session.flush()
        run = await session.get(models.SpectrumRun, original.current_run_id)
        if run:
            duplicate = models.SpectrumRun(id=uuid.uuid4().hex, collection_id=row.id,
                input_hash=run.input_hash, algorithm_version=run.algorithm_version, model_name=run.model_name,
                status=run.status, calibration_json=copy.deepcopy(run.calibration_json),
                result_json=copy.deepcopy(run.result_json), completed_at=run.completed_at)
            session.add(duplicate); row.current_run_id = duplicate.id
