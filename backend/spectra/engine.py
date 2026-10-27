"""图像与标定生成可追溯谱及分项质量；正文答案仅用于事后比较。"""
from __future__ import annotations
import copy
import numpy as np
from .contracts import PanelCalibration, FREQUENCY_FACTORS, ALGORITHM_VERSION
from .digitize import LinearAxis, extract_curve, spectral_integrals
from .quality import zero_baseline_candidate, cumulative_moments
from .joint_reconstruction import reconstruct_joint, increment_envelope
from .scientific_review import independent_integral
from .relative import calculate_alpha
from .dos import calculate_dos, apply_dos, dos_integrals


def comparison(value, reference, source=None, same_conditions=False):
    if value is None or reference is None or not source or not same_conditions:
        return dict(status="unavailable", reason="缺少同条件、可定位的论文报告值", reference=reference,
                    source=source, signed_difference=None, absolute_difference=None, relative_difference_pct=None)
    delta = value - reference
    return dict(status="available", value=value, reference=reference, source=source,
                signed_difference=delta, absolute_difference=abs(delta),
                relative_difference_pct=100 * delta / abs(reference) if reference != 0 else None,
                meaning="相对同条件论文报告值的偏差；不是整条谱真实误差")


def unavailable(reason):
    return dict(status="unavailable", reason=str(reason))


def attempt(operation):
    try:
        return operation()
    except ValueError as exc:
        return unavailable(exc)


def coverage(curve):
    points = curve["points"]
    counts = curve["point_counts"]
    size = len(points)
    longest = current = 0
    for p in points:
        current = current + 1 if p["observed_amplitude"] is None else 0
        longest = max(current, longest)
    missing_intervals=[]
    start=None
    for i,p in enumerate(points):
        if p["reconstructed_amplitude"] is None and start is None:
            start=i
        if start is not None and (p["reconstructed_amplitude"] is not None or i==len(points)-1):
            end=i-1 if p["reconstructed_amplitude"] is not None else i
            missing_intervals.append([points[start]["frequency_thz"],points[end]["frequency_thz"]])
            start=None
    return dict(total_points=size, counts=counts,
                rejected_chromatic_pixels=sum(p.get("rejected_chromatic_pixels", 0) for p in points),
                ambiguous_samples=sum(p.get("detection_mode") == "ambiguous_components" for p in points),
                frequency_interval_thz=[points[0]["frequency_thz"],points[-1]["frequency_thz"]],
                omitted_low_frequency_interval_thz=([0.,points[0]["frequency_thz"]] if points[0]["frequency_thz"]>0 else None),
                missing_frequency_intervals_thz=missing_intervals,
                observed_fraction=counts["observed"] / size,
                missing_fraction=counts["missing"] / size,
                reconstructed_fraction=(size - counts["observed"] - counts["missing"]) / size,
                chromatic_recovered_points=curve["chromatic_recovered_points"],
                largest_unobserved_gap_samples=longest,
                clipped_frequencies_thz=curve["clipped_frequencies_thz"],
                frequency_tick_residual=curve["axis_calibration"]["frequency"]["max_tick_residual"],
                amplitude_tick_residual=curve["axis_calibration"]["amplitude"]["max_tick_residual"],
                envelope_is_statistical_confidence_interval=False)


