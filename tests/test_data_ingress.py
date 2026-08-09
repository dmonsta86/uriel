"""R1.2 immutable local Evidence Ingress tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from uriel.core import Refusal, canonical_json, initialize_project
from uriel.data_contracts import plan_data_import
from uriel.data_ingress import import_data_artifact, verify_data_import


class DataIngressTests(unittest.TestCase):
    def _project_and_source(self, temporary: str) -> tuple[Path, Path]:
        base = Path(temporary)
        root = base / "project"
        source = base / "private-account-name" / "records.csv"
        source.parent.mkdir()
        source.write_text("id,value\na,1\nb,2\n", encoding="utf-8")
        initialize_project(root, title="Ingress", question="Can exact local bytes be sealed?")
        return root, source

    def _save_plan(
        self,
        root: Path,
        source: Path,
        *,
        label: str = "records",
        filename: str = "import-plan.json",
        max_source_bytes: int = 1024 * 1024,
    ) -> str:
        plan = plan_data_import(
            root,
            source,
            label=label,
            max_source_bytes=max_source_bytes,
        )["plan"]
        target = root / "artifacts" / filename
        target.write_text(canonical_json(plan), encoding="utf-8")
        return target.relative_to(root).as_posix()

    def test_copy_reference_retry_and_independent_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._project_and_source(temporary)
            first_plan = self._save_plan(root, source, label="alpha", filename="alpha-plan.json")
            first = import_data_artifact(root, source, first_plan)
            self.assertEqual("SEALED", first["status"])
            self.assertEqual("COPIED", first["outcome"])
            self.assertTrue(first["copy_performed"])
            self.assertFalse(first["gate_0_authority_granted"])

            managed = root / first["managed_relative_path"]
            self.assertEqual(source.read_bytes(), managed.read_bytes())
            verified = verify_data_import(root, first["receipt_relative_path"])
            self.assertTrue(verified["verified"])
            self.assertEqual("PASS", verified["decision"])

            retry = import_data_artifact(root, source, first_plan)
            self.assertEqual("ALREADY_IMPORTED", retry["status"])
            self.assertTrue(retry["reused_existing_receipt"])
            self.assertFalse(retry["copy_performed"])
            self.assertEqual(first["receipt_relative_path"], retry["receipt_relative_path"])

            second_plan = self._save_plan(root, source, label="beta", filename="beta-plan.json")
            second = import_data_artifact(root, source, second_plan)
            self.assertEqual("REFERENCED", second["outcome"])
            self.assertFalse(second["copy_performed"])
            self.assertEqual(first["managed_relative_path"], second["managed_relative_path"])
            self.assertNotEqual(first["raw_record_relative_path"], second["raw_record_relative_path"])

            raw_files = [path for path in (root / ".uriel" / "data" / "raw").rglob("*") if path.is_file()]
            raw_records = list((root / ".uriel" / "data" / "records" / "raw").glob("*.json"))
            self.assertEqual(1, len(raw_files))
            self.assertEqual(2, len(raw_records))

            persisted = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (root / ".uriel" / "data").rglob("*.json")
            )
            self.assertNotIn(str(source), persisted)
            self.assertNotIn("private-account-name", persisted)

    def test_changed_encoding_oversize_and_low_disk_fail_without_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._project_and_source(temporary)
            plan_path = self._save_plan(root, source, filename="stale-plan.json")
            source.write_text("id,value\na,changed\n", encoding="utf-8")
            with self.assertRaises(Refusal) as stale:
                import_data_artifact(root, source, plan_path)
            self.assertEqual("DATA_PLAN_STALE", stale.exception.code)

            source.write_text("id,value\na,1\nb,2\n", encoding="utf-8")
            encoding_plan = self._save_plan(root, source, filename="encoding-plan.json")
            source.write_bytes(b"id,value\n\xff,1\n")
            with self.assertRaises(Refusal) as encoding:
                import_data_artifact(root, source, encoding_plan)
            self.assertEqual("DATA_ENCODING_REFUSED", encoding.exception.code)

            source.write_text("a\n", encoding="utf-8")
            small_plan = self._save_plan(root, source, filename="small-plan.json", max_source_bytes=8)
            source.write_text("0123456789\n", encoding="utf-8")
            with self.assertRaises(Refusal) as oversized:
                import_data_artifact(root, source, small_plan)
            self.assertEqual("DATA_RESOURCE_BUDGET", oversized.exception.code)

            source.write_text("id,value\na,1\n", encoding="utf-8")
            disk_plan = self._save_plan(root, source, filename="disk-plan.json")
            with mock.patch("uriel.data_ingress.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
                with self.assertRaises(Refusal) as disk:
                    import_data_artifact(root, source, disk_plan)
            self.assertEqual("DATA_DISK_SPACE", disk.exception.code)

            receipts = root / ".uriel" / "data" / "receipts" / "import"
            self.assertFalse(receipts.exists())
            data_root = root / ".uriel" / "data"
            if data_root.exists():
                self.assertFalse(any(".tmp." in path.name for path in data_root.rglob("*")))

    def test_interrupted_publish_leaves_no_authoritative_partial_and_retry_works(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._project_and_source(temporary)
            plan_path = self._save_plan(root, source)
            with mock.patch("uriel.data_ingress.os.link", side_effect=OSError("injected interruption")):
                with self.assertRaises(Refusal) as interrupted:
                    import_data_artifact(root, source, plan_path)
            self.assertEqual("DATA_IMPORT_INTERRUPTED", interrupted.exception.code)
            receipts = root / ".uriel" / "data" / "receipts" / "import"
            self.assertFalse(receipts.exists())
            self.assertFalse(any(".tmp." in path.name for path in (root / ".uriel" / "data").rglob("*")))

            recovered = import_data_artifact(root, source, plan_path)
            self.assertEqual("SEALED", recovered["status"])
            self.assertTrue(verify_data_import(root, recovered["receipt_relative_path"])["verified"])

    def test_tamper_and_unsafe_plan_path_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._project_and_source(temporary)
            with self.assertRaises(Refusal) as escaped:
                import_data_artifact(root, source, "../outside-plan.json")
            self.assertEqual("INVALID_RELATIVE_PATH", escaped.exception.code)

            plan_path = self._save_plan(root, source)
            imported = import_data_artifact(root, source, plan_path)
            (root / imported["managed_relative_path"]).write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(Refusal) as tampered:
                verify_data_import(root, imported["receipt_relative_path"])
            self.assertEqual("DATA_MANAGED_ARTIFACT_TAMPERED", tampered.exception.code)

            managed = root / imported["managed_relative_path"]
            managed.write_bytes(source.read_bytes())
            self.assertTrue(verify_data_import(root, imported["receipt_relative_path"])["verified"])
            managed.unlink()
            with self.assertRaises(Refusal) as missing:
                verify_data_import(root, imported["receipt_relative_path"])
            self.assertEqual("DATA_MANAGED_ARTIFACT_TAMPERED", missing.exception.code)
            with self.assertRaises(Refusal) as retry:
                import_data_artifact(root, source, plan_path)
            self.assertEqual("DATA_MANAGED_ARTIFACT_TAMPERED", retry.exception.code)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_source_replaced_by_symlink_after_plan_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._project_and_source(temporary)
            plan_path = self._save_plan(root, source)
            alternate = source.parent / "alternate.csv"
            alternate.write_bytes(source.read_bytes())
            source.unlink()
            try:
                os.symlink(str(alternate), str(source))
            except OSError:
                self.skipTest("symlink creation unavailable for this account")
            with self.assertRaises(Refusal) as linked:
                import_data_artifact(root, source, plan_path)
            self.assertEqual("DATA_SOURCE_TYPE_REFUSED", linked.exception.code)


if __name__ == "__main__":
    unittest.main()
