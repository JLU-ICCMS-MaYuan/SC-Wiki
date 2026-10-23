"""谱图半自动数字化的数学与轨迹提取；不读取论文参考答案。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np

_trapezoid = np.trapezoid if hasattr(np, "trapezoid") else np.trapz


@dataclass(frozen=True)
class LinearAxis:
    slope: float
    intercept: float
    residual: float

    @classmethod
    def fit(cls, ticks: list[list[float]], scale: str = "linear") -> "LinearAxis":
        if scale != "linear":
            raise ValueError("当前谱提取仅支持线性坐标")
        a = np.asarray(ticks, dtype=float)
        if a.ndim != 2 or a.shape[1] != 2 or len(a) < 2 or not np.isfinite(a).all():
            raise ValueError("至少需要两个有限的坐标标定点")
        if len(np.unique(a[:, 0])) != len(a) or np.ptp(a[:, 1]) == 0:
            raise ValueError("坐标标定退化或像素位置重复")
        slope, intercept = np.polyfit(a[:, 0], a[:, 1], 1)
        if abs(slope) < 1e-12:
            raise ValueError("坐标斜率为零")
        return cls(float(slope), float(intercept),
                   float(np.max(np.abs(a[:, 1] - (slope * a[:, 0] + intercept)))))

    def value(self, pixel: float) -> float:
        return self.slope * pixel + self.intercept

    def pixel(self, value: float) -> float:
        return (value - self.intercept) / self.slope

    def as_dict(self) -> dict:
        return dict(slope=self.slope, intercept=self.intercept,
                    max_tick_residual=self.residual)


def color_mask(rgb: np.ndarray, color: str) -> np.ndarray:
    r, g, b = np.asarray(rgb, dtype=float).transpose(2, 0, 1)
    masks = {
        "blue": (b > 120) & (b > 1.4 * r) & (b > 1.4 * g),
        "red": (r > 150) & (g < .55 * r) & (b < .55 * r),
        "green": (g > 45) & (g > 1.35 * r) & (g > 1.35 * b),
        "magenta": (r > 150) & (b > 50) & (g < .55 * r) & (b > .2 * r),
        "olive": (r > 45) & (g > 45) & (b < .5 * np.minimum(r, g)) &
                 (r < 1.5 * g) & (g < 1.5 * r),
    }
    if color not in masks:
        raise ValueError(f"未知颜色：{color}")
    return masks[color]


def chromatic_mask(rgb: np.ndarray, color: str) -> np.ndarray:
    """补读与黑色坐标轴混合的暗色像素；无色灰线不能成为曲线证据。"""
    r, g, b = np.asarray(rgb, dtype=float).transpose(2, 0, 1)
    masks = {
        "red": (r > 35) & (r > g + 15) & (r > b + 15),
        "blue": (b > 35) & (b > r + 15) & (b > g + 15),
        "green": (g > 25) & (g > r + 12) & (g > b + 12),
        "magenta": (r > 40) & (r > g + 20) & (b > g + 12) & (b > .2 * r),
        "olive": (np.minimum(r, g) > 25) & (np.minimum(r, g) > b + 15) &
                 (np.abs(r - g) < .35 * np.maximum(r, g)),
    }
    if color not in masks:
        raise ValueError(f"未知颜色：{color}")
    return masks[color]


def continue_frame_plateau(rows: list[dict], *, max_pixels: int, tolerance: float) -> None:
    """累计曲线在图框处仅缺少至多两个像素且邻域已稳定时，延续端值。"""
    observed = [i for i, p in enumerate(rows) if p["observed_amplitude"] is not None]
    if len(observed) < 5:
        return
    for at_start in (True, False):
        edge = observed[0] if at_start else observed[-1]
        missing = list(range(edge)) if at_start else list(range(edge + 1, len(rows)))
        if not missing or len(missing) > max_pixels:
            continue
        nearby = observed[:5] if at_start else observed[-5:]
        positions = [rows[i]["frequency_pixel"] for i in nearby]
        amplitudes = [rows[i]["observed_amplitude"] for i in nearby]
        if max(positions) - min(positions) > 12 or max(amplitudes) - min(amplitudes) > tolerance:
            continue
        for i in missing:
            if rows[i]["status"] == "missing":
                rows[i]["reconstructed_amplitude"] = rows[edge]["observed_amplitude"]
                rows[i]["status"] = "edge_continuation"


def reconstruct(values: list[float | None], *, max_gap: int,
                baseline_tolerance: float, max_baseline_gap: int) -> tuple[list, list]:
    """只填有界内部缺口；低值长缺口也明确记为推断，尾部不外推。"""
    out = list(values)
    flags = ["observed" if v is not None else "missing" for v in values]
    observed = [i for i, v in enumerate(values) if v is not None]
    for left, right in zip(observed, observed[1:]):
        gap = right - left - 1
        if gap == 0:
            continue
        if gap <= max_gap:
            flag = "interpolated"
        elif gap <= max_baseline_gap and max(values[left], values[right]) <= baseline_tolerance:
            flag = "baseline_inferred"
        else:
            continue
        for j in range(left + 1, right):
            out[j] = float(values[left] + (values[right] - values[left]) * (j - left) / (right - left))
            flags[j] = flag
    return out, flags


def extract_curve(rgb: np.ndarray, spec: dict, frequency_axis: LinearAxis) -> dict:
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = spec["roi"]
    if not (0 <= x0 < x1 < w and 0 <= y0 < y1 < h):
        raise ValueError("曲线区域超出原图")
    orientation = spec.get("frequency_direction", "y")
    if orientation not in ("x", "y"):
        raise ValueError("频率方向必须为 x 或 y")
    amplitude_axis = LinearAxis.fit(spec["amplitude_ticks"], spec.get("scale", "linear"))
    mask = color_mask(rgb, spec["color"])
    recovered_mask = chromatic_mask(rgb, spec["color"])
    allowed = np.zeros(mask.shape, dtype=bool)
    allowed[y0:y1 + 1, x0:x1 + 1] = True
    for box in spec.get("exclude", []):
        a, b, c, d = box
        if not (0 <= a <= c < w and 0 <= b <= d < h):
            raise ValueError("图例排除区域非法")
        allowed[b:d + 1, a:c + 1] = False
    mask &= allowed
    recovered_mask &= allowed
    pixels = list(range(y0, y1 + 1) if orientation == "y" else range(x0, x1 + 1))
    zero_pixel = spec.get("zero_frequency_pixel")
    if zero_pixel is not None and zero_pixel not in pixels:
        pixels.append(zero_pixel)
    rows: list[dict[str, Any]] = []
    clipped = []
    for pos in pixels:
        fractional = int(pos) != pos
        if fractional:
            lo, hi = int(np.floor(pos)), int(np.ceil(pos))
            weight = pos - lo
            strip = ((1 - weight) * rgb[lo:lo+1] + weight * rgb[hi:hi+1] if orientation == "y" else
                     (1 - weight) * rgb[:, lo:lo+1] + weight * rgb[:, hi:hi+1])
            permitted = (allowed[lo] & allowed[hi] if orientation == "y" else allowed[:, lo] & allowed[:, hi])
            direct = color_mask(strip, spec["color"]).reshape(-1) & permitted
            recovered = chromatic_mask(strip, spec["color"]).reshape(-1) & permitted
        else:
            pos = int(pos)
            direct = mask[pos, :] if orientation == "y" else mask[:, pos]
            recovered = recovered_mask[pos, :] if orientation == "y" else recovered_mask[:, pos]
        coords = np.flatnonzero(direct)
        detection_mode = "strict_color" if len(coords) else None
        if not len(coords):
            coords = np.flatnonzero(recovered)
            if len(coords):
                detection_mode = "chromatic_recovery"
        if fractional and len(coords):
            detection_mode = "subpixel_color"
        freq = 0.0 if zero_pixel is not None and pos == zero_pixel else frequency_axis.value(pos)
        if freq < 0:
            continue
        lo = hi = center = value = None
        if len(coords):
            center = float(coords.mean())
            lo, hi = float(coords.min()), float(coords.max())
            raw_value = amplitude_axis.value(center)
            # 仅消除浮点运算舍入误差，不把贴轴的可辨幅值当作物理零。
            roundoff = 8 * np.finfo(float).eps * (abs(amplitude_axis.slope * center) + abs(amplitude_axis.intercept))
            value = 0.0 if abs(raw_value) <= roundoff else max(0.0, raw_value)
            # 标定方向反向也成立，裁切按实际 ROI 两侧检查。
            bounds = (x0, x1) if orientation == "y" else (y0, y1)
            nonzero_edge = bounds[1] if amplitude_axis.slope > 0 else bounds[0]
            if np.any(np.abs(coords - nonzero_edge) <= 2):
                clipped.append(float(freq))
        rows.append(dict(frequency_thz=float(freq), frequency_pixel=float(pos),
                         amplitude_pixel=center, pixel_low=lo, pixel_high=hi,
                         observed_amplitude=value, detection_mode=detection_mode))
    rows.sort(key=lambda p: p["frequency_thz"])
    if not any(p["observed_amplitude"] is not None for p in rows):
        raise ValueError(f"没有找到曲线颜色：{spec['id']}")
    tolerance = spec.get("baseline_tolerance_px", 4) * abs(amplitude_axis.slope)
    values = [p["observed_amplitude"] for p in rows]
    filled, flags = reconstruct(values, max_gap=spec.get("max_gap_px", 12),
                                baseline_tolerance=tolerance,
                                max_baseline_gap=spec.get("max_baseline_gap_px", 90))
    # 边界零值仅在案例明确声明且最近实测值接近基线时用于候选重建。
    boundary_records = []
    for side, freq in (("low", spec.get("zero_boundaries_thz", [None, None])[0]),
                       ("high", spec.get("zero_boundaries_thz", [None, None])[1])):
        if freq is None:
            continue
        obs = [i for i, v in enumerate(values) if v is not None]
        edge = obs[0] if side == "low" else obs[-1]
        if values[edge] > tolerance or abs(rows[edge]["frequency_pixel"] - frequency_axis.pixel(freq)) > spec.get("max_baseline_gap_px", 90):
            continue
        indices = range(edge) if side == "low" else range(edge + 1, len(rows))
        for i in indices:
            f0, f1 = freq, rows[edge]["frequency_thz"]
            filled[i] = max(0.0, values[edge] * (rows[i]["frequency_thz"] - f0) / (f1 - f0))
            flags[i] = "baseline_inferred"
        boundary_records.append(dict(frequency_thz=float(freq),
                                     frequency_pixel=float(frequency_axis.pixel(freq)),
                                     amplitude_pixel=None, pixel_low=None, pixel_high=None,
                                     observed_amplitude=None, reconstructed_amplitude=0.0,
                                     status="boundary_assumption", detection_mode=None))
    for p, val, flag in zip(rows, filled, flags):
        p["reconstructed_amplitude"] = val
        p["status"] = flag
    if spec["kind"] == "cumulative_lambda":
        continue_frame_plateau(rows, max_pixels=2, tolerance=1.5 * abs(amplitude_axis.slope))
    for boundary in boundary_records:
        # 不用假设覆盖恰好落在边界的直接观测。
        if all(abs(p["frequency_thz"] - boundary["frequency_thz"]) > 1e-8 for p in rows):
            rows.append(boundary)
    rows.sort(key=lambda p: p["frequency_thz"])
    counts = {s: sum(p["status"] == s for p in rows)
              for s in ("observed", "interpolated", "baseline_inferred", "boundary_assumption",
                        "edge_continuation", "missing")}
    return {**{k: spec[k] for k in ("id", "kind", "projection", "color", "unit", "roi")},
            "frequency_direction": orientation,
            "axis_calibration": {"frequency": frequency_axis.as_dict(), "amplitude": amplitude_axis.as_dict()},
            "points": rows, "point_counts": counts,
            "chromatic_recovered_points": sum(p["detection_mode"] == "chromatic_recovery" for p in rows),
            "clipped_frequencies_thz": clipped,
            "review_status": "needs_review", "training_ready": False}


def integrate_contiguous(x: np.ndarray, y: list) -> tuple[float, bool]:
    """缺口不能跨越积分；返回部分积分和完整性，而非把 NaN 当零。"""
    total = 0.0
    complete = all(v is not None and np.isfinite(v) for v in y)
    for i in range(len(x) - 1):
        a, b = y[i:i + 2]
        if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
            total += (x[i + 1] - x[i]) * (a + b) / 2
    return float(total), complete


def spectral_integrals(frequency: list, amplitude: list, cutoff_thz: float = 0.0) -> dict:
    f = np.asarray(frequency, dtype=float)
    if len(f) < 2 or len(f) != len(amplitude) or not np.isfinite(f).all() or np.any(f < 0) or np.any(np.diff(f) <= 0):
        raise ValueError("频率必须非负、有限、严格递增且与幅值等长，至少两个点")
    if not np.isfinite(cutoff_thz) or cutoff_thz < 0 or cutoff_thz >= f[-1]:
        raise ValueError("积分下限必须非负、有限且小于最高频率")
    if any(v is not None and (not np.isfinite(v) or v < 0) for v in amplitude):
        raise ValueError("谱幅值必须非负或为 null")
    # 对已重建的分段线性 α²F 精确积分；不能用丢弃零频点回避首区间。
    lam = log_moment = zero_interval_lambda = 0.0
    complete = True
    first_integrated = None
    for x, y, a, b in zip(f[:-1], f[1:], amplitude[:-1], amplitude[1:]):
        lo = max(float(x), cutoff_thz)
        hi = float(y)
        if hi <= lo:
            continue
        if a is None or b is None:
            complete = False
            continue
        slope = (b - a) / (y - x)
        intercept = a - slope * x
        if lo == 0:
            if a != 0:
                raise ValueError("零频处 α²F 非零，完整 λ 积分发散；不能静默丢弃该区间")
            segment_lambda = 2 * slope * hi
            segment_moment = 2 * slope * (hi * np.log(hi) - hi)
            zero_interval_lambda += segment_lambda
        else:
            log_ratio = np.log1p((hi - lo) / lo)
            segment_lambda = 2 * (slope * (hi - lo) + intercept * log_ratio)
            segment_moment = (2 * slope * (hi * np.log(hi) - hi - lo * np.log(lo) + lo)
                              + intercept * log_ratio * (np.log(hi) + np.log(lo)))
        lam += float(segment_lambda)
        log_moment += float(segment_moment)
        if first_integrated is None:
            first_integrated = lo
    if first_integrated is None:
        raise ValueError("没有可积分的连续有效区间")
    nu_log = float(np.exp(log_moment / lam)) if lam > 0 else None
    return dict(lambda_integral=lam, frequency_log_thz=nu_log,
                omega_log_k=None if nu_log is None else nu_log * 47.99243073366221,
                positive_frequency_complete=complete,
                minimum_integrated_thz=first_integrated, cutoff_thz=cutoff_thz,
                integration_method="exact_piecewise_linear_alpha2f",
                zero_interval_lambda=zero_interval_lambda)


def normalize_dos(frequency: list, components: dict[str, list], atoms: int,
                  *, assumptions_confirmed: bool = False) -> dict:
    if not isinstance(atoms, int) or isinstance(atoms, bool) or atoms <= 0:
        raise ValueError("原胞原子数必须为正整数")
    f = np.asarray(frequency, dtype=float)
    if not components or not np.isfinite(f).all() or np.any(np.diff(f) <= 0):
        raise ValueError("DOS 频率或分波无效")
    if any(len(v) != len(f) for v in components.values()):
        raise ValueError("分波网格不一致")
    if any(v is not None and (not np.isfinite(v) or v < 0) for c in components.values() for v in c):
        raise ValueError("DOS 幅值无效")
    target = 3 * atoms
    if any(v is None for c in components.values() for v in c):
        return dict(status="incomplete", accepted=False, target_modes=target, scale_factor=None,
                    reason="仍有未重建缺口，未进行 3N 归一化")
    total = np.sum(np.asarray(list(components.values()), dtype=float), axis=0)
    area = float(_trapezoid(total, f))
    if area <= 0:
        raise ValueError("DOS 积分必须为正")
    factor = target / area
    scaled = {k: (np.asarray(v) * factor).tolist() for k, v in components.items()}
    return dict(status="normalized" if assumptions_confirmed else "conditional_candidate",
                accepted=assumptions_confirmed, target_modes=target, scale_factor=factor,
                frequency_thz=f.tolist(), components=scaled,
                total=(total * factor).tolist(),
                component_mode_integrals={k: float(_trapezoid(v, f)) for k, v in scaled.items()},
                total_mode_integral=float(_trapezoid(total * factor, f)),
                unit="modes / THz / primitive cell")
