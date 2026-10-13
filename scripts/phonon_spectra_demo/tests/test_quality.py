"""零基线候选与累计谱矩的独立真值测试。"""
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitize import LinearAxis, extract_curve, spectral_integrals
from quality import zero_baseline_candidate, monotone_projection, cumulative_moments


class PrecisionTests(unittest.TestCase):
    def fixture(self):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        image[:, 20] = 0
        image[:, 21:23] = [0, 100, 0]  # 被黑轴遮住后可见的零线
        image[30:51, 21:23] = 255
        image[30:51, 40:42] = [0, 128, 0]  # 已知非零平台，不应被消除
        spec = dict(id="alpha", kind="alpha2f", projection=None, color="green", unit="plot",
                    roi=[20, 0, 99, 99], amplitude_ticks=[[20, 0], [21, 1]],
                    frequency_direction="y", zero_reference_band_thz=[80, 90])
        curve = extract_curve(image, spec, LinearAxis.fit([[0, 0], [99, 99]]))
        return image, spec, curve

    def test_zero_footprint_candidate_preserves_raw_and_resolved_peak(self):
        image, spec, curve = self.fixture()
        raw = [p["observed_amplitude"] for p in curve["points"]]
        candidate = zero_baseline_candidate(image, curve, spec)
        self.assertEqual(candidate["status"], "conditional_candidate")
        self.assertFalse(candidate["accepted"])
        self.assertEqual(candidate["reference_pixel_range"], [21, 22])
        self.assertEqual(raw, [p["observed_amplitude"] for p in curve["points"]])
        self.assertEqual(candidate["amplitude"][20], 0)
        self.assertAlmostEqual(candidate["amplitude"][40], 20.5)
        self.assertEqual(candidate["point_reasons"][20], "within_zero_footprint")
        self.assertEqual(candidate["point_reasons"][40], "retained")
        f = [p["frequency_thz"] for p in curve["points"]]
        truth = [20.5 if 30 <= round(p["frequency_pixel"]) <= 50 else 0 for p in curve["points"]]
        expected = spectral_integrals(f, truth)
        self.assertAlmostEqual(candidate["integral"]["lambda_integral"], expected["lambda_integral"])

    def test_nonzero_reference_band_cannot_silently_zero_a_peak(self):
        image, spec, curve = self.fixture()
        spec["zero_reference_band_thz"] = [35, 45]
        candidate = zero_baseline_candidate(image, curve, spec)
        self.assertEqual(candidate["status"], "unavailable")
        self.assertNotIn("amplitude", candidate)

    def test_no_color_or_unconfigured_reference_is_unavailable(self):
        image, spec, curve = self.fixture()
        white = np.full_like(image, 255)
        self.assertEqual(zero_baseline_candidate(white, curve, spec)["status"], "unavailable")
        del spec["zero_reference_band_thz"]
        self.assertEqual(zero_baseline_candidate(image, curve, spec)["status"], "unavailable")

    def test_reference_scalar_does_not_enter_candidate_calculation(self):
        image, spec, curve = self.fixture()
        a = zero_baseline_candidate(image, curve, spec)
        spec["reference_lambda"] = 98765
        spec["reference_omega_log"] = -123
        self.assertEqual(a, zero_baseline_candidate(image, curve, spec))

    def test_pava_is_monotone_and_leaves_monotone_data_unchanged(self):
        self.assertEqual(monotone_projection([0, 2, 1, 3]), [0, 1.5, 1.5, 3])
        self.assertEqual(monotone_projection([0, 1, 1, 2]), [0, 1, 1, 2])

    def test_cumulative_moment_against_analytic_integral(self):
        f = np.linspace(1, math.e, 1000)
        # dλ=dν，因此对数频率 exp(∫lnν dν / ∫dν)=exp(1/(e−1))。
        result = cumulative_moments(f.tolist(), (f - 1).tolist())
        self.assertAlmostEqual(result["resolved_lambda_span"], math.e - 1)
        self.assertAlmostEqual(result["frequency_log_thz"], math.exp(1 / (math.e - 1)), places=10)
        self.assertEqual(result["omitted_low_frequency_interval_thz"], [0., 1.])
        self.assertEqual(result["max_monotone_adjustment"], 0)

    def test_cumulative_missing_or_flat_cannot_be_accepted(self):
        for values in ([0, None, 1], [1, 1, 1], [1, 2, math.nan]):
            with self.assertRaises(ValueError):
                cumulative_moments([1, 2, 3], values)


if __name__ == "__main__":
    unittest.main()
