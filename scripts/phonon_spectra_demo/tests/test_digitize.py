"""独立数学真值、缺失保护及合成图测试，不以原论文答案校准实现。"""
import csv
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from digitize import LinearAxis, extract_curve, reconstruct, normalize_dos, spectral_integrals
from build_demo import verified_bytes, primitive_structure, csv_text


class AxisTests(unittest.TestCase):
    def test_inverted_axis_and_roundtrip(self):
        axis = LinearAxis.fit([[100, 0], [50, 5], [0, 10]])
        self.assertAlmostEqual(axis.value(25), 7.5)
        self.assertAlmostEqual(axis.pixel(7.5), 25)
        self.assertLess(axis.residual, 1e-10)

    def test_degenerate_and_unsupported_axis(self):
        for ticks in ([[0, 0], [0, 1]], [[0, 1], [2, 1]], [[0, 1], [2, math.inf]]):
            with self.assertRaises(ValueError):
                LinearAxis.fit(ticks)
        with self.assertRaisesRegex(ValueError, "线性"):
            LinearAxis.fit([[0, 1], [2, 2]], "log")


class CurveTests(unittest.TestCase):
    def synthetic(self, transpose=False):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        for y in range(5, 91):
            image[y, 20 + y // 5] = [255, 0, 0]
        spec = dict(id="arbitrary_id", kind="phonon_dos", projection="X", color="red",
                    unit="pixel", roi=[0, 0, 99, 99], amplitude_ticks=[[20, 0], [21, 1]],
                    frequency_direction="x" if transpose else "y")
        return extract_curve(image.transpose(1, 0, 2) if transpose else image, spec,
                             LinearAxis.fit([[0, 0], [99, 99]]))

    def test_horizontal_and_vertical_frequency_agree(self):
        a, b = self.synthetic(), self.synthetic(True)
        self.assertEqual(a["point_counts"], b["point_counts"])
        for p, q in zip(a["points"], b["points"]):
            self.assertEqual(p["observed_amplitude"], q["observed_amplitude"])
        observed = [p for p in a["points"] if p["status"] == "observed"]
        self.assertEqual(len(observed), 86)
        for p in observed:
            self.assertAlmostEqual(p["observed_amplitude"], int(round(p["frequency_pixel"])) // 5)

    def test_unknown_gaps_and_tails_stay_missing(self):
        values = [None, 5., None, 7., None, None, None, None, 9., None]
        out, flags = reconstruct(values, max_gap=1, baseline_tolerance=.2, max_baseline_gap=5)
        self.assertEqual(out[2], 6.)
        self.assertEqual(flags[2], "interpolated")
        self.assertTrue(all(out[i] is None for i in [0, 4, 5, 6, 7, 9]))

    def test_baseline_inference_is_not_observed(self):
        out, flags = reconstruct([.1, None, None, .2], max_gap=1,
                                 baseline_tolerance=.3, max_baseline_gap=3)
        self.assertEqual(flags[1:3], ["baseline_inferred"] * 2)
        self.assertAlmostEqual(out[1], 2 / 15)


class PhysicsTests(unittest.TestCase):
    def test_one_common_normalization_factor(self):
        result = normalize_dos([0, 1, 2], {"X": [3., 3., 3.], "Y": [1., 1., 1.]}, 4)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["total_mode_integral"], 12)
        self.assertEqual(result["component_mode_integrals"], {"X": 9., "Y": 3.})
        self.assertEqual(result["scale_factor"], 1.5)

    def test_missing_dos_blocks_normalization(self):
        result = normalize_dos([0, 1, 2], {"X": [1., None, 1.]}, 4)
        self.assertIsNone(result["scale_factor"])
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["accepted"])

    def test_invalid_atom_counts_and_negative_amplitudes(self):
        for n in (True, 0, -1, 4.5):
            with self.assertRaises(ValueError):
                normalize_dos([0, 1], {"X": [1, 1]}, n)
        with self.assertRaises(ValueError):
            spectral_integrals([1, 2], [1, -1])

    def test_analytic_spectrum_and_thz_to_kelvin(self):
        f = np.linspace(1, math.e, 10001)
        # α²F(ν)=ν；λ=2(e−1)，ln(νlog)=1/(e−1)。
        result = spectral_integrals(f.tolist(), f.tolist())
        self.assertAlmostEqual(result["lambda_integral"], 2 * (math.e - 1), places=8)
        expected = math.exp(1 / (math.e - 1))
        self.assertAlmostEqual(result["frequency_log_thz"], expected, places=7)
        self.assertAlmostEqual(result["omega_log_k"], expected * 47.99243073366221, places=5)

    def test_unknown_gap_is_not_integrated_across(self):
        result = spectral_integrals([1, 2, 3, 4, 5], [1, 2, None, 4, 5])
        self.assertAlmostEqual(result["lambda_integral"], 4.)
        self.assertFalse(result["positive_frequency_complete"])

    def test_zero_frequency_is_not_divided_by_zero(self):
        r = spectral_integrals([0, 1, 2], [0, 1, 2])
        self.assertTrue(math.isfinite(r["lambda_integral"]))
        with self.assertRaises(ValueError):
            spectral_integrals([0, 1], [0, 1])


class EvidenceTests(unittest.TestCase):
    def test_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.pdf"
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "哈希"):
                verified_bytes(path, "0" * 64)

    def test_real_structure_multiplicities_and_primitive_counts(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "cases/h3s-2014.json").read_text())
        for s in config["material_states"]:
            result = primitive_structure(s["structure"])
            self.assertEqual(result["conventional_atoms"], 12 if s["phase"] == "R3m" else 8)
            self.assertEqual(result["primitive_atoms"], 4)
            self.assertEqual(result["atomic_numbers"].count(1), 3)
            self.assertEqual(result["atomic_numbers"].count(16), 1)

    def test_csv_nulls_and_provenance(self):
        p = dict(frequency_thz=1, frequency_pixel=12, amplitude_pixel=None, pixel_low=None,
                 pixel_high=None, observed_amplitude=None, reconstructed_amplitude=None, status="missing")
        c = dict(id="x", kind="phonon_dos", projection="X", unit="pixel", points=[p],
                 review_status="needs_review")
        result = dict(case_id="test", source=dict(paper_sha256="a"*64, figure=dict(pdf_page=5, label="Fig. 5")),
                      material_states=[dict(id="state", formula="X", phase="P1", pressure_gpa=10, curves=[c],
                                            dos_normalization_candidate={})])
        row = list(csv.DictReader(io.StringIO(csv_text(result))))[0]
        self.assertEqual(row["observed_amplitude"], "")
        self.assertEqual(row["point_status"], "missing")
        self.assertEqual(row["training_ready"], "False")
        self.assertEqual(row["source_sha256"], "a"*64)
        self.assertEqual(row["normalized_unit"], "")
        self.assertEqual(row["normalization_accepted"], "False")


if __name__ == "__main__":
    unittest.main()
