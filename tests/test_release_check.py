from __future__ import annotations

from contextlib import ExitStack
import importlib.util
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch


def load_release_check():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("uriel_release_check_test", root / "scripts" / "release_check.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load release_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 424242
        self.returncode = None
        self.stopped = False
        self.waited = False

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.stopped = True
        self.returncode = -15

    def kill(self) -> None:
        self.stopped = True
        self.returncode = -9

    def wait(self, timeout=None):
        del timeout
        self.waited = True
        if self.returncode is None:
            self.returncode = -15
        return self.returncode

    def stop_group(self, pid: int, signum: int) -> None:
        self.assert_pid = pid
        self.assert_signal = signum
        self.stopped = True
        self.returncode = -signum

    def communicate(self, input=None, timeout=None):
        del input, timeout
        return None, None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class ReleaseCheckInterruptionTests(unittest.TestCase):
    def test_captured_child_output_replaces_non_utf8_bytes(self) -> None:
        module = load_release_check()
        with module._temporary_output_file() as captured:
            captured.buffer.write(b"diagnostic\x96tail")
            captured.seek(0)
            output = captured.read()
        self.assertEqual("diagnostic\ufffdtail", output)

    def test_release_gates_cover_public_truth_surfaces(self) -> None:
        module = load_release_check()
        required = {
            "scripts/check_community_health.py",
            "scripts/check_public_identity.py",
            "scripts/check_readme.py",
            "scripts/check_i18n.py",
            "scripts/check_localization_integrity.py",
            "scripts/check_capability_status.py",
            "scripts/check_schema_mirror.py",
            "scripts/check_forge_trial.py",
            "scripts/check_data_desk_benchmark.py",
        }
        self.assertEqual(set(module.PRE_BUILD_CHECKS), required)

    def test_signal_handler_raises_recoverable_exception(self) -> None:
        module = load_release_check()
        with self.assertRaises(module.ReleaseInterrupted) as caught:
            module._termination_handler(signal.SIGTERM, None)
        self.assertEqual(signal.SIGTERM, caught.exception.signum)

    def test_windows_stop_requests_complete_child_tree_termination(self) -> None:
        module = load_release_check()
        fake = FakeProcess()
        completed = type("Completed", (), {"returncode": 0})()
        with patch.object(module.os, "name", "nt"), patch.object(
            module.subprocess, "run", return_value=completed
        ) as taskkill:
            module._stop_process(fake)
        self.assertEqual(
            ["taskkill", "/PID", str(fake.pid), "/T", "/F"],
            taskkill.call_args.args[0],
        )
        self.assertTrue(fake.waited)

    def test_main_checkpoints_signal_between_subprocesses(self) -> None:
        module = load_release_check()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "between-steps.txt"
            argv = [
                "release_check.py",
                "--repository",
                str(root),
                "--report",
                str(report),
            ]
            with patch.object(module.sys, "argv", argv), patch.object(
                module,
                "execute",
                side_effect=module.ReleaseInterrupted(signal.SIGTERM),
            ):
                code = module.main()
            self.assertEqual(128 + signal.SIGTERM, code)
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("no child process remained active", report_text)
            self.assertIn("STATUS: INTERRUPTED", report_text)

    def test_run_stops_child_and_checkpoints_interruption(self) -> None:
        module = load_release_check()
        fake = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "release-check.txt"
            log = []
            with ExitStack() as stack:
                stack.enter_context(patch.object(module.subprocess, "Popen", return_value=fake))
                stack.enter_context(
                    patch.object(module.time, "sleep", side_effect=module.ReleaseInterrupted(signal.SIGTERM))
                )
                if module.os.name != "nt":
                    stack.enter_context(patch.object(module.os, "killpg", side_effect=fake.stop_group))
                else:
                    stack.enter_context(
                        patch.object(
                            module.subprocess,
                            "run",
                            return_value=type("Completed", (), {"returncode": 1})(),
                        )
                    )
                with self.assertRaises(SystemExit) as caught:
                    module.run(
                        ["fake-command"],
                        root,
                        log,
                        report,
                        timeout_seconds=30,
                    )
            self.assertEqual(128 + signal.SIGTERM, caught.exception.code)
            self.assertTrue(fake.stopped)
            self.assertTrue(fake.waited)
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("active child process stopped", report_text)
            self.assertIn("STATUS: INTERRUPTED", report_text)


if __name__ == "__main__":
    unittest.main()
