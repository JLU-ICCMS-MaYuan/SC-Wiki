"""DOS 分层积分：相对面积、共同归一化和独立绝对密度；不改写描线。"""
from __future__ import annotations

import math
from .contracts import FREQUENCY_FACTORS
from .relative import pixel_curve
from .samples import connected_samples
from .topology import finite

METHOD = "dos-relative-v1"


def unavailable(reason):
    return dict(status="unavailable", reason=str(reason))


def demand(condition, reason):
    if not condition:
        raise ValueError(reason)


def fractions(counts):
    if not counts or any(not finite(v) or v <= 0 for v in counts.values()):
        return {}
    try:
        total = math.fsum(counts.values())
    except OverflowError:
        return {}
    return {k: v/total for k, v in counts.items()} if finite(total) else {}


def area(f, a):
    value = math.fsum((y-x)*(v/2+w/2) for x, y, v, w in zip(f, f[1:], a, a[1:]))
    demand(finite(value), "积分数值溢出")
    return value


def coverage_reason(curve, calibration, frequency):
    """完整范围必须有来源声明且实际采样覆盖；图框本身不自动证明完整。"""
    if curve.get("clipped_frequencies_thz"):
        return "曲线存在抵框裁峰，无法确定完整模式面积"
    upper = (calibration.get("zero_boundaries_thz") or [None, None])[1]
    if not finite(upper):
        if not calibration.get("frequency_range_confirmed"):
            return "原图完整频段尚待核对"
        ticks = calibration.get("frequency_ticks") or []
        roi = calibration.get("roi")
        if len(ticks) < 2 or not roi:
            return "完整频段缺少可核对的原图边界"
        (p0, v0), (p1, v1) = ticks[0], ticks[-1]
        if p1 == p0:
            return "频率标定退化"
        factor = FREQUENCY_FACTORS.get(calibration.get("frequency_unit", "THz"))
        if factor is None:
            return "频率单位未知"
        indices = (1, 3) if calibration.get("frequency_direction") == "y" else (0, 2)
        upper = max((v0+(roi[i]-p0)*(v1-v0)/(p1-p0))*factor for i in indices)
    if not finite(upper) or upper <= 0 or frequency[-1] < upper - 1e-9*max(1, upper):
        return "实际采样未覆盖已核对的完整高频边界"
    return None