def extract_panel(rgb: np.ndarray, calibration: dict, *, references: dict | None = None,
                  primitive: dict | None = None, composition: dict | None = None) -> dict:
    panel = PanelCalibration.model_validate(calibration)
    refs = references or {}
    curves, failures, metrics = [], [], {}
    specs = {}
    for c in panel.curves:
        spec = c.model_dump()
        spec["scale"] = c.amplitude_scale
        try:
            fextent = rgb.shape[1] if c.frequency_direction == "x" else rgb.shape[0]
            aextent = rgb.shape[0] if c.frequency_direction == "x" else rgb.shape[1]
            for ticks, extent in ((c.frequency_ticks, fextent), (c.amplitude_ticks, aextent)):
                if any(not 0 <= p < extent for p, _ in ticks):
                    raise ValueError("坐标刻度像素超出原图")
                ordered = sorted(ticks)
                steps = np.diff([v for _, v in ordered])
                if not (np.all(steps > 0) or np.all(steps < 0)):
                    raise ValueError("坐标刻度不单调，不能使用线性标定")
            if c.display_bbox and (c.display_bbox[2] >= rgb.shape[1] or c.display_bbox[3] >= rgb.shape[0]):
                raise ValueError("显示裁切框超出原图")
            ticks = [[p, v * FREQUENCY_FACTORS[c.frequency_unit]] for p, v in c.frequency_ticks]
            axis = LinearAxis.fit(ticks)
            if axis.residual > abs(axis.slope):
                raise ValueError("坐标刻度残差超过一个像素，请核对标定")
            spec["zero_boundaries_thz"] = [None, None]
            curve = extract_curve(rgb, spec, axis)
        except ValueError as exc:
            failures.append(dict(curve_id=c.id, reason=str(exc)))
            continue
        curve["source_frequency_unit"] = c.frequency_unit
        curve["display_bbox"] = list(c.display_bbox) if c.display_bbox else None
        curve["canonical_frequency_unit"] = "THz"
        curve["physical_definition_confirmed"] = c.physical_definition_confirmed
        # 已有实际单位 DOS 的密度随 dν 转换；像素相对幅值不用伪单位转换。
        if c.kind == "phonon_dos" and c.unit == "modes_per_source_frequency":
            factor = FREQUENCY_FACTORS[c.frequency_unit]
            for p in curve["points"]:
                for k in ("observed_amplitude", "reconstructed_amplitude"):
                    if p[k] is not None:
                        p[k] /= factor
            curve["axis_calibration"]["amplitude"] = {k: v / factor for k, v in curve["axis_calibration"]["amplitude"].items()}
            curve["unit"] = "modes/THz/primitive_cell"
        curves.append(curve)
        specs[c.id] = spec
        metrics[c.id] = coverage(curve)
        metrics[c.id].update(frequency_tick_count=len(c.frequency_ticks), amplitude_tick_count=len(c.amplitude_ticks),
                            frequency_pixel_resolution_thz=abs(axis.slope),
                            linearity_independently_checkable=len(c.frequency_ticks)>2 and len(c.amplitude_ticks)>2)
    result = dict(algorithm_version=ALGORITHM_VERSION, calibration=panel.model_dump(), curves=curves,
                  failures=failures, quality=dict(curves=metrics, limitations=[]), candidates={})
    if failures or any(metric["ambiguous_samples"] for metric in metrics.values()):
        result["status"] = "needs_review"
    q = result["quality"]
    alpha = next((c for c in curves if c["kind"] == "alpha2f"), None)
    cumulative = next((c for c in curves if c["kind"] == "cumulative_lambda"), None)
    q["integrals"] = {}
    if alpha:
        if not alpha["physical_definition_confirmed"] or alpha["unit"] != "dimensionless" or not specs[alpha["id"]].get("amplitude_evidence"):
            q["integrals"]["raw"] = unavailable("α²F 独立幅值刻度依据、单位或普通频率定义尚未确认")
        else:
            f = [p["frequency_thz"] for p in alpha["points"]]
            a = [p["reconstructed_amplitude"] for p in alpha["points"]]
            q["integrals"]["raw"] = (unavailable("谱存在缺口，不能给出完整频段积分") if any(v is None for v in a)
                                      else attempt(lambda: spectral_integrals(f, a)))
            q["low_frequency_sensitivity"] = [attempt(lambda cut=cut: spectral_integrals(f, a, cut)) for cut in (.5, 1, 2)]
            base = attempt(lambda: zero_baseline_candidate(rgb, alpha, specs[alpha["id"]]))
            result["candidates"]["zero_baseline"] = base
            if base["status"] == "conditional_candidate":
                q["integrals"]["zero_baseline"] = base["integral"]
                q["unresolved_amplitude_interval"] = base["unresolved_amplitude_interval"]
                pixel = abs(alpha["axis_calibration"]["amplitude"]["slope"])
                q["one_pixel_sensitivity"] = [dict(amplitude_shift_px=shift,
                    **attempt(lambda shift=shift: spectral_integrals(f,
                        [max(0, v + shift * pixel) if v and v > 0 else v for v in base["amplitude"]])))
                    for shift in (-1, 0, 1)]
                if cumulative and cumulative["physical_definition_confirmed"]:
                    joint = attempt(lambda: reconstruct_joint(alpha, cumulative, base))
                    result["candidates"]["joint"] = joint
                    if joint["status"] == "physics_constrained_candidate":
                        q["integrals"]["joint"] = spectral_integrals(joint["frequency_thz"], joint["alpha2f"])
                        q["joint_validation"] = {k: v for k, v in joint.items()
                            if k not in ("frequency_thz", "alpha2f", "cumulative_lambda", "alpha_lower_bound", "alpha_upper_bound")}
    if cumulative and cumulative["physical_definition_confirmed"]:
        observed = [p for p in cumulative["points"] if p["observed_amplitude"] is not None]
        if observed:
            q["cumulative_endpoint"] = dict(value=observed[-1]["observed_amplitude"],
                                           frequency_thz=observed[-1]["frequency_thz"])
        q["cumulative_moment"] = attempt(lambda: cumulative_moments(
            [p["frequency_thz"] for p in cumulative["points"]],
            [p["reconstructed_amplitude"] for p in cumulative["points"]]))
        base = result["candidates"].get("zero_baseline", {})
        if alpha and base.get("status") == "conditional_candidate" and len(observed) >= 2:
            lo = max(alpha["points"][0]["frequency_thz"], observed[0]["frequency_thz"])
            hi = min(alpha["points"][-1]["frequency_thz"], observed[-1]["frequency_thz"])
            edges = [lo, *(x for x in np.arange(5, hi, 5).tolist() if x > lo), hi]
            q["frequency_bins"] = []
            for left, right in zip(edges[:-1], edges[1:]):
                def bin_result():
                    env = increment_envelope(cumulative, left, right)
                    val, _ = independent_integral(np.array(base["frequency_thz"]), np.array(base["amplitude"]), left, right)
                    b = dict(frequency_thz=[left, right], observed_envelope=env,
                             raw_candidate_contribution=val, raw_compatible=env["lower"] <= val <= env["upper"])
                    joint = result["candidates"].get("joint", {})
                    if joint.get("status") == "physics_constrained_candidate":
                        jval, _ = independent_integral(np.array(joint["frequency_thz"]), np.array(joint["alpha2f"]), left, right)
                        b.update(joint_contribution=jval, joint_compatible=env["lower"] <= jval <= env["upper"])
                    return b
                if right > left:
                    q["frequency_bins"].append(attempt(bin_result))
    q["comparisons"] = {variant: {name: comparison(values.get(key), refs.get(name, {}).get("value"),
        refs.get(name, {}).get("source"), refs.get(name, {}).get("same_conditions", False))
        for name, key in (("lambda", "lambda_integral"), ("omega_log", "omega_log_k"))}
        for variant, values in q["integrals"].items()}
    if any(c["kind"] == "phonon_dos" for c in curves):
        apply_dos(result, calculate_dos(result, primitive, composition))
    q["limitations"] = ["图像包络不是统计置信区间", "积分一致是物理约束，不独立证明准确度",
                        "抵框峰只提供带掩膜候选，不唯一恢复峰顶", "质量指标不自动授予科学采纳"]
    if alpha:
        relative=calculate_alpha(result,refs)
        q["integrals"]["raw"]=relative["raw"]
        for comparisons in q["comparisons"].values():
            comparisons.pop("lambda",None)
        q["comparisons"]["raw"]={"omega_log":relative["comparison"]}
        if relative["candidate"] is not None:
            result["candidates"]["alpha2f_lambda_normalized"]=relative["candidate"]
    return copy.deepcopy(result)


def dos_mode_integral(curves, primitive, complete, common_scale):
    """兼容旧调用，绝对积分使用与正式重算相同的实现。"""
    return dos_integrals(dict(curves=[{**c, "kind": "phonon_dos"} for c in curves],
                              calibration=dict(projection_complete=complete,
                                               projection_scale_confirmed=common_scale)), primitive)
