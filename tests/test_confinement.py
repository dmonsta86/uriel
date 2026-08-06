from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, guard_path, initialize_project, safe_relative_path


class ConfinementTests(unittest.TestCase):
    def test_parent_traversal_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            initialize_project(root, title="x", question="q")
            with self.assertRaises(Refusal) as caught:
                guard_path(root, root / ".." / "outside.txt")
            self.assertEqual(caught.exception.code, "PATH_CONFINEMENT_REFUSAL")

    def test_absolute_outside_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            root.mkdir()
            initialize_project(root, title="x", question="q")
            outside = base / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaises(Refusal):
                guard_path(root, outside, must_exist=True)

    def test_safe_relative_rejects_parent_and_absolute(self) -> None:
        with self.assertRaises(Refusal):
            safe_relative_path("../escape")
        with self.assertRaises(Refusal):
            safe_relative_path(str(Path.cwd().resolve()))

    def test_symlink_traversal_is_refused_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            initialize_project(root, title="x", question="q")
            outside = base / "outside"
            outside.mkdir()
            link = root / "linked"
            try:
                os.symlink(str(outside), str(link), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable for this account")
            with self.assertRaises(Refusal) as caught:
                guard_path(root, link / "file.txt")
            self.assertEqual(caught.exception.code, "LINK_TRAVERSAL_REFUSAL")


if __name__ == "__main__":
    unittest.main()
