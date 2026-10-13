"""不读取论文参考答案的分辨率候选和累计谱独立核验。"""
from __future__ import annotations
import numpy as np
from digitize import LinearAxis, chromatic_mask, spectral_integrals


def monotone_projection(values: list[float]) -> list[float]:
    """等权 PAVA；只生成物理单调候选，不覆盖原图观测。"""
    if not values or not np.isfinite(values).all():
        raise ValueError("累计曲线需要有限数值")
    blocks: list[list[float]] = []
    for i, value in enumerate(values):
        blocks.append([float(value), 1, i, i + 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            right, left = blocks.pop(), blocks.pop()
            count = left[1] + right[1]
            blocks.append([(left[0] * left[1] + right[0] * right[1]) / count,
                           count, left[2], right[3]])
    out = [0.0] * len(values)
    for value, _, start, end in blocks:
        out[int(start):int(end)] = [value] * (int(end) - int(start))
    return out


def cumulative_moments(frequency: list[float], cumulative: list[float | None]) -> dict:
    """按累计 λ 的正频区间增量估算对数矩；不补入未知零频质量。"""
    f = np.asarray(frequency, dtype=float)
    if len(f) != len(cumulative) or not np.isfinite(f).all() or np.any(np.diff(f) <= 0):
        raise ValueError("累计曲线频率无效")
    if any(v is None or not np.isfinite(v) or v < 0 for v in cumulative):
        raise ValueError("累计曲线有缺失或无效值")
    positive = f > 0
    f = f[positive]
    v = np.asarray(cumulative, dtype=float)[positive]
    if len(f) < 2:
        raise ValueError("累计曲线缺少正频率区间")
    mono = np.asarray(monotone_projection(v.tolist()))
    increments = np.diff(mono)
    span = float(mono[-1] - mono[0])
    if span <= 0:
        raise ValueError("累计曲线没有可辨认的正增量")
    # 分段线性 λ 的 Stieltjes 积分；积分中的 ln(ν) 在每段精确平均。
    log_average = np.diff(f * np.log(f) - f) / np.diff(f)
    log_frequency = float(np.exp(np.sum(increments * log_average) / span))
    return dict(status="diagnostic_only", resolved_lambda_span=span,
                cumulative_endpoint=float(mono[-1]), lower_endpoint=float(mono[0]),
                omega_log_k=log_frequency * 47.99243073366221,
                frequency_log_thz=log_frequency,
                frequency_interval_thz=[float(f[0]), float(f[-1])],
                omitted_low_frequency_interval_thz=[0.0, float(f[0])],
                negative_steps_before_projection=int(np.sum(np.diff(v) < 0)),
                max_monotone_adjustment=float(np.max(np.abs(mono - v))),
                monotone_frequency_thz=f.tolist(), monotone_cumulative=mono.tolist(),
                assumption="累计谱应单调；仅核验首个可读正频点到末点之间的增量，不假定零频缺失质量")


def zero_baseline_candidate(rgb: np.ndarray, curve: dict, spec: dict) -> dict:
    """只在人工指定、图像验证为窄近轴线的零参考带内估计可辨幅值。"""
    band = spec.get("zero_reference_band_thz")
    if band is None:
        return dict(status="unavailable", reason="未提供独立图像零参考带", accepted=False)
    if len(band) != 2 or not np.isfinite(band).all() or not 0 < band[0] < band[1]:
        raise ValueError("零参考带无效")
    axis = LinearAxis(**{k: curve["axis_calibration"]["amplitude"][k]
                       for k in ("slope", "intercept")},
                      residual=curve["axis_calibration"]["amplitude"]["max_tick_residual"])
    if axis.slope <= 0:
        return dict(status="unavailable", reason="当前零参考候选仅支持幅值像素递增方向", accepted=False)
    mask = chromatic_mask(rgb, spec["color"])
    x0, y0, x1, y1 = spec["roi"]
    allowed = np.zeros(mask.shape, dtype=bool)
    allowed[y0:y1 + 1, x0:x1 + 1] = True
    for a, b, c, d in spec.get("exclude", []):
        allowed[b:d + 1, a:c + 1] = False
    mask &= allowed
    samples = []
    observed_rows = 0
    for point in curve["points"]:
        if not band[0] <= point["frequency_thz"] <= band[1]:
            continue
        pos = round(point["frequency_pixel"])
        pixels = np.flatnonzero(mask[pos]) if curve["frequency_direction"] == "y" else np.flatnonzero(mask[:, pos])
        if len(pixels):
            samples.extend(pixels.tolist())
            observed_rows += 1
    if observed_rows < 5:
        return dict(status="unavailable", reason="零参考带不足五个有色采样行", accepted=False)
    low, high = min(samples), max(samples)
    zero_pixel = axis.pixel(0)
    if high - low > 3 or low < zero_pixel - 1 or high > zero_pixel + 3:
        return dict(status="unavailable", reason="参考带不是贴近零轴的窄线，拒绝自动消零", accepted=False)
    amplitude_limit = max(0.0, axis.value(high))
    values, flags, count = [], [], 0
    for p in curve["points"]:
        value = p["reconstructed_amplitude"]
        unresolved = value is not None and (
            (p["pixel_high"] is not None and p["pixel_high"] <= high) or
            (p["pixel_high"] is None and value <= amplitude_limit))
        values.append(0.0 if unresolved else value)
        flags.append("within_zero_footprint" if unresolved else "retained")
        count += unresolved and value > 0
    f = [p["frequency_thz"] for p in curve["points"]]
    if any(v is None for v in values):
        return dict(status="unavailable", reason="仍有缺口，不能完成零基线候选核验", accepted=False)
    return dict(status="conditional_candidate", accepted=False,
                reference_band_thz=band, reference_pixel_range=[low, high],
                reference_observed_rows=observed_rows, unresolved_amplitude_interval=[0, amplitude_limit],
                affected_nonzero_points=int(count), frequency_thz=f, amplitude=values, point_reasons=flags,
                integral=spectral_integrals(f, values),
                raw_minus_candidate_lambda=None,
                assumption="把与图像零参考线不可区分的幅值按零处理，仅为候选；原始像素值保留，不宣称这些点精确等于零")
