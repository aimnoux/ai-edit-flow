"""Generated adapter drift and checklist identity are portable, offline contracts."""
from pathlib import Path
import re
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from sync_skills import sync
from contracts import report
from demo import fixture
from scipy.io import wavfile


class AdapterTests(unittest.TestCase):
    def test_committed_compatibility_copy_matches(self):
        self.assertEqual(sync(ROOT, check=True), [])

    def test_check_never_writes_and_sync_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / ".agents/skills/demo/SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("canonical")
            mirror = root / ".claude/skills/demo/SKILL.md"
            mirror.parent.mkdir(parents=True)
            mirror.write_text("stale")
            extra = mirror.parent / "obsolete.md"
            extra.write_text("old")
            with self.assertRaises(ValueError): sync(root, check=True)
            self.assertEqual(mirror.read_text(), "stale")
            sync(root)
            self.assertEqual(mirror.read_bytes(), source.read_bytes())
            self.assertFalse(extra.exists())
            self.assertFalse(mirror.is_symlink())

    @unittest.skipIf(os.name == "nt", "Creating symlink fixtures needs Windows developer mode")
    def test_sync_replaces_compatibility_symlink_without_writing_through_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / ".agents/skills/demo/SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("canonical")
            outside = root / "outside.md"
            outside.write_text("keep")
            mirror = root / ".claude/skills/demo/SKILL.md"
            mirror.parent.mkdir(parents=True)
            mirror.symlink_to(outside)
            with self.assertRaises(ValueError): sync(root, check=True)
            sync(root)
            self.assertFalse(mirror.is_symlink())
            self.assertEqual(outside.read_text(), "keep")
            self.assertEqual(mirror.read_text(), "canonical")

    def test_complete_visual_checklist_preserved(self):
        text = (ROOT / ".agents/skills/review/references/checklist.md").read_text()
        codes = re.findall(r"\*\*([A-Z]+-\d+)\*\*", text)
        self.assertEqual(len(codes), 65)
        self.assertEqual(len(set(codes)), 65)

    def test_shared_contract_report_is_deterministic_and_passes(self):
        a, b = report(), report()
        self.assertEqual(a, b)
        self.assertEqual(a["schema"], 1)
        self.assertTrue(a["contracts"]["review_verdict_binding"])
        self.assertTrue(all(x["input"] == x["output"] for x in a["contracts"]["envelope_lengths"]))

    def test_demo_fixture_is_local_repeatable_and_matches_word_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(ROOT / "vertical/example.md", root)
            first = (root / "voice.wav").read_bytes()
            words = fixture(ROOT / "vertical/example.md", root)
            self.assertEqual(first, (root / "voice.wav").read_bytes())
            rate, audio = wavfile.read(root / "voice.wav")
            self.assertTrue(all(w["e"] <= len(audio) / rate for w in words))
            self.assertFalse(any(w["block"] == "1.0" for w in words))
            self.assertGreater(float(abs(audio).max()), 0)


if __name__ == "__main__":
    unittest.main()
