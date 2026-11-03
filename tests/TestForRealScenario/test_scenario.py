"""只验证辅助工具边界，不代表真实业务黑盒测试已通过。"""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scenario


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / "正文.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nfixture for helper validation only")
        self.case = copy.deepcopy(scenario.read_json(scenario.ROOT / "h3s.json"))
        self.case["files"] = [{"role": "main", "path": str(self.pdf)}]

    def test_file_identity_and_role_are_preserved(self):
        files = scenario.validate_case(self.case)
        self.assertEqual(files[0]["role"], "main")
        self.pdf.write_bytes(self.pdf.read_bytes() + b"changed")
        self.assertNotEqual(files[0]["sha256"], scenario.validate_case(self.case)[0]["sha256"])

    def test_missing_or_multiple_main_is_rejected(self):
        for files in ([], self.case["files"] * 2):
            self.case["files"] = files
            with self.assertRaisesRegex(ValueError, "恰好"):
                scenario.validate_case(self.case)

    def test_wrong_pdf_content_is_rejected(self):
        self.pdf.write_text("not a PDF")
        with self.assertRaisesRegex(ValueError, "格式"):
            scenario.validate_case(self.case)

    def test_remote_origin_and_wrong_browser_are_rejected(self):
        account = self.case["accounts"]["user"]
        account["origin"] = "https://example.com"
        with self.assertRaisesRegex(ValueError, "本机"):
            scenario.validate_case(self.case)
        account["browser"] = "chrome"
        with self.assertRaisesRegex(ValueError, "safari"):
            scenario.validate_case(self.case)

    def test_explicit_tab_and_two_origin_checks(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({"text": "网页观察"}), "")
        with patch.object(scenario.subprocess, "run", return_value=result) as run:
            self.assertEqual(scenario.call_browser("safari", "http://127.0.0.1:5173", 81, 1, "return 1;"), {"text": "网页观察"})
        args, kwargs = run.call_args
        self.assertEqual(args[0][2:5], ["http://127.0.0.1:5173", "81", "1"])
        self.assertIn("location.origin", args[0][-1])
        self.assertIn("tabURL does not start with", kwargs["input"])
        with self.assertRaisesRegex(ValueError, "明确指定"):
            scenario.call_browser("safari", "http://127.0.0.1:5173", 81, None, "return 1;")

    def test_browser_disabled_error_is_not_success(self):
        result = subprocess.CompletedProcess([], 1, "", "Allow JavaScript from Apple Events")
        with patch.object(scenario.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Allow JavaScript"):
                scenario.call_browser("chrome", "http://localhost:5173", 1, 2, "return 1;")

    def test_run_must_stay_in_case_directory(self):
        with self.assertRaisesRegex(ValueError, "runs"):
            scenario.run_dir(self.temp.name)

    def test_records_never_overwrite_an_observation(self):
        root = Path(self.temp.name)
        first = scenario.save_event(root, {"kind": "operator_note", "text": "第一次"})
        second = scenario.save_event(root, {"kind": "operator_note", "text": "第二次"})
        self.assertNotEqual(first, second)
        self.assertEqual(scenario.read_json(first)["text"], "第一次")
        self.assertEqual(first.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
