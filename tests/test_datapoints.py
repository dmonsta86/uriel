from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from uriel import datapoints as dpm
from uriel.core import Refusal, initialize_project, run_workload


def issue_codes(report):
    return {(row["code"], row["subject"]) for row in report["issues"]}


class DatapointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-datapoints-")
        self.root = Path(self.temporary.name) / "project"
        initialize_project(self.root, title="Datapoint test", question="Do bound numbers stay bound?")
        (self.root / "artifacts" / "summary.csv").write_text(
            "metric,value\nn_total,40\nn_a,18\nn_b,22\nmean_a,3.47\npct_a,45.0\np_main,0.0123\n", encoding="utf-8"
        )
        (self.root / "artifacts" / "model.json").write_text(
            json.dumps({"effect": {"est": 0.42, "lo": 0.10, "hi": 0.70}, "label": "primary"}), encoding="utf-8"
        )
        (self.root / "artifacts" / "log.txt").write_text("fit ok\nR2 = 0.312\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_csv(self, key: str, **kwargs) -> dict:
        return dpm.add_datapoint(
            self.root,
            datapoint_id=key,
            artifact_path="artifacts/summary.csv",
            locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=" + key]),
            description="Summary value " + key,
            **kwargs,
        )

    def test_values_are_extracted_not_typed(self) -> None:
        saved = self.add_csv("n_total", kind="count")["datapoint"]
        self.assertEqual(40, saved["value"])
        self.assertEqual("40", saved["source_token"])
        json_dp = dpm.add_datapoint(
            self.root, datapoint_id="est", artifact_path="artifacts/model.json",
            locator=dpm.locator_from_arguments(json_pointer="/effect/est"), description="Effect estimate", kind="estimate",
        )["datapoint"]
        self.assertEqual(0.42, json_dp["value"])
        text_dp = dpm.add_datapoint(
            self.root, datapoint_id="r2", artifact_path="artifacts/log.txt",
            locator=dpm.locator_from_arguments(text_regex=r"R2 = (\d\.\d+)"), description="Model R squared", kind="proportion",
        )["datapoint"]
        self.assertEqual("0.312", text_dp["source_token"])
        report = dpm.verify_registry(self.root)
        self.assertEqual(3, report["verified_count"])
        self.assertEqual(0, report["grave_count"])

    def test_ambiguous_or_missing_locators_refuse(self) -> None:
        (self.root / "artifacts" / "dup.csv").write_text("metric,value\nn,1\nn,2\n", encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            dpm.add_datapoint(self.root, datapoint_id="n", artifact_path="artifacts/dup.csv",
                              locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=n"]), description="Count n")
        self.assertEqual("DATAPOINT_LOCATOR_FAILED", caught.exception.code)
        self.assertEqual(3, len(caught.exception.repairs))
        with self.assertRaises(Refusal):
            dpm.add_datapoint(self.root, datapoint_id="x", artifact_path="artifacts/model.json",
                              locator=dpm.locator_from_arguments(json_pointer="/effect"), description="Object value")
        with self.assertRaises(Refusal):
            dpm.add_datapoint(self.root, datapoint_id="y", artifact_path="artifacts/log.txt",
                              locator=dpm.locator_from_arguments(text_regex=r"(\w+)"), description="Too many matches")
        with self.assertRaises(Refusal):
            dpm.locator_from_arguments(csv_column="value", json_pointer="/a")

    def test_duplicate_ids_and_circular_sources_refuse(self) -> None:
        self.add_csv("n_total", kind="count")
        with self.assertRaises(Refusal) as caught:
            self.add_csv("n_total", kind="count")
        self.assertEqual("DATAPOINT_ID_EXISTS", caught.exception.code)
        (self.root / "paper").mkdir(exist_ok=True)
        (self.root / "paper" / "values.csv").write_text("metric,value\nn,1\n", encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            dpm.add_datapoint(self.root, datapoint_id="circ", artifact_path="paper/values.csv",
                              locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=n"]), description="Circular")
        self.assertEqual("DATAPOINT_ARTIFACT_CIRCULAR", caught.exception.code)

    def test_changed_bytes_are_stale_and_refresh_needs_confirmation(self) -> None:
        self.add_csv("n_total", kind="count")
        csv_path = self.root / "artifacts" / "summary.csv"
        csv_path.write_text(csv_path.read_text(encoding="utf-8").replace("n_total,40", "n_total,41"), encoding="utf-8")
        self.assertIn(("DATAPOINT_ARTIFACT_STALE", "n_total"), issue_codes(dpm.verify_registry(self.root)))
        with self.assertRaises(Refusal) as caught:
            dpm.refresh_datapoint(self.root, "n_total")
        self.assertEqual("DATAPOINT_VALUE_CHANGED", caught.exception.code)
        refreshed = dpm.refresh_datapoint(self.root, "n_total", confirm_change=True)
        self.assertTrue(refreshed["value_changed"])
        self.assertEqual(41, refreshed["datapoint"]["value"])
        self.assertEqual(0, dpm.verify_registry(self.root)["grave_count"])

    def test_unchanged_value_refresh_needs_no_confirmation(self) -> None:
        self.add_csv("n_total", kind="count")
        csv_path = self.root / "artifacts" / "summary.csv"
        csv_path.write_text(csv_path.read_text(encoding="utf-8") + "extra,1\n", encoding="utf-8")
        refreshed = dpm.refresh_datapoint(self.root, "n_total")
        self.assertFalse(refreshed["value_changed"])

    def test_hand_edited_value_is_a_mismatch(self) -> None:
        self.add_csv("n_total", kind="count")
        registry = dpm.load_registry(self.root)
        registry["datapoints"][0]["value"] = 44
        (self.root / "paper" / "datapoints.json").write_text(json.dumps(registry), encoding="utf-8")
        self.assertIn(("DATAPOINT_VALUE_MISMATCH", "n_total"), issue_codes(dpm.verify_registry(self.root)))

    def test_kind_bounds_relations_and_grim(self) -> None:
        for key, kind in (("n_total", "count"), ("n_a", "count"), ("n_b", "count"), ("pct_a", "percent")):
            self.add_csv(key, kind=kind)
        self.add_csv("mean_a", kind="mean", grim_n="dp:n_a")
        registry = dpm.load_registry(self.root)
        registry["relations"] = [
            {"type": "sum", "parts": ["n_a", "n_b"], "total": "n_total"},
            {"type": "ratio", "numerator": "n_a", "denominator": "n_total", "result": "pct_a", "scale": 100},
            {"type": "le", "left": "n_total", "right": "n_a"},
        ]
        (self.root / "paper" / "datapoints.json").write_text(json.dumps(registry), encoding="utf-8")
        report = dpm.verify_registry(self.root)
        codes = issue_codes(report)
        self.assertIn(("DATAPOINT_GRIM_INCONSISTENT", "mean_a"), codes)  # 3.47 is impossible for n = 18
        self.assertEqual(["PASS", "PASS", "FAIL"], [row["status"] for row in report["relations"]])
        registry["datapoints"].append({
            "id": "bad_p", "description": "Impossible p value", "artifact_path": "artifacts/summary.csv",
            "sha256": registry["datapoints"][0]["sha256"], "kind": "count",
            "locator": {"type": "csv_cell", "column": "value", "row": {"metric": "mean_a"}}, "value": 3.47,
        })
        (self.root / "paper" / "datapoints.json").write_text(json.dumps(registry), encoding="utf-8")
        self.assertIn(("DATAPOINT_SANITY_VIOLATION", "bad_p"), issue_codes(dpm.verify_registry(self.root)))

    def test_non_numeric_bounds_are_rejected_not_ignored(self) -> None:
        self.add_csv("n_total", kind="count")
        registry = dpm.load_registry(self.root)
        registry["datapoints"][0]["max"] = "ten"
        (self.root / "paper" / "datapoints.json").write_text(json.dumps(registry), encoding="utf-8")
        self.assertIn(("DATAPOINT_REGISTRY_INVALID", "n_total"), issue_codes(dpm.verify_registry(self.root)))

    def test_formats_render_from_the_verified_token(self) -> None:
        self.assertEqual("p < .001", dpm.render_token("0.0004", "apa_p"))
        self.assertEqual("p = .012", dpm.render_token("0.0123", "apa_p"))
        self.assertEqual("1,234", dpm.render_token("1234", ",d"))
        self.assertEqual("0.43", dpm.render_token("0.425", ".2f"))
        self.assertEqual("-.45", dpm.render_token("-0.449", ".2f~"))
        self.assertEqual("45.0%", dpm.render_token("0.45", ".1%"))
        self.assertEqual("0.4300", dpm.render_token("0.4300", None))
        with self.assertRaises(Refusal):
            dpm.render_token("3.5", "d")
        with self.assertRaises(Refusal):
            dpm.render_token("abc", ".2f")
        self.assertFalse(dpm.valid_format("{:.2f}"))

    def test_rounded_to_zero_is_flagged(self) -> None:
        dpm.add_datapoint(self.root, datapoint_id="p", artifact_path="artifacts/summary.csv",
                          locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=p_main"]),
                          description="Main p value", kind="p_value", fmt=".1f")
        self.assertIn(("DATAPOINT_ROUNDED_TO_ZERO", "p"), issue_codes(dpm.verify_registry(self.root)))

    def test_generated_artifacts_need_run_provenance_or_disclosure(self) -> None:
        self.add_csv("n_total", kind="count")
        self.add_csv("n_a", kind="count", provenance="external: produced by the registry office export in 2026")
        codes = issue_codes(dpm.verify_registry(self.root))
        self.assertIn(("DATAPOINT_NOT_FROM_RECORDED_RUN", "n_total"), codes)
        self.assertNotIn(("DATAPOINT_NOT_FROM_RECORDED_RUN", "n_a"), codes)
        (self.root / "make.py").write_text("open('artifacts/made.csv','w').write('metric,value\\nk,7\\n')\n", encoding="utf-8")
        run_workload(self.root, [sys.executable, "make.py"], timeout=60, workload_id="make")
        dpm.add_datapoint(self.root, datapoint_id="k", artifact_path="artifacts/made.csv",
                          locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=k"]), description="Made value k")
        report = dpm.verify_registry(self.root)
        made = next(row for row in report["datapoints"] if row["id"] == "k")
        self.assertEqual("written_by_run", made["provenance"])

    def test_artifacts_outside_the_source_inventory_are_rejected(self) -> None:
        build = self.root / "artifacts" / "build"
        build.mkdir()
        (build / "out.csv").write_text("metric,value\nk,1\n", encoding="utf-8")
        dpm.add_datapoint(self.root, datapoint_id="hidden", artifact_path="artifacts/build/out.csv",
                          locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=k"]), description="Ignored dir value")
        from uriel.core import build_manifest

        manifest = build_manifest(self.root, persist=False)
        paths = {row["relative_path"]: row["sha256"] for row in manifest["records"]}
        report = dpm.verify_registry(self.root, manifest_paths=paths)
        self.assertIn(("DATAPOINT_ARTIFACT_NOT_MANIFESTED", "hidden"), issue_codes(report))

    def test_unknown_claim_links_are_refused_at_registration(self) -> None:
        with self.assertRaises(Refusal) as caught:
            self.add_csv("n_total", kind="count", claim_ids=["C99"])
        self.assertEqual("DATAPOINT_UNKNOWN_CLAIM", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
