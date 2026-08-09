from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from uriel import adapters
from uriel.core import Refusal, initialize_project, load_project, save_project
from uriel.prompts import MAX_PROMPT_BYTES, MAX_PROMPT_SOURCE_PROJECT_BYTES, build_prompt


class PromptPrivacyTests(unittest.TestCase):
    def test_nonpublic_projection_is_allowlisted_and_local_is_not_implicitly_sensitive(self) -> None:
        marker = "PRIVATE-MARKER-DO-NOT-EXPORT"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title=marker, question=marker, privacy="confidential")
            project = load_project(root)
            project["unexpected_future_field"] = marker
            project["hypothesis"]["falsifier"] = marker
            project["novelty_review"]["queries"] = [marker]
            project["methods"]["analysis_plan"] = marker
            project["ethics"]["risks"] = [marker]
            project["disclosures"]["funding"] = [marker]
            project["submission"]["target_venues"] = [marker]
            project["privacy"]["redaction_notes"] = [marker]
            save_project(root, project, event="test.private_content", details={})

            generic = build_prompt(root, task="clarity", provider="generic")
            local_default = build_prompt(root, task="clarity", provider="local")
            self.assertTrue(generic["redacted"])
            self.assertTrue(local_default["redacted"])
            self.assertNotIn(marker, generic["prompt"])
            self.assertNotIn(marker, local_default["prompt"])
            self.assertNotIn("unexpected_future_field", generic["prompt"])
            self.assertIn("redacted_project_projection", generic["prompt"])

            explicit_local = build_prompt(
                root,
                task="clarity",
                provider="local",
                include_sensitive=True,
            )
            self.assertFalse(explicit_local["redacted"])
            self.assertIn(marker, explicit_local["prompt"])

    def test_sensitive_external_export_needs_acknowledgement_and_stays_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="private title", question="private question", privacy="internal")
            with self.assertRaises(Refusal) as blocked:
                build_prompt(root, task="clarity", provider="generic-web")
            self.assertEqual("EXTERNAL_AI_PRIVACY_ACK_REQUIRED", blocked.exception.code)
            result = build_prompt(
                root,
                task="clarity",
                provider="generic-web",
                acknowledge_external=True,
                model="generic/test",
            )
            self.assertTrue(result["redacted"])
            self.assertNotIn("private question", result["prompt"])
            self.assertIn('"model": "generic/test"', result["prompt"])

    def test_prompt_hard_budget_refuses_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="large", question="bounded?", privacy="public")
            project = load_project(root)
            project["claims"][0]["statement"] = "x" * MAX_PROMPT_BYTES
            save_project(root, project, event="test.large_prompt", details={})
            with self.assertRaises(Refusal) as blocked:
                build_prompt(root, task="clarity")
            self.assertEqual("PROMPT_BUDGET_EXCEEDED", blocked.exception.code)

    def test_oversized_project_is_refused_before_prompt_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="large", question="bounded source?", privacy="public")
            project = load_project(root)
            project["claims"][0]["statement"] = "x" * MAX_PROMPT_SOURCE_PROJECT_BYTES
            save_project(root, project, event="test.large_prompt_source", details={})
            with self.assertRaises(Refusal) as blocked:
                build_prompt(root, task="clarity")
            self.assertEqual("PROMPT_SOURCE_PROJECT_TOO_LARGE", blocked.exception.code)


