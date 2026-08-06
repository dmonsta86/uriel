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
            "START_HERE.md",
            "scripts/Uriel.ps1",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            "docs/PUBLISH_TO_GITHUB.md",
            "docs/MAINTAINER_HANDOFF.md",
            "scripts/publish_github.ps1",
            "scripts/publish_github.sh",
            "PUBLISH_TO_GITHUB.cmd",
            "scripts/build_distributions.py",
            "scripts/configure_repository.py",
            "scripts/make_checksums.py",
            "OPENAI_CODEX_FOR_OSS_APPLICATION.md",
            "src/uriel/core.py",
            "src/uriel/demo.py",
            "src/uriel/audit.py",
            "src/uriel/blessing.py",
            "src/uriel/cli.py",
        ]
        self.assertEqual([], [item for item in required if not (root / item).is_file()])

    def test_publishers_bind_metadata_and_verify_before_push(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("scripts/publish_github.ps1", "scripts/publish_github.sh"):
            text = (root / name).read_text(encoding="utf-8")
            configure_at = text.find("configure_repository.py")
            check_at = text.find("release_check.py")
            push_at = text.find("git push")
            self.assertGreaterEqual(configure_at, 0, name)
            self.assertGreater(check_at, configure_at, name)
            self.assertGreater(push_at, check_at, name)
            self.assertIn("Uriel Bootstrap", text, name)
            self.assertIn("uriel-bootstrap@example.invalid", text, name)

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

    def test_repository_configurator_is_idempotent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "pyproject.toml").write_text(
                "[project]\nname = \"uriel-research\"\n\n[project.scripts]\nuriel = \"uriel.cli:main\"\n",
                encoding="utf-8",
            )
            (target / "CITATION.cff").write_text(
                "cff-version: 1.2.0\ntitle: \"Uriel\"\ndate-released: 2026-08-06\n",
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(root / "scripts" / "configure_repository.py"),
                "--repository",
                str(target),
                "--slug",
                "example/uriel",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            first_pyproject = (target / "pyproject.toml").read_text(encoding="utf-8")
            first_citation = (target / "CITATION.cff").read_text(encoding="utf-8")
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first_pyproject, (target / "pyproject.toml").read_text(encoding="utf-8"))
            self.assertEqual(first_citation, (target / "CITATION.cff").read_text(encoding="utf-8"))
            self.assertIn('Repository = "https://github.com/example/uriel"', first_pyproject)
            self.assertIn('repository-code: "https://github.com/example/uriel"', first_citation)


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
