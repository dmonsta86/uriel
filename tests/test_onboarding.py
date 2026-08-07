"""Tests for workspace onboarding, consent, preflight, and workspace modes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.onboarding import (
    consent_set,
    consent_status,
    directory_manifest,
    inplace_dryrun,
    inplace_verify,
    preflight,
    review_workspace,
    safe_copy,
    start,
)


class OnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")
        (self.root / "artifacts" / "data.csv").write_bytes(b"a,b\n1,2\n")
        (self.root / "notes.md").write_text("# notes", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_preflight_is_metadata_only(self):
        result = preflight(self.root)
        self.assertEqual(result["schema"], "uriel.preflight.v1")
        self.assertGreaterEqual(result["file_count"], 2)
        names = [row["path"] for row in directory_manifest(self.root)["files"]]
        self.assertIn("artifacts/data.csv", names)
        self.assertIn("notes.md", names)
        self.assertRegex(result["root_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["copy_estimate"]["files"], result["file_count"])
        self.assertTrue(result["read_only_feasible"])
        self.assertNotIn(".uriel", [name.split("/", 1)[0] for name in names])

    def test_preflight_detects_vcs_and_sensitive_names(self):
        (self.root / ".git").mkdir()
        (self.root / ".env").write_text("KEY=value", encoding="utf-8")
        result = preflight(self.root)
        self.assertEqual(result["detected_vcs"], [".git"])
        self.assertIn(".env", result["sensitive_file_indications"])

    def test_preflight_detects_cloud_sync_marker(self):
        cloud = Path(self.tmp.name) / "OneDrive" / "x"
        initialize_project(cloud, title="t", question="q", privacy="public")
        result = preflight(cloud)
        self.assertTrue(result["cloud_sync_indicators"])

    def test_preflight_refuses_missing_root(self):
        with self.assertRaises(Refusal):
            preflight(Path(self.tmp.name) / "missing")

    def test_consent_requires_cloud_ack_in_content_modes(self):
        cloud = Path(self.tmp.name) / "Dropbox" / "y"
        initialize_project(cloud, title="t", question="q", privacy="public")
        with self.assertRaises(Refusal):
            consent_set(cloud, "read_only")
        result = consent_set(cloud, "read_only", cloud_sync_acknowledged=True,
                             sensitive_data_acknowledged=True)
        self.assertTrue(result["created"])

    def test_consent_records_are_immutable_and_latest_wins(self):
        first = consent_set(self.root, "metadata_only")
        second = consent_set(self.root, "read_only", sensitive_data_acknowledged=True)
        self.assertNotEqual(first["record_sha256"], second["record_sha256"])
        status = consent_status(self.root)
        self.assertEqual(status["records"], 2)
        self.assertEqual(status["latest"]["mode"], "read_only")

    def test_consent_in_place_requires_explicit_confirmation(self):
        with self.assertRaises(Refusal):
            consent_set(self.root, "in_place", confirmation="installer_default_read_only")

    def test_start_requires_explicit_kind(self):
        with self.assertRaises(Refusal):
            start(self.root / "fresh")
        result = start(self.root / "fresh", "new_idea", title="t", question="q")
        self.assertEqual(result["entry_kind"], "new_idea")
        self.assertEqual(result["mode"], "read_only")

    def test_start_writes_entry_files_without_authority(self):
        result = start(self.root, "resume")
        for name in ("URIEL_START_HERE.md", "URIEL_AI_ENTRY.md", "COPY_THIS_TO_YOUR_AI.txt", "AGENTS.md"):
            self.assertIn(name, result["files_written"])
            self.assertTrue((self.root / name).is_file())
        entry = (self.root / "URIEL_AI_ENTRY.md").read_text(encoding="utf-8")
        self.assertIn("Blessing", entry)
        self.assertIn("Data Readiness", entry)
        self.assertIn(self.root.name, entry)
        for agent in ("uriel-orient.md", "uriel-plan.md", "uriel-build.md"):
            self.assertTrue((self.root / ".opencode" / "agents" / agent).is_file())
        orient = (self.root / ".opencode" / "agents" / "uriel-orient.md").read_text(encoding="utf-8")
        self.assertIn("edit: deny", orient)
        self.assertIn("bash: deny", orient)
        build = (self.root / ".opencode" / "agents" / "uriel-build.md").read_text(encoding="utf-8")
        self.assertIn("git push: deny", build)

    def test_start_refuses_to_overwrite_entry_files(self):
        start(self.root, "resume")
        with self.assertRaises(Refusal):
            start(self.root, "resume")

    def test_start_records_onboarding_state(self):
        start(self.root, "resume")
        onboarding = json.loads((self.root / ".uriel" / "onboarding.json").read_text(encoding="utf-8"))
        self.assertEqual(onboarding["schema"], "uriel.onboarding.v1")
        self.assertEqual(onboarding["data_readiness"], "not_started")
        self.assertEqual(onboarding["publication_authority"], "none")

    def test_review_workspace_lives_outside_root(self):
        start(self.root, "resume")
        result = review_workspace(self.root)
        review_path = Path(result["review_workspace"])
        self.assertNotIn(self.root, review_path.parents)
        for name in ("PROJECT_MAP.md", "FINDINGS.md", "GAP_REGISTER.csv",
                     "DATA_READINESS_PLAN.md", "REPAIR_OR_INTEGRATION_PLAN.md", "NEXT_PROMPT.txt"):
            self.assertTrue((review_path / name).is_file())
        prompt = (review_path / "NEXT_PROMPT.txt").read_text(encoding="utf-8")
        self.assertIn("next instruction", prompt)

    def test_review_workspace_requires_consent(self):
        with self.assertRaises(Refusal):
            review_workspace(self.root)

    def test_safe_copy_preserves_original_generation(self):
        consent_set(self.root, "safe_copy", sensitive_data_acknowledged=True)
        result = safe_copy(self.root)
        self.assertTrue(result["same_original_generation"])
        copy_root = Path(result["destination"])
        self.assertTrue((copy_root / "artifacts" / "data.csv").is_file())
        self.assertTrue((copy_root / "URIEL_COPY_MANIFEST.json").is_file())
        self.assertTrue((copy_root / "ORIGINAL_INVARIANCE.json").is_file())
        self.assertNotIn(".uriel", [p.name for p in copy_root.iterdir()])
        receipt = json.loads((copy_root / "ORIGINAL_INVARIANCE.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt["same_original_generation"])

    def test_safe_copy_requires_consent(self):
        with self.assertRaises(Refusal):
            safe_copy(self.root)

    def test_safe_copy_refuses_existing_destination(self):
        consent_set(self.root, "safe_copy", sensitive_data_acknowledged=True)
        destination = Path(self.tmp.name) / "existing"
        destination.mkdir()
        with self.assertRaises(Refusal):
            safe_copy(self.root, destination=destination)

    def test_safe_copy_records_links_without_following(self):
        consent_set(self.root, "safe_copy", sensitive_data_acknowledged=True)
        link = self.root / "linked.txt"
        try:
            link.symlink_to(self.root / "notes.md")
        except OSError:
            self.skipTest("symlinks unavailable on this platform")
        result = safe_copy(self.root)
        self.assertEqual(result["exclusions"][0]["reason"], "link_or_reparse_recorded_not_followed")
        copy_root = Path(result["destination"])
        self.assertFalse((copy_root / "linked.txt").exists())

    def test_inplace_dryrun_requires_consent(self):
        with self.assertRaises(Refusal):
            inplace_dryrun(self.root)

    def test_inplace_dryrun_and_verify_unchanged(self):
        consent_set(self.root, "in_place", confirmation="explicit_user",
                    sensitive_data_acknowledged=True)
        plan = inplace_dryrun(self.root)
        self.assertTrue(plan["plan"]["dry_run"])
        verify = inplace_verify(self.root)
        self.assertTrue(verify["unchanged"])

    def test_inplace_verify_stops_on_source_change(self):
        consent_set(self.root, "in_place", confirmation="explicit_user",
                    sensitive_data_acknowledged=True)
        inplace_dryrun(self.root)
        (self.root / "notes.md").write_text("# changed", encoding="utf-8")
        with self.assertRaises(Refusal) as context:
            inplace_verify(self.root)
        self.assertEqual(context.exception.code, "INPLACE_SOURCE_CHANGED")


if __name__ == "__main__":
    unittest.main()
