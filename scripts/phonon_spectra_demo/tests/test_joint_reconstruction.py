"""联合重建与虚线空隙的观测范围验证。"""
import copy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from joint_reconstruction import cumulative_operator, reconstruct_joint, increment_envelope
from scientific_review import independent_integral


class JointTests(unittest.TestCase):
    def test_operator_matches_independent_quadrature_on_uneven_grid(self):
        f = np.array([0., .1, .35, 1., 2.])
        a = np.array([0., .2, .6, .1, 0.])
        values = cumulative_operator(f) @ a
        for i in range(1, len(f)):
            expected, _ = independent_integral(f, a, 0., f[i])
            self.assertAlmostEqual(values[i], expected, places=12)

    def test_invalid_operator_grids_are_rejected(self):
        for f in ([1., 2., 3.], [0., 1., 1.], [0., 1., np.nan]):
            with self.assertRaises(ValueError):
                cumulative_operator(np.array(f))

    def curve(self):
        return dict(axis_calibration=dict(amplitude=dict(slope=.01, intercept=0.)), points=[
            dict(frequency_thz=f, observed_amplitude=v, pixel_low=p, pixel_high=p)
            for f, v, p in [(20., .5, 50.), (24., .7, 70.),
                            (25., None, 99.), (26., .8, 80.)]])

    def test_dash_gap_uses_observed_range_not_interpolated_value(self):
        result = increment_envelope(self.curve(), 20., 25.)
        self.assertAlmostEqual(result["lower"], .19)
        self.assertAlmostEqual(result["upper"], .31)
        self.assertFalse(result["upper_boundary"]["boundary_is_direct_observation"])
        self.assertEqual(result["upper_boundary"]["adjacent_observed_frequency_thz"], [24., 26.])
        self.assertTrue(result["lower"] <= .299 <= result["upper"])
        self.assertFalse(result["lower"] <= .4 <= result["upper"])

    def test_edge_extension_is_not_an_observation(self):
        with self.assertRaisesRegex(ValueError, "真实"):
            increment_envelope(self.curve(), 20., 27.)

    def fixture(self):
        f = np.linspace(0, 10, 101)
        a = .1 * f * (1 - f / 10)
        cumulative = cumulative_operator(f) @ a
        def point(i, value):
            return dict(frequency_thz=float(f[i]), observed_amplitude=float(value),
                        pixel_low=float(value / .01 - .5), pixel_high=float(value / .01 + .5))
        alpha = dict(axis_calibration=dict(amplitude=dict(slope=.01, intercept=0.)),
                     points=[point(i, v) for i, v in enumerate(a)], clipped_frequencies_thz=[])
        curve = copy.deepcopy(alpha)
        curve["points"] = [point(i, v + .002 * np.sin(i)) for i, v in enumerate(cumulative)]
        for i, p in enumerate(curve["points"]):
            if i % 4 == 0:
                p["observed_amplitude"] = None  # 模拟虚线空隙
        return alpha, curve, dict(amplitude=a.tolist()), a

    def test_synthetic_reconstruction_predicts_held_out_observations(self):
        alpha, curve, baseline, truth = self.fixture()
        before = copy.deepcopy((alpha, curve, baseline))
        result = reconstruct_joint(alpha, curve, baseline)
        self.assertEqual(before, (alpha, curve, baseline))
        self.assertFalse(result["uses_paper_reference"])
        self.assertGreater(result["held_out_nodes"], 5)
        self.assertLess(result["held_out_rmse_px"], .25)
        self.assertLess(np.max(np.abs(np.array(result["alpha2f"]) - truth)), .01)
        np.testing.assert_allclose(cumulative_operator(np.array(result["frequency_thz"])) @ result["alpha2f"],
                                   result["cumulative_lambda"], atol=1e-12)
        self.assertTrue(result["consistency_is_constraint_not_independent_accuracy"])

    def test_reference_answers_do_not_change_joint_reconstruction(self):
        alpha, curve, baseline, _ = self.fixture()
        expected = reconstruct_joint(alpha, curve, baseline)
        alpha["reference"] = dict(lambda_reported=98765, omega_log_k=-999)
        curve["reference"] = dict(lambda_reported=0)
        self.assertEqual(expected, reconstruct_joint(alpha, curve, baseline))


if __name__ == "__main__":
    unittest.main()
