from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicContractTests(unittest.TestCase):
    def test_readme_explains_name_blessing_and_three_gates(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "# Uriel — The Evidence Lantern",
            "## Why the name?",
            "light, wisdom, and illumination",
            "## The Blessing of Uriel — earned, never granted",
            "## The Three Gates",
            "Gate 1 — Novelty & Clarity",
            "Gate 2 — Evidence & Citation",
            "Gate 3 — Adversarial Integrity",
            "does **not** mean",
            "It is not a claim of absolute truth.",
            ".uriel/REMINDERS.md",
        )
        for phrase in required:
            self.assertIn(phrase, text, phrase)

    def test_name_explanation_is_free_of_denominational_wording(self) -> None:
        documents = (ROOT / "README.md", ROOT / "docs" / "WHY_URIEL.md")
        forbidden = (
            "Jewish",
            "Christian",
            "apocryphal",
            "God is my light",
            "faith and no faith",
            "archangel",
            "doctrine",
            "canonical status",
        )
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{document.name}: {phrase}")

    def test_readme_local_images_exist(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for source in re.findall(r'<img[^>]+src="([^"]+)"', text):
            if "://" not in source:
                self.assertTrue((ROOT / source).is_file(), source)

    def test_local_markdown_links_resolve(self) -> None:
        documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
        broken: list[str] = []
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for raw in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text):
                target = raw.strip().split()[0].strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                candidate = (document.parent / target).resolve()
                if not candidate.exists():
                    broken.append(f"{document.relative_to(ROOT).as_posix()} -> {target}")
        self.assertEqual([], broken)

    def test_ci_declares_explicit_cross_platform_contract(self) -> None:
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for token in (
            "ubuntu-latest",
            "windows-latest",
            "macos-15-intel",
            "macos-arm64-smoke",
            '"3.9"',
            '"3.10"',
            '"3.11"',
            '"3.12"',
            '"3.13"',
            '"3.14"',
            "python -m pip check",
            "PYTHONUTF8",
            "persist-credentials: false",
            "Uriel.ps1",
        ):
            self.assertIn(token, text, token)

    def test_powershell_wrapper_preserves_single_executable_path(self) -> None:
        text = (ROOT / "scripts" / "Uriel.ps1").read_text(encoding="utf-8")
        self.assertIn("$python = @(Get-UrielPythonCommand)", text)
        self.assertIn("$exe = [string]$python[0]", text)
        self.assertNotIn("return $LASTEXITCODE", text)

    def test_public_metadata_and_private_material_boundary(self) -> None:
        expected = "https://github.com/dmonsta86/uriel"
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn(expected, pyproject)
        self.assertIn(expected, citation)
        forbidden = (
            "OPENAI_CODEX_FOR_OSS_APPLICATION.md",
            "PUBLISH_TO_GITHUB.cmd",
            "START_HERE.md",
            "docs/PUBLISH_TO_GITHUB.md",
        )
        for relative in forbidden:
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_readme_describes_lifecycle_flow(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for token in (
            "## From a question to a submission",
            "Uriel Seed",
            "Uriel Workbench + Data Desk",
            "Paper Builder",
            "Three-Gate audit",
            "Submission or revision packet",
        ):
            self.assertIn(token, text, token)

    def test_readme_lens_is_advisory_and_cannot_bless(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("No installation: Uriel Lens", text)
        self.assertIn("Lens is advisory", text)
        self.assertIn("issue The Blessing of Uriel", text)

    def test_readme_packet_and_budget_sections(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Guided submission and revision", text)
        self.assertIn("one instruction file", text)
        self.assertIn("Designed for limited budgets", text)
        self.assertIn("resumable context packets", text)
        self.assertIn("consider privacy before uploading", text)

    def test_lifecycle_doc_covers_all_planned_surfaces(self) -> None:
        text = (ROOT / "docs" / "LIFECYCLE.md").read_text(encoding="utf-8")
        for token in (
            "Uriel Lens",
            "Uriel Seed",
            "Research Workbench",
            "Data Desk",
            "Paper Builder",
            "Submission Guide",
            "Publication authority",
            "Generation and checkpoint model",
            "AI and privacy boundary",
            "00_READ_ME_FIRST.md",
            "submission_authorized",
            "NEXT_PROMPT.txt",
        ):
            self.assertIn(token, text, token)

    def test_lifecycle_doc_preserves_blessing_boundary(self) -> None:
        text = (ROOT / "docs" / "LIFECYCLE.md").read_text(encoding="utf-8")
        self.assertIn("cannot issue a Blessing", text)
        self.assertIn("deterministic audit and Blessing boundary remain authoritative", text)
        self.assertNotIn("AI can grant", text)

    def test_kit_material_never_entered_public_tree(self) -> None:
        for relative in sorted((ROOT / "docs").glob("*.md")):
            text = relative.read_text(encoding="utf-8", errors="replace")
            for secret in (
                "RESEARCH_LIFECYCLE_UPGRADE_KIT",
                "LOCAL_AI_MASTER_IMPLEMENTATION_PROMPT",
                "C:\\Users\\Taller",
                "uriel-work-20260806",
            ):
                self.assertNotIn(secret, text, f"{relative.name}: {secret}")


if __name__ == "__main__":
    unittest.main()
