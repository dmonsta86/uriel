from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.blessing import issue_blessing, verify_blessing
from uriel.qr import qr_matrix
from tests.helpers import make_passing_project


class BlessingTests(unittest.TestCase):
    def test_blessing_issues_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_passing_project(root)
            result = issue_blessing(root)
            self.assertTrue(result["verified"], result["errors"])
            package = Path(result["package"])
            self.assertTrue((package / "certificate.svg").is_file())
            self.assertTrue((package / "verify.py").is_file())
            checked = verify_blessing(package, project_root=root)
            self.assertTrue(checked["verified"], checked["errors"])

    def test_package_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_passing_project(root)
            result = issue_blessing(root)
            package = Path(result["package"])
            (package / "certificate.txt").write_text("tampered\n", encoding="utf-8")
            checked = verify_blessing(package)
            self.assertFalse(checked["verified"])
            self.assertTrue(checked["errors"])

    def test_qr_encoder_is_deterministic(self) -> None:
        payload = "URIEL-BLESSING-v1:" + "a" * 32 + ":" + "b" * 16
        first = qr_matrix(payload)
        second = qr_matrix(payload)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 37)
        self.assertTrue(all(len(row) == 37 for row in first))


if __name__ == "__main__":
    unittest.main()
