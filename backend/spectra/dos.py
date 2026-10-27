"""DOS 分层积分：相对面积、共同归一化和独立绝对密度；不改写描线。"""
from __future__ import annotations

import math
from .relative import pixel_curve
from .samples import connected_samples
from .topology import finite

METHOD = "dos-relative-v2"


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


def element_ratio(components, expected, source):
    """同一参考元素下比较比例；接近程度用与参考选择无关的占比差表示。"""
    if not expected:
        return unavailable("缺少化学计量依据，暂不能比较元素比例")
    if {c["projection"] for c in components} != set(expected):
        return unavailable("分波元素与化学计量元素集合不一致，暂不能比较元素比例")
    observed = fractions({c["projection"]: c["area"] for c in components if c["area"] > 0})
    if not observed:
        return unavailable("没有正的面积，无法选择比例参考元素")
    reference = min(observed, key=lambda k: (expected[k], k))
    elements = [reference] + [c["projection"] for c in components if c["projection"] != reference]
    estimated = [observed.get(k, 0)/observed[reference] for k in elements]
    target = [expected[k]/expected[reference] for k in elements]
    if not all(finite(v) for v in estimated + target):
        return unavailable("元素比例数值溢出")
    differences = {k: 100*(observed.get(k, 0)-expected[k]) for k in elements}
    formula = (source or {}).get("formula") if (source or {}).get("kind") == "material_formula" else None
    return dict(status="available", reference_element=reference, elements=elements,
                estimated_ratio=estimated, expected_ratio=target, formula=formula,
                reference_label="化学式比例" if formula else "结构原子数比例",
                share_difference_pp=differences, max_share_difference_pp=max(abs(v) for v in differences.values()))


def calculate_dos(payload, primitive=None, composition=None):
    curves = [c for c in payload.get("curves", []) if c["kind"] == "phonon_dos"]
    panel = payload.get("calibration") or {}
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
    expected = formula_fractions or primitive_fractions
    source = (composition or {}).get("source") if formula_fractions else primitive
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
            shares["element_ratio"] = element_ratio(components, expected, source)
        else:
            shares["expected_reason"] = "标准原子振动投影定义尚待核对，暂不套用原子数占比"
        if not expected:
            shares["expected_reason"] = "缺少明确的化学计量或结构计数依据"
        demand(standard, "标准原子振动投影定义尚待核对，不能套用 3N")
        clipped = [c.get("projection") or c["id"] for c in curves if c.get("clipped_frequencies_thz")]
        demand(not clipped, "、".join(clipped) + "：曲线存在已记录的抵框裁峰，无法确定完整模式面积")
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
