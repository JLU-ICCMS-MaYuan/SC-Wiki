"""独立科学审阅计算与结果绑定；计算本身不授予科学采纳。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.integrate import quad


def dataset_fingerprint(data: dict) -> str:
    payload = {k: data[k] for k in ("case_id", "source", "calibration_manifest", "material_states")}
    payload["algorithm_version"] = data["provenance"]["algorithm_version"]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def verify_review(review: dict, data: dict) -> dict:
    if review.get("dataset_fingerprint") != dataset_fingerprint(data):
        raise ValueError("科学复核绑定的数据已变化，必须重新复核")
    if review.get("status") != "completed_with_restrictions" or review.get("quantitative_ml_approved") is not False:
        raise ValueError("此 demo 只接受明确保留定量限制的复核记录")
    return review


def independent_integral(f: np.ndarray, a: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    """使用独立自适应求积，而非生产积分函数；误差只表示数值求积误差。"""
    if lo < f[0] or hi > f[-1] or hi <= lo:
        raise ValueError("核验积分范围无效")
    if lo == 0 and a[0] != 0:
        raise ValueError("零频非零谱权重导致发散")
    knots = f[(f > lo) & (f < hi)]
    def integrand(x):
        if x == 0:
            return 2 * (a[1] - a[0]) / (f[1] - f[0])
        return 2 * np.interp(x, f, a) / x
    value, error = quad(integrand, lo, hi, points=knots, limit=len(knots) + 50,
                        epsabs=1e-10, epsrel=1e-10)
    return float(value), float(error)


def audit_dataset(data: dict) -> dict:
    report = dict(dataset_fingerprint=dataset_fingerprint(data),
                  method="independent_adaptive_quadrature_and_frequency_bin_consistency",
                  grants_scientific_acceptance=False, states=[])
    for s in data["material_states"]:
        curve = next(c for c in s["curves"] if c["kind"] == "alpha2f")
        f = np.array([p["frequency_thz"] for p in curve["points"]])
        a = np.array(s["precision"]["zero_baseline_candidate"]["amplitude"])
        c = s["precision"]["cumulative_moment"]
        cf, cv = np.array(c["monotone_frequency_thz"]), np.array(c["monotone_cumulative"])
        lo, hi = max(float(f[0]), float(cf[0])), min(float(f[-1]), float(cf[-1]))
        if any(p["reconstructed_amplitude"] is None for p in curve["points"]):
            raise ValueError("该审阅计算要求先明确处理曲线缺失")
        # 预先固定 5 THz 频段，不根据正文参考值挑选分段。
        edges = np.r_[lo, np.arange(5, hi, 5), hi]
        bins = []
        for left, right in zip(edges[:-1], edges[1:]):
            value, error = independent_integral(f, a, float(left), float(right))
            cumulative_delta = float(np.interp(right, cf, cv) - np.interp(left, cf, cv))
            bins.append(dict(frequency_thz=[float(left), float(right)],
                             lambda_from_alpha=value, lambda_from_cumulative=cumulative_delta,
                             difference=value - cumulative_delta, numerical_quadrature_error=error))
        pixel = abs(curve["axis_calibration"]["amplitude"]["slope"])
        sensitivity = []
        for shift in (-1, 0, 1):
            shifted = np.where(a > 0, np.maximum(0, a + shift * pixel), 0)
            value, error = independent_integral(f, shifted, float(f[0]), float(f[-1]))
            sensitivity.append(dict(amplitude_shift_px=shift, lambda_integral=value,
                                    numerical_quadrature_error=error))
        value, error = independent_integral(f, a, float(f[0]), float(f[-1]))
        low = s["precision"]["zero_baseline_candidate"]["unresolved_amplitude_interval"]
        endpoint = s["diagnostics"]["cumulative_lambda_endpoint"]
        ccurve = next(x for x in s["curves"] if x["kind"] == "cumulative_lambda")
        cpx = abs(ccurve["axis_calibration"]["amplitude"]["slope"])
        report["states"].append(dict(
            id=s["id"], primitive_atoms=s["structure"]["primitive_atoms"],
            independent_lambda=value, production_lambda=s["precision"]["zero_baseline_candidate"]["integral"]["lambda_integral"],
            quadrature_difference=value - s["precision"]["zero_baseline_candidate"]["integral"]["lambda_integral"],
            zero_frequency_first_interval_lambda=s["diagnostics"]["zero_interval_lambda"],
            bins=bins,
            binned_absolute_discrepancy_fraction=sum(abs(b["difference"]) for b in bins) / c["resolved_lambda_span"],
            largest_absolute_discrepancy_bin=max(bins, key=lambda b: abs(b["difference"])),
            one_pixel_amplitude_sensitivity=sensitivity,
            sensitivity_is_confidence_interval=False,
            unresolved_amplitude_interval=low,
            cumulative_endpoint=endpoint, cumulative_endpoint_one_pixel_interval=[endpoint - cpx, endpoint + cpx],
            clipped_frequencies_thz=curve["clipped_frequencies_thz"],
            projection_mode_check=s["precision"]["projection_mode_check"],
            cumulative_omega_log_k=c["omega_log_k"],
            alpha_omega_log_k=s["precision"]["zero_baseline_candidate"]["integral"]["omega_log_k"]))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    data = json.loads(args.input.read_text())
    report = audit_dataset(data)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
