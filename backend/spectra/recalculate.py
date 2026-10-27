"""对当前保存谱主动积分；不重新读图、不修补点、不授予科学采纳。"""
from __future__ import annotations

import copy
import math
import uuid
from datetime import datetime, timezone

from backend import models
from . import manual
from .context import primitive_for, references_for
from .contracts import fingerprint
from .digitize import spectral_integrals
from .engine import comparison, unavailable
from .topology import build_graph, graph_parts, diagnose

VERSION = "spectra-recalculate-v2"


def demand(condition, reason):
    if not condition:
        raise ValueError(reason)


def connected_samples(curve, document=None):
    """线性复杂度遍历真实连接，拒绝断片/分叉/环；不按频率排序来填缺口。"""
    points = curve.get("points") or []
    demand(len(points) >= 2, "至少需要两个有效数据点")
    nodes, edges, invalid = build_graph(curve)
    demand(not invalid, "描线含失效连接")
    demand(all(len(e) <= 2 for e in edges.values()), "曲线存在分叉，请检查下方问题坐标")
    components, cycles = graph_parts(edges)
    demand(not cycles, "曲线存在闭环，请检查下方问题坐标")
    demand(len(components) == 1, "曲线存在缺口或孤立点，请检查下方未连接片段坐标")
    ends = [identity for identity, e in edges.items() if len(e) == 1]
    demand(len(ends) == 2, "曲线缺少有效端点")
    ordered, seen, current = [], set(), ends[0]
    while current not in seen:
        seen.add(current)
        ordered.append(nodes[current])
        next_ids = [key for key in edges[current] if key not in seen]
        if not next_ids:
            break
        current = next(iter(next_ids))
    demand(len(seen) == len(points), "曲线存在未连接片段，不能跨缺口积分")
    f = [p.get("frequency_thz") for p in ordered]
    a = [p.get("reconstructed_amplitude") for p in ordered]
    demand(all(manual.finite(v) for v in f + a), "曲线含缺失或非有限数值")
    amplitude_axis = curve.get("axis_calibration", {}).get("amplitude", {})
    for i, point in enumerate(ordered):
        if amplitude_axis and manual.finite(point.get("amplitude_pixel")):
            terms = (amplitude_axis["slope"] * point["amplitude_pixel"], amplitude_axis["intercept"])
            error = 8 * sum(math.ulp(abs(term)) for term in terms)
            if abs(a[i]) <= error:
                a[i] = 0.  # 仅消除线性标定的浮点消去误差，不回写源数据。
    if f[0] > f[-1]:
        f.reverse()
        a.reverse()
    demand(all(y > x for x, y in zip(f, f[1:])), "曲线存在重复或回折频率，不能作为单值谱积分")
    demand(all(v >= 0 for v in a), "幅值存在负数，请核对零基线")
    # 只消除标定浮点舍入；不把邻近频率的真实数据改成零。
    tolerance = 1e-12 * max(1., abs(f[-1]))
    demand(abs(f[0]) <= tolerance, "当前曲线未从真实零频开始")
    f[0] = 0.
    if document is not None:
        demand(manual.zero_report(document)["complete"], "当前曲线的零频位置或零频点尚未确认")
    axis = curve.get("axis_calibration", {}).get("frequency")
    roi = curve.get("roi")
    if axis and roi:
        bounds = (roi[0], roi[2]) if curve.get("frequency_direction") == "x" else (roi[1], roi[3])
        if document:
            plot = document["source"]["plot"]
            bounds = (plot[0], plot[2]) if document["calibration"]["direction"] == "x" else (plot[1], plot[3])
        upper = max(axis["slope"] * p + axis["intercept"] for p in bounds)
        demand(math.isclose(f[-1], upper, rel_tol=1e-10, abs_tol=1e-10),
               "曲线未覆盖当前图框的完整高频端，请核对末端数据")
    return f, a


def amplitude_evidence(payload, curve):
    document = payload.get("manual_documents", {}).get(curve["id"])
    if document is not None:
        return document["calibration"].get("amplitudeEvidence", "").strip()
    spec = next((s for s in payload.get("calibration", {}).get("curves", []) if s["id"] == curve["id"]), {})
    return (spec.get("amplitude_evidence") or "").strip()


def alpha_integrals(payload):
    params = {}
    try:
        curves = [c for c in payload["curves"] if c["kind"] == "alpha2f"]
        demand(len(curves) == 1, "当前需要一条明确的α²F目标曲线")
        curve = curves[0]
        demand(curve.get("physical_definition_confirmed"), "α²F物理定义及普通频率定义尚未确认")
        f, a = connected_samples(curve, payload.get("manual_documents", {}).get(curve["id"]))
        evidence = amplitude_evidence(payload, curve)
        demand(evidence, "α²F幅值标定依据尚待核对；相对谱也须提供零基线和统一倍率依据")
        absolute = curve.get("unit") == "dimensionless"
        demand(absolute or curve.get("unit") == "pixel", "α²F幅值单位尚待核对")
        values = spectral_integrals(f, a)
        demand(all(v is None or not isinstance(v, (int, float)) or math.isfinite(v) for v in values.values()),
               "积分数值溢出，请核对幅值与频率")
        params["lambda"] = (dict(status="available", value=values["lambda_integral"]) if absolute
                            else unavailable("λ需要α²F绝对幅值刻度；当前只有相对幅值"))
        params["omega_log"] = (dict(status="available", value=values["omega_log_k"]) if values["omega_log_k"] is not None
                               else unavailable("谱积分为零，ωlog无定义"))
        # 相对尺度下的中间λ不是物理λ，不发布该值。
        if not absolute:
            values.pop("zero_interval_lambda", None)
            values["lambda_integral"] = None
        return {**values, "status": "available", "parameters": params,
                "maximum_integrated_thz": f[-1], "amplitude_basis": "absolute" if absolute else "relative_uniform_scale"}
    except (ValueError, OverflowError) as exc:
        return {**unavailable(exc), "parameters": {k: unavailable(exc) for k in ("lambda", "omega_log")}}


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
        demand(all(math.isclose(interval[1], intervals[0][1], rel_tol=1e-10, abs_tol=1e-10) for interval in intervals),
               "DOS各分波覆盖的频率范围不一致")
        value = math.fsum(integrals.values())
        demand(math.isfinite(value), "DOS积分数值溢出")
        result = dict(status="available", integral=value, component_integrals=integrals,
                      frequency_interval_thz=intervals[0], comparison_status="unavailable",
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
    quality = payload.setdefault("quality", {})
    quality.setdefault("trace_diagnostics", {})[kind] = diagnose(payload, kind)
    if kind == "alpha2f":
        raw = alpha_integrals(payload)
        quality["integrals"] = {"raw": raw}
        refs = references_for(state)
        quality["comparisons"] = {"raw": {
            name: comparison(raw["parameters"][name].get("value"), refs.get(name, {}).get("value"),
                             refs.get(name, {}).get("source"), refs.get(name, {}).get("same_conditions", False))
            for name in ("lambda", "omega_log")}}
    else:
        quality["dos_mode_integral"] = dos_integrals(payload, primitive_for(state, ctx.get("draft", {})))
    now = datetime.now(timezone.utc)
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
