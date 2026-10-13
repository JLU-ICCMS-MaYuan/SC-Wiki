"""科学审阅的独立求积和数据绑定回归。"""
import copy
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scientific_review import independent_integral, dataset_fingerprint, verify_review
from digitize import spectral_integrals


class ScientificReviewTests(unittest.TestCase):
    def data(self):
        return dict(case_id="test", source={"hash": "source"}, calibration_manifest={"ticks": [0, 1]},
                    material_states=[{"points": [0., 1.]}],
                    provenance={"algorithm_version": "v4", "generated_at": "t1"})

    def test_independent_quadrature_includes_zero_interval(self):
        f = np.array([0., .4, 2.])
        val, err = independent_integral(f, f, 0., 2.)
        self.assertAlmostEqual(val, 4., places=12)
        self.assertAlmostEqual(val, spectral_integrals(f.tolist(), f.tolist())["lambda_integral"], places=12)
        self.assertLess(err, 1e-9)

    def test_constant_spectrum_quadrature(self):
        val, _ = independent_integral(np.array([1., math.e]), np.ones(2), 1., math.e)
        self.assertAlmostEqual(val, 2., places=12)

    def test_timestamp_does_not_invalidate_review_but_data_does(self):
        data = self.data()
        report = dict(dataset_fingerprint=dataset_fingerprint(data),
                      status="completed_with_restrictions", quantitative_ml_approved=False)
        data["provenance"]["generated_at"] = "t2"
        self.assertEqual(verify_review(report, data), report)
        changed = copy.deepcopy(data)
        changed["material_states"][0]["points"][1] = 1.01
        with self.assertRaisesRegex(ValueError, "变化"):
            verify_review(report, changed)

    def test_review_cannot_be_used_to_approve_training(self):
        data = self.data()
        report = dict(dataset_fingerprint=dataset_fingerprint(data),
                      status="completed_with_restrictions", quantitative_ml_approved=True)
        with self.assertRaises(ValueError):
            verify_review(report, data)


if __name__ == "__main__":
    unittest.main()