def calculate_dos(payload, primitive=None, composition=None):
    curves = [c for c in payload.get("curves", []) if c["kind"] == "phonon_dos"]
    panel = payload.get("calibration") or {}
    calibrations = {c["id"]: c for c in panel.get("curves", [])}
    components, samples = [], {}
    for curve in curves:
        row = dict(curve_id=curve["id"], projection=curve.get("projection") or curve["id"],
                   unit="pixel·THz")
        try:
            relative, basis = pixel_curve(payload, curve)
            demand(basis["kind"] != "stored_relative_values", "缺少幅值零基线或像素换算，不能计算像素面积")
            f, p = connected_samples(relative, payload.get("manual_documents", {}).get(curve["id"]))
            value = area(f, p)
            row.update(status="available", area=value, frequency_interval_thz=[f[0], f[-1]],
                       amplitude_basis=basis)
            samples[curve["id"]] = (f, p)
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            row.update(unavailable(exc))
        components.append(row)

    shares = unavailable("缺少完整共同尺度投影")
    normalization = unavailable("缺少完整共同尺度投影")
    candidate = None
    atoms = (primitive or {}).get("primitive_atoms")
    valid_atoms = isinstance(atoms, int) and not isinstance(atoms, bool) and atoms > 0
    primitive_fractions = fractions((primitive or {}).get("species_counts"))
    formula_fractions = fractions((composition or {}).get("species_counts"))
    expected = primitive_fractions or formula_fractions
    source = primitive if primitive_fractions else (composition or {}).get("source")
    try:
        demand(curves, "当前没有声子 DOS 曲线")
        demand(all(c["status"] == "available" for c in components), "部分曲线不能积分，不能计算全部分波占比")
        demand(panel.get("projection_complete"), "元素投影完整性尚待核对")
        demand(panel.get("projection_scale_confirmed"), "各分波共同幅值尺度尚待核对")
        labels = [c["projection"].strip().lower() for c in components]
        demand(len(set(labels)) == len(labels) and not (len(labels) > 1 and "total" in labels),
               "投影重复或总谱与分波同时存在，不能相加")
        # 识别提取失败的隐藏分波，不因余下曲线有值就声称完整集合。
        expected_ids = {c["id"] for c in panel.get("curves", []) if c.get("kind") == "phonon_dos"}
        demand(not expected_ids or expected_ids == {c["id"] for c in curves}, "部分标定分波提取失败，投影不完整")
        total = math.fsum(c["area"] for c in components)
        demand(finite(total) and total > 0, "全部像素面积为零或溢出，不能确定占比或共同系数")
        shares = dict(status="available", total_area=total, unit="pixel·THz",
                      fractions={c["curve_id"]: c["area"]/total for c in components},
                      expected_fractions={}, composition_source=source)
        standard = all(c.get("physical_definition_confirmed") for c in curves)
        if standard:
            shares["expected_fractions"] = {c["curve_id"]: expected[c["projection"]]
                                           for c in components if c["projection"] in expected}
        else:
            shares["expected_reason"] = "标准原子振动投影定义尚待核对，暂不套用原子数占比"
        if not expected:
            shares["expected_reason"] = "缺少明确的化学计量或结构计数依据"
        demand(standard, "标准原子振动投影定义尚待核对，不能套用 3N")
        for curve in curves:
            reason = coverage_reason(curve, calibrations.get(curve["id"], {}), samples[curve["id"]][0])
            demand(reason is None, f"{curve.get('projection') or curve['id']}：{reason}")
        demand(valid_atoms, "缺少可信原胞原子数 N；化学式比例不能确定原胞倍数")
        if primitive_fractions and formula_fractions:
            demand(primitive_fractions.keys() == formula_fractions.keys() and all(
                math.isclose(v, formula_fractions[k], rel_tol=1e-8, abs_tol=1e-12)
                for k, v in primitive_fractions.items()), "当前化学式与结构元素比例不一致，暂不归一化")
        counts = (primitive or {}).get("species_counts") or {}
        if counts:
            demand(all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in counts.values())
                   and sum(counts.values()) == atoms, "原胞元素计数与 N 不一致")
            demand(labels == ["total"] or {c["projection"] for c in components} == set(counts),
                   "当前分波元素与原胞元素集合不一致")
        coefficient = 3*atoms/total
        demand(finite(coefficient) and coefficient > 0, "共同系数数值溢出")
        normalized = {}
        integrals, expected_modes, deviations = {}, {}, {}
        for c in components:
            cid = c["curve_id"]; f, p = samples[cid]
            density = [coefficient*v for v in p]
            demand(all(finite(v) for v in density), "归一化密度数值溢出")
            integrals[cid] = area(f, density)
            normalized[cid] = dict(frequency_thz=f, density=density, amplitude_basis=c["amplitude_basis"])
            count = counts.get(c["projection"])
            if count is not None:
                target = 3*count
                delta = abs(integrals[cid]-target)
                expected_modes[cid] = target
                deviations[cid] = dict(absolute_difference=delta, relative_difference_pct=100*delta/target)
        normalization = dict(status="available", label="按 3N 归一化", coefficient=coefficient,
                             primitive_atoms=atoms, target_modes=3*atoms,
                             component_mode_integrals=integrals, expected_modes=expected_modes,
                             deviations=deviations, structure_evidence=primitive,
                             total_mode_integral=math.fsum(integrals.values()), unit="modes/THz/primitive_cell")
        candidate = dict(status="available", method=METHOD, coefficient=coefficient,
                         curves=normalized, unit="modes/THz/primitive_cell", structure_evidence=primitive)
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        if shares["status"] != "available":
            shares = unavailable(exc)
        normalization = unavailable(exc)
    if valid_atoms:
        normalization.update(primitive_atoms=atoms, target_modes=3*atoms, structure_evidence=primitive)
    relative = dict(method=METHOD, components=components, shares=shares, normalization=normalization)
    return dict(relative=relative, absolute=dos_integrals(payload, primitive), candidate=candidate)


def apply_dos(payload, result, base_run_id=None):
    """替换本次派生结果，清除旧候选，保留原始曲线。"""
    quality = payload.setdefault("quality", {})
    quality["dos_relative"] = result["relative"]
    quality["dos_mode_integral"] = result["absolute"]
    for key in ("dos_normalization", "projection_mode_check"):
        quality.pop(key, None)
    candidates = payload.setdefault("candidates", {})
    for key in ("dos_normalization", "dos_relative_normalized"):
        candidates.pop(key, None)
    if result["candidate"] is not None:
        candidates["dos_relative_normalized"] = {**result["candidate"], "base_run_id": base_run_id}
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
               "未提供独立绝对密度刻度；相对面积与按 3N 归一化结果单独展示")
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
