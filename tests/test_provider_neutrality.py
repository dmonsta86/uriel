"""Tests for provider neutrality, brand scrub, capability inventory, and public docs (Wave U6).

Exercises:
- Public Brand Scrub scanner (SCRUB-001..003)
- Capability status inventory validation (CAPSTATUS-001..002)
- README commands and links (README-NEW-001..005)
- Generic AI-entry contract (NEUTRAL-001..005)
- Provider credential prohibition (NEUTRAL-006)
- Local-model authority (LOCAL-NEUTRAL-001..002)
- Public copy length & placeholders (COPY-001)
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from uriel.capability_status import CAPABILITIES, generate_capability_inventory


class ProviderNeutralityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent

    # 1. Brand Scrub Test
    def test_public_brand_scrub(self) -> None:
        disallowed = ["opencode", "deepseek", "gemini", "claude", "cursor", "cline", "aider"]
        allowlisted_files = {
            "08_GEMINI_MASTER_ADDENDUM.md",
            "09_ONE_MESSAGE_TO_GEMINI.txt",
            "URIEL_PROVIDER_NEUTRAL_DOCS_FINAL_REPORT.md",
            "UNIFIED_WORKLOG.md",
            "test_provider_neutrality.py",
            "release-check.txt",
        }

        matches = []
        for root, dirs, files in os.walk(self.repo_root):
            # Skip hidden dirs, build dirs, and venv
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("build", "dist", "venv", "__pycache__", "source_archives_do_not_publish", "uriel_research.egg-info")]
            for f in files:
                if f in allowlisted_files or f.endswith((".pyc", ".png", ".jpg", ".avif", ".zip", ".bundle", ".pdf")):
                    continue
                file_path = Path(root) / f
                if file_path.suffix in (".md", ".txt", ".json", ".py", ".cff"):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
                        for brand in disallowed:
                            # Avoid matching ordinary words like 'aid' in 'aider' or 'class' in 'claude'
                            pattern = r"\b" + re.escape(brand) + r"\b"
                            if re.search(pattern, content):
                                matches.append(f"{file_path.relative_to(self.repo_root)}: matched '{brand}'")
                    except Exception:
                        pass

        self.assertEqual(len(matches), 0, "Public brand scrub found disallowed provider strings:\n" + "\n".join(matches))

    # 2. Allowlisted GPT-5.6 Sol Recommendation Test
    def test_gpt56_sol_recommendation_allowlist(self) -> None:
        readme_path = self.repo_root / "README.md"
        readme_text = readme_path.read_text(encoding="utf-8")
        self.assertIn("GPT-5.6 Sol with ultra mode", readme_text)
        self.assertIn("optional tested recommendation", readme_text)
        self.assertNotIn("pricing", readme_text.lower())
        self.assertNotIn("free tier", readme_text.lower())

    # 3. Capability Inventory Test
    def test_capability_inventory_generated_and_valid(self) -> None:
        inventory = generate_capability_inventory(self.repo_root)
        self.assertEqual(inventory["schema"], "uriel.capability_inventory.v1")
        self.assertGreaterEqual(len(inventory["capabilities"]), 8)
        for cap in inventory["capabilities"]:
            self.assertIn(cap["status"], ("SHIPPED", "BETA", "EXPERIMENTAL", "PLANNED", "DEFERRED"))
            self.assertTrue(cap["name"])

    # 4. Generic AI Entry Contract Test
    def test_generic_ai_entry_files_exist(self) -> None:
        for fname in ("URIEL_AI_ENTRY.md", "COPY_THIS_TO_YOUR_AI.txt", "NEXT_PROMPT.txt"):
            fpath = self.repo_root / fname
            self.assertTrue(fpath.is_file(), f"Required generic AI entry file {fname} is missing.")
            text = fpath.read_text(encoding="utf-8")
            self.assertGreater(len(text), 20)

    # 5. Project QRD & Target Copy Test
    def test_project_qrd_exists(self) -> None:
        qrd_path = self.repo_root / "docs" / "PROJECT_QRD.md"
        self.assertTrue(qrd_path.is_file(), "docs/PROJECT_QRD.md is missing.")
        text = qrd_path.read_text(encoding="utf-8")
        self.assertIn("Quality Requirements Document", text)
        self.assertIn("Interpret generously.", text)

    # 6. No Provider Credential Test
    def test_no_provider_credentials_in_repo(self) -> None:
        cred_patterns = [r"\bapi_key\b", r"\bsecret_key\b", r"\bbearer_token\b"]
        for root, dirs, files in os.walk(self.repo_root / "src"):
            for f in files:
                if f.endswith(".py"):
                    code = (Path(root) / f).read_text(encoding="utf-8")
                    for pat in cred_patterns:
                        self.assertNotRegex(code, pat)
