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


class ReleaseCheckInterruptionTests(unittest.TestCase):
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
