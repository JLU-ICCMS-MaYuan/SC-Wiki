"""对当前保存谱主动积分；不重新读图、不修补点、不授予科学采纳。"""
from __future__ import annotations

import copy
import math
import uuid
from datetime import datetime, timezone

from backend import models
from . import manual
from .context import primitive_for, reference_choices
from .contracts import fingerprint
from .engine import unavailable
from .topology import diagnose
from .preflight import prepare_repairs
from .samples import connected_samples
from .relative import calculate_alpha, pixel_curve

VERSION = "spectra-recalculate-relative-v1"


def demand(condition, reason):
    if not condition:
        raise ValueError(reason)


def alpha_integrals(payload, references=None):
    """兼容调用入口；λ仅发布论文参考归一化结果。"""
    from .relative import calculate_alpha, pixel_curve
    return calculate_alpha(payload,references or {})["raw"]


def dos_integrals(payload, primitive):
    try:
        curves = [c for c in payload["curves"] if c["kind"] == "phonon_dos"]
        demand(curves, "当前没有声子DOS曲线")
        panel = payload.get("calibration", {})
        demand(panel.get("projection_complete") and panel.get("projection_scale_confirmed"),
               "声子DOS的完整投影与共同幅值尺度尚待核对")
        labels = [(c.get("projection") or c["id"]).strip().lower() for c in curves]
        demand(len(set(labels)) == len(labels) and not (len(labels) > 1 and "total" in labels),
               "投影重复或总谱与分波同时存在，不能相加")
        units = {c.get("unit") for c in curves}
        demand(len(units) == 1 and units <= {"modes/THz", "modes/THz/primitive_cell"},
               "DOS绝对密度单位尚待核对，不能积分相对像素")
        integrals, intervals = {}, []
        for curve in curves:
            f, a = connected_samples(curve, payload.get("manual_documents", {}).get(curve["id"]))
            integrals[curve["id"]] = math.fsum((y-x)*(v+w)/2 for x,y,v,w in zip(f,f[1:],a,a[1:]))
            intervals.append([f[0], f[-1]])
        value = math.fsum(integrals.values())
        demand(math.isfinite(value), "DOS积分数值溢出")
        result = dict(status="available", integral=value, component_integrals=integrals,
                      frequency_interval_thz=[0.,max(v[1] for v in intervals)], component_intervals=dict(zip((c["id"] for c in curves),intervals)), comparison_status="unavailable",
                      reason="缺少原胞原子数或每原胞绝对密度依据，暂不比较3N")
        atoms = (primitive or {}).get("primitive_atoms")
        if units == {"modes/THz/primitive_cell"} and isinstance(atoms, int) and not isinstance(atoms, bool) and atoms > 0:
            result.update(comparison_status="available", primitive_atoms=atoms, target_modes=3*atoms,
                          absolute_difference=abs(value-3*atoms), relative_difference_pct=100*abs(value-3*atoms)/(3*atoms),
                          structure_evidence=primitive, reason="")
        return result
    except (ValueError, OverflowError) as exc:
        return unavailable(exc)


def save(session, ctx, row, run, state, kind, user):
    manual.assert_latest(session, ctx, row, kind)
    payload = copy.deepcopy(run.result_json)
    manual.require(any(c["kind"] == kind for c in payload["curves"]), "当前谱类型没有可计算数据")
    now = datetime.now(timezone.utc)
    repairs = prepare_repairs(payload,kind,now.isoformat())
    quality = payload.setdefault("quality", {})
    quality.setdefault("automatic_repairs",{})[kind]=repairs
    diagnostic_payload=payload
    if kind=="alpha2f":
        try:
            diagnostic_payload={**payload,"curves":[pixel_curve(payload,c)[0] if c["kind"]=="alpha2f" else c for c in payload["curves"]]}
        except (ValueError,ZeroDivisionError):
            pass
    quality.setdefault("trace_diagnostics", {})[kind] = diagnose(diagnostic_payload, kind)
    if kind == "alpha2f":
        references, reasons = reference_choices(state)
        computed = calculate_alpha(payload,references,reasons)
        quality["integrals"] = {"raw": computed["raw"]}
        quality["comparisons"] = {"raw": {"omega_log": computed["comparison"]}}
        payload.setdefault("candidates",{}).pop("alpha2f_lambda_normalized",None)
        if computed["candidate"] is not None:
            computed["candidate"]["base_run_id"]=run.id
            payload["candidates"]["alpha2f_lambda_normalized"]=computed["candidate"]
    else:
        quality["dos_mode_integral"] = dos_integrals(payload, primitive_for(state, ctx.get("draft", {})))
    quality.setdefault("recalculations", {})[kind] = dict(base_run_id=run.id, calculated_at=now.isoformat(),
                                                         author_id=user.id, algorithm_version=VERSION)
    payload["status"] = "needs_review"
    payload["algorithm_version"] = VERSION
    fresh = models.SpectrumRun(id=uuid.uuid4().hex, collection_id=row.id,
        input_hash=fingerprint(dict(parent=run.id, kind=kind, actor=user.id, algorithm=VERSION)),
        algorithm_version=VERSION, status="succeeded", calibration_json=copy.deepcopy(run.calibration_json),
        result_json=payload, completed_at=now)
    session.add(fresh)
    session.flush()
    row.current_run_id = fresh.id
    row.version += 1
    row.review_json = {}
    return fresh
