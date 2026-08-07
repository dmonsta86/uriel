from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_public_identity import main as check_public_identity_main

ROOT = Path(__file__).resolve().parents[1]


class PublicIdentityTests(unittest.TestCase):
    def test_public_identity_check_passes(self) -> None:
        exit_code = check_public_identity_main()
        self.assertEqual(exit_code, 0, "Public identity check failed.")
