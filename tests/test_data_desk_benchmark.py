from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "uriel_data_benchmark_check_test", ROOT / "scripts" / "check_data_desk_benchmark.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Data Desk benchmark checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DataDeskBenchmarkTests(unittest.TestCase):
    def test_tracked_receipt_is_bound_and_claim_limited(self) -> None:
        checker = _load_checker()
        value = json.loads(checker.RECEIPT.read_text(encoding="utf-8"))
        result = checker.validate_receipt(ROOT, value)
        self.assertTrue(result["verified"], result["errors"])
        self.assertIn("not a throughput", result["claim_boundary"])

    def test_tampered_measurement_or_private_path_fails(self) -> None:
        checker = _load_checker()
        value = json.loads(checker.RECEIPT.read_text(encoding="utf-8"))
        tampered = deepcopy(value)
        tampered["fixture"]["rows"] += 1
        tampered["operator_path"] = "C:\\Users\\Example\\secret.csv"
        result = checker.validate_receipt(ROOT, tampered)
        self.assertFalse(result["verified"])
        self.assertTrue(any("membership" in error for error in result["errors"]))
        self.assertTrue(any("fixture" in error for error in result["errors"]))
        self.assertTrue(any("user path" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
