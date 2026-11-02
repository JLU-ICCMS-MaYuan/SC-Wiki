"""费用不猜测、参考答案不入提示、配对与图谱误识别可检出的Demo回归。"""
from copy import deepcopy
from pathlib import Path
import unittest

from experiment import SYSTEM, combine, formula, number_equal, reference, resources, score
from serve import source_path


class ComparisonTests(unittest.TestCase):
    def test_common_prompt_contains_no_reference_answers(self):
        for value in ("235", "220", "201", "187", "0.02234", "3.05", "0.48"):
            self.assertNotIn(value, SYSTEM)

    def test_wrong_mu_pair_is_not_counted_as_correct(self):
        ref = reference()
        out = {"tc_points": deepcopy(ref["tc_points"]), "electronic_results": [], "spectra": []}
        out["tc_points"][0]["mu_star"] = .13
        result = score(out)
        self.assertEqual(result["present"], 4)
        self.assertEqual(result["tc_pairs"], 3)

    def test_missing_usage_and_failed_requests_are_not_zero_cost(self):
        self.assertIsNone(resources([{"status": "completed", "seconds": 2}])["input_tokens"])
        self.assertIsNone(resources([{"status": "completed", "usage": {
            "prompt_tokens": None, "completion_tokens": None}}])["input_tokens"])
        calls = [{"status": "completed", "seconds": 2, "usage": {"prompt_tokens": 10, "completion_tokens": 3}}]
        self.assertEqual(resources(calls)["input_tokens"], 10)
        calls.append({"status": "failed", "seconds": 1})
        self.assertIsNone(resources(calls)["input_tokens"])
        self.assertEqual(resources(calls)["seconds"], 3)

    def test_electronic_dos_cannot_count_as_phonon_dos(self):
        out = {"tc_points": [], "electronic_results": [], "spectra": [
            {"role": "supplementary", "page": 10, "figure_label": "Figure S7", "kinds": ["phonon_dos"]}]}
        result = score(out)
        self.assertEqual(result["figure_matches"], 0)
        self.assertEqual(len(result["unexpected_spectra"]), 1)

    def test_failed_partial_results_are_not_scored_as_success(self):
        failed = {"status": "failed", "result": {"tc_points": [{"tc_k": 235}]}}
        self.assertEqual(combine([failed])["tc_points"], [])

    def test_no_server_filesystem_traversal_or_business_proxy(self):
        root = Path("/private/demo")
        for route in ("/.env", "/page/../../.env", "/api/upload-tasks", "/source/other.pdf"):
            self.assertIsNone(source_path(root, route))
        self.assertEqual(source_path(root, "/page/main/3.jpg")[0], root / "pages/main/3.jpg")

    def test_formula_and_numeric_types_are_not_guessed(self):
        self.assertEqual(formula("CaH₆"), "cah6")
        self.assertFalse(number_equal(True, 1))
        self.assertFalse(number_equal("235", 235))


if __name__ == "__main__":
    unittest.main()