class ExternalAdapterTests(unittest.TestCase):
    def test_bounded_capture_stops_oversized_output_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(Refusal) as oversized:
                adapters._run_bounded_process(
                    [sys.executable, "-c", "import sys; sys.stdout.write('x' * 200000); sys.stdout.flush()"],
                    cwd=root,
                    timeout=5,
                    max_output_bytes=1024,
                    environment=adapters._sanitized_environment(),
                )
            self.assertEqual("EXTERNAL_AGENT_OUTPUT_LIMIT", oversized.exception.code)
            with self.assertRaises(Refusal) as timed_out:
                adapters._run_bounded_process(
                    [sys.executable, "-c", "import time; time.sleep(2)"],
                    cwd=root,
                    timeout=0.05,
                    max_output_bytes=1024,
                    environment=adapters._sanitized_environment(),
                )
            self.assertEqual("EXTERNAL_AGENT_TIMEOUT", timed_out.exception.code)

    def test_external_adapter_passes_model_and_uses_isolated_minimized_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="public", question="review this", privacy="public")
            observed = {}

            def fake_run(command, **kwargs):
                observed["command"] = list(command)
                observed.update(kwargs)
                value = {
                    "reviewer_type": "ai",
                    "provider": "generic-web",
                    "model": "generic/test",
                }
                return adapters._ProcessCapture(0, json.dumps(value), "")

            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "not-forwarded"}), mock.patch.object(
                adapters.shutil, "which", return_value=str(root.parent / "fake-agent")
            ), mock.patch.object(adapters, "_run_bounded_process", side_effect=fake_run), mock.patch.object(
                adapters, "import_review", return_value={"finding_count": 1}
            ):
                result = adapters.run_external_agent(
                    root,
                    task="clarity",
                    model="generic/test",
                    timeout=60,
                    acknowledge_external=True,
                )

            self.assertIn("--model", observed["command"])
            self.assertEqual("generic/test", observed["command"][observed["command"].index("--model") + 1])
            self.assertNotIn(str(root), " ".join(observed["command"]))
            self.assertNotEqual(root.resolve(), Path(observed["cwd"]).resolve())
            self.assertNotIn("OPENAI_API_KEY", observed["environment"])
            self.assertEqual("ADVISORY_ONLY", result["authority"])
            self.assertEqual(1, result["finding_count"])
            self.assertFalse(result["raw_output_truncated"])
            self.assertFalse(result["controls"]["os_sandbox"])

    def test_ack_model_identity_and_project_policy_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="internal", question="private", privacy="internal")
            with self.assertRaises(Refusal) as no_ack:
                adapters.run_external_agent(root, task="clarity", model="generic/test")
            self.assertEqual("EXTERNAL_AGENT_ACK_REQUIRED", no_ack.exception.code)
            with self.assertRaises(Refusal) as bad_model:
                adapters.run_external_agent(
                    root,
                    task="clarity",
                    model="--unsafe",
                    acknowledge_external=True,
                )
            self.assertEqual("INVALID_AGENT_MODEL", bad_model.exception.code)

            project = load_project(root)
            project["privacy"]["external_ai"] = "deny"
            save_project(root, project, event="test.external_deny", details={})
            with mock.patch.object(adapters.shutil, "which", return_value=str(root.parent / "fake-agent")):
                with self.assertRaises(Refusal) as denied:
                    adapters.run_external_agent(
                        root,
                        task="clarity",
                        model="generic/test",
                        timeout=60,
                        acknowledge_external=True,
                    )
            self.assertEqual("EXTERNAL_AI_DENIED", denied.exception.code)

    def test_external_output_cannot_spoof_invoked_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="public", question="identity?", privacy="public")
            spoofed = adapters._ProcessCapture(
                0,
                json.dumps(
                    {
                        "reviewer_type": "ai",
                        "provider": "generic-web",
                        "model": "generic/other",
                    }
                ),
                "",
            )
            with mock.patch.object(
                adapters.shutil, "which", return_value=str(root.parent / "fake-agent")
            ), mock.patch.object(adapters, "_run_bounded_process", return_value=spoofed):
                with self.assertRaises(Refusal) as mismatch:
                    adapters.run_external_agent(
                        root,
                        task="clarity",
                        model="generic/test",
                        timeout=60,
                        acknowledge_external=True,
                    )
            self.assertEqual("EXTERNAL_AGENT_IDENTITY_MISMATCH", mismatch.exception.code)


if __name__ == "__main__":
    unittest.main()
