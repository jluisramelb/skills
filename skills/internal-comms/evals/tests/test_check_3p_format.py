"""Tests for scripts/check_3p_format.py (the deterministic format-check step).

Run from the skill root:
    python -m unittest discover -s evals/tests
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "check_3p_format.py"

spec = importlib.util.spec_from_file_location("check_3p_format", SCRIPT)
check_3p_format = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_3p_format)
check_3p = check_3p_format.check_3p

VALID = (
    "📱 Mobile (Sep 28 – Oct 2, 2026)\n"
    "Progress: Shipped offline mode to 100% of iOS users, lifting crash-free sessions from 99.2% to 99.6%.\n"
    "Plans: Start the Android rollout at 10%.\n"
    "Problems: Blocked on the sync endpoint.\n"
)


class Check3PTests(unittest.TestCase):
    def test_valid_update(self):
        report = check_3p(VALID)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["sections"]["progress"]["sentences"], 1)  # decimals aren't sentence ends

    def test_golden_drafts_are_valid(self):
        for draft in (SKILL_ROOT / "evals" / "files" / "golden").glob("*/04-draft.md"):
            with self.subTest(draft=draft.parent.name):
                self.assertTrue(check_3p(draft.read_text())["valid"])

    def test_header_needs_emoji_and_dates(self):
        report = check_3p(VALID.replace("📱 Mobile (Sep 28 – Oct 2, 2026)", "Mobile update"))
        self.assertFalse(report["valid"])
        self.assertIn("Header must start with an emoji", report["errors"])
        self.assertIn("Header must end with the dates covered in parentheses", report["errors"])

    def test_sections_in_order(self):
        lines = VALID.splitlines()
        swapped = "\n".join([lines[0], lines[2], lines[1], lines[3]])
        self.assertFalse(check_3p(swapped)["valid"])

    def test_too_many_sentences(self):
        long_plans = "Plans: One. Two. Three. Four."
        report = check_3p(VALID.replace("Plans: Start the Android rollout at 10%.", long_plans))
        self.assertIn("'Plans' has 4 sentences (allowed 1-3)", report["errors"])

    def test_markdown_and_extra_lines_rejected(self):
        report = check_3p("**" + VALID + "- extra bullet\n")
        self.assertFalse(report["valid"])
        self.assertTrue(any("markdown" in e for e in report["errors"]))
        self.assertTrue(any("exactly 4" in e for e in report["errors"]))

    def test_empty_draft(self):
        report = check_3p("")
        self.assertFalse(report["valid"])
        self.assertIn("Draft is empty", report["errors"])

    def test_cli_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(VALID)
            outs = []
            for i in range(2):
                out = Path(tmp) / f"out{i}.json"
                subprocess.run([sys.executable, str(SCRIPT), str(draft), str(out)], check=True)
                outs.append(out.read_bytes())
            self.assertEqual(outs[0], outs[1])
            self.assertTrue(json.loads(outs[0])["valid"])


if __name__ == "__main__":
    unittest.main()
