from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


class PackagingTests(unittest.TestCase):
    def test_console_entry_point_and_zero_runtime_dependencies(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?ms)^\[project\.scripts\]\s+uriel\s*=\s*[\"']uriel\.cli:main[\"']")
        self.assertRegex(text, r"(?m)^dependencies\s*=\s*\[\s*\]\s*$")

    def test_required_release_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = [
            "README.md",
            "LICENSE",
            "pyproject.toml",
            "scripts/Uriel.ps1",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            "docs/MAINTAINER_HANDOFF.md",
            "scripts/build_distributions.py",
            "scripts/make_checksums.py",
            "src/uriel/core.py",
            "src/uriel/demo.py",
            "src/uriel/audit.py",
            "src/uriel/blessing.py",
            "src/uriel/cli.py",
        ]
        self.assertEqual([], [item for item in required if not (root / item).is_file()])

    def test_public_repository_metadata_is_bound(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = "https://github.com/dmonsta86/uriel"
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        citation = (root / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn(f'Homepage = "{expected}"', pyproject)
        self.assertIn(f'Repository = "{expected}"', pyproject)
        self.assertIn(f'Issues = "{expected}/issues"', pyproject)
        self.assertIn(f'repository-code: "{expected}"', citation)
        self.assertIn(f'url: "{expected}"', citation)

    def test_public_passing_example_runs_without_test_package_imports(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "src")
            completed = subprocess.run(
                [sys.executable, str(root / "examples" / "passing_fixture.py"), str(Path(temporary) / "demo")],
                cwd=str(root),
                env=environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("audit: PASS", completed.stdout)
            self.assertIn("blessing:", completed.stdout)

    def test_readme_local_assets_resolve(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        for fragment in readme.split('src="')[1:]:
            source = fragment.split('"', 1)[0]
            if "://" not in source:
                self.assertTrue((root / source).is_file(), source)

    def test_release_checker_exposes_safe_interruption_resume(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "release_check.py"), "--help"],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertIn("--reuse-artifacts", completed.stdout)
        self.assertIn("hash-matched", completed.stdout)
        self.assertIn("--command-timeout", completed.stdout)


if __name__ == "__main__":
    unittest.main()
