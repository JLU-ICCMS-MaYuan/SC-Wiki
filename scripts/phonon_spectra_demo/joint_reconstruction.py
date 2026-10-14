"""以原图像素约束联合重建 α²F 和累计 λ；不接收论文标量答案。"""
from __future__ import annotations
import numpy as np
from scipy.optimize import lsq_linear


def cumulative_operator(frequency: np.ndarray) -> np.ndarray:
    f = np.asarray(frequency, dtype=float)
    if len(f) < 3 or f[0] != 0 or not np.isfinite(f).all() or np.any(np.diff(f) <= 0):
        raise ValueError("联合重建要求从零开始的有限递增频率网格")
    matrix = np.zeros((len(f), len(f)))
    for i in range(1, len(f)):
        matrix[i] = matrix[i - 1]
        left, right = f[i - 1:i + 1]
        width = right - left
        if left == 0:
            matrix[i, i] += 2
        else:
            ratio = np.log1p(width / left)
            matrix[i, i - 1] += 2 * (-1 + right / width * ratio)
            matrix[i, i] += 2 * (1 - left / width * ratio)
    return matrix


def reconstruct_joint(alpha: dict, cumulative: dict, baseline: dict) -> dict:
    f = np.array([p["frequency_thz"] for p in alpha["points"]])
    prior = np.array(baseline["amplitude"], dtype=float)
    if not np.isfinite(prior).all():
        raise ValueError("联合重建不能静默填补未知谱")
    operator = cumulative_operator(f)
    pixel = abs(alpha["axis_calibration"]["amplitude"]["slope"])
    cpixel = abs(cumulative["axis_calibration"]["amplitude"]["slope"])
    axis = alpha["axis_calibration"]["amplitude"]
    if axis["slope"] <= 0 or cumulative["axis_calibration"]["amplitude"]["slope"] <= 0:
        raise ValueError("当前联合重建要求幅值像素轴正向；反向轴须先转换")
    lower, upper, tolerance = [], [], []
    for point, value in zip(alpha["points"], prior):
        if point["pixel_low"] is None:
            low, high = 0., max(4 * pixel, value + 4 * pixel)
        else:
            low = max(0., (point["pixel_low"] - .5) * axis["slope"] + axis["intercept"])
            high = (point["pixel_high"] + .5) * axis["slope"] + axis["intercept"]
        if value == 0:
            low = 0.
        lower.append(low)
        upper.append(max(high, low + .01 * pixel))
        tolerance.append(max(pixel, (high - low) / 2))
    lower, upper, tolerance = map(np.asarray, (lower, upper, tolerance))
    variables = np.arange(1, len(f) - 1)  # 继承有标记的零频/高频边界假设
    points = [p for p in cumulative["points"] if p["observed_amplitude"] is not None]
    obs_f = np.array([p["frequency_thz"] for p in points])
    obs = np.array([p["observed_amplitude"] for p in points])
    matrix = np.column_stack([np.interp(obs_f, f, operator[:, j]) for j in variables])
    ctolerance = np.array([max(cpixel, (p["pixel_high"] - p["pixel_low"] + 1) * cpixel / 2)
                           for p in points])

    def fit(included):
        weights = ctolerance[included]
        a = np.vstack([
            np.c_[np.diag(1 / tolerance[variables]), np.zeros(len(variables))],
            np.c_[matrix[included] / weights[:, None], 1 / weights],
            np.r_[np.zeros(len(variables)), 1 / cpixel][None, :],
        ])
        b = np.r_[prior[variables] / tolerance[variables], obs[included] / weights, 0.]
        solution = lsq_linear(a, b,
                             bounds=(np.r_[lower[variables], -cpixel],
                                     np.r_[upper[variables], cpixel]),
                             lsq_solver="lsmr", lsmr_tol=1e-8, tol=1e-8, max_iter=100)
        if not solution.success:
            raise ValueError("联合重建未收敛")
        spectrum = np.r_[0., solution.x[:-1], 0.]
        residual = (matrix @ solution.x[:-1] + solution.x[-1] - obs) / cpixel
        return spectrum, float(solution.x[-1]), residual

    all_nodes = np.ones(len(points), dtype=bool)
    held_out = np.arange(len(points)) % 5 == 2
    if held_out.sum() < 5:
        raise ValueError("真实累计谱点不足以留出验证")
    _, _, validation_residual = fit(~held_out)
    spectrum, offset, residual = fit(all_nodes)
    return dict(status="physics_constrained_candidate", frequency_thz=f.tolist(),
                alpha2f=spectrum.tolist(), cumulative_lambda=(operator @ spectrum).tolist(),
                alpha_lower_bound=lower.tolist(), alpha_upper_bound=upper.tolist(),
                cumulative_zero_offset=offset,
                observed_nodes=len(points), held_out_nodes=int(held_out.sum()),
                held_out_rmse_px=float(np.sqrt(np.mean(validation_residual[held_out] ** 2))),
                held_out_max_abs_px=float(np.max(np.abs(validation_residual[held_out]))),
                full_fit_rmse_px=float(np.sqrt(np.mean(residual ** 2))),
                clipped_frequency_mask=alpha["clipped_frequencies_thz"],
                uses_paper_reference=False,
                held_out_fraction=0.2,
                consistency_is_constraint_not_independent_accuracy=True,
                assumptions=["像素包络限定可见曲线幅值", "累计 λ 的零轴偏移限于一个像素",
                             "零频/高频端继承已有边界假设", "边界遮挡区只提供重建候选，不声称恢复唯一峰顶"],
                validation="每五个真实累计谱点留出一个；其余点与绿色原图支持范围用于重建")


def observed_value_envelope(curve: dict, frequency: float) -> dict:
    points = sorted((p for p in curve["points"] if p["observed_amplitude"] is not None),
                    key=lambda p: p["frequency_thz"])
    left = [p for p in points if p["frequency_thz"] <= frequency]
    right = [p for p in points if p["frequency_thz"] >= frequency]
    if not left or not right:
        raise ValueError("频段边界超出真实累计谱观测")
    p, q = left[-1], right[0]
    axis = curve["axis_calibration"]["amplitude"]
    lo = min(p["pixel_low"], q["pixel_low"]) - .5
    hi = max(p["pixel_high"], q["pixel_high"]) + .5
    values = [lo * axis["slope"] + axis["intercept"], hi * axis["slope"] + axis["intercept"]]
    return dict(lower=max(0., min(values)), upper=max(0., max(values)),
                adjacent_observed_frequency_thz=[p["frequency_thz"], q["frequency_thz"]],
                boundary_is_direct_observation=abs(p["frequency_thz"] - frequency) < 1e-9,
                basis="真实有色像素包络加半像素；空隙仅使用累计谱单调约束，不作为精确插值值")


def increment_envelope(curve: dict, lo: float, hi: float) -> dict:
    left, right = observed_value_envelope(curve, lo), observed_value_envelope(curve, hi)
    return dict(lower=max(0., right["lower"] - left["upper"]),
                upper=max(0., right["upper"] - left["lower"]),
                lower_boundary=left, upper_boundary=right,
                is_statistical_confidence_interval=False)
