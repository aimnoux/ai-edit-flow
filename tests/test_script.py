"""Offline parsing and STT output regressions: python -m unittest discover -s tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
import stt
from cut import script_words
from tts_elevenlabs import parse_blocks


class ScriptTests(unittest.TestCase):
    def test_example_wrapped_block_is_one_paragraph(self):
        blocks = parse_blocks((ROOT / "videos/example/script.md").read_text())
        self.assertEqual(len(blocks["2.1"]), 1)
        self.assertIn("people you see [every] day.", blocks["2.1"][0])
        words = script_words(ROOT / "videos/example/script.md")
        self.assertEqual({p for _, b, p in words if b == "2.1"}, {"2.1/0"})

    def test_paragraphs_and_non_speech_boundaries(self):
        script = """### 1.1 Opening
First wrapped
line.

Second paragraph.
> Editor's note.
Third paragraph.
| table | note |
Fourth paragraph.
#### Camera note
Fifth paragraph.
---
Sixth paragraph.
## 2. Chapter
This is not speech.
### Notes
Neither is this.
### 2.1
Last line.
"""
        self.assertEqual(parse_blocks(script), {
            "1.1": ["First wrapped line.", "Second paragraph.", "Third paragraph.",
                    "Fourth paragraph.", "Fifth paragraph.", "Sixth paragraph."],
            "2.1": ["Last line."],
        })

    def test_empty_block_and_trailing_paragraph(self):
        self.assertEqual(parse_blocks("### 1.1\n> note\n### 1.2\nhello\nworld"),
                         {"1.1": [], "1.2": ["hello world"]})


class SttOutputTests(unittest.TestCase):
    def test_creates_nested_output_directory_before_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new" / "cut" / "stt.json"
            data = {"words": [{"text": "hello", "type": "word"}]}

            def transcribe(*args):
                self.assertTrue(out.parent.is_dir())
                return data

            with patch.object(sys, "argv", ["stt.py", "recording.m4a", str(out)]), \
                    patch.object(stt, "transcribe", side_effect=transcribe):
                stt.main()
            self.assertEqual(json.loads(out.read_text()), data)

    def test_invalid_output_parent_prevents_paid_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not-a-directory"
            blocker.write_text("file")
            with patch.object(sys, "argv", ["stt.py", "recording.m4a", str(blocker / "stt.json")]), \
                    patch.object(stt, "transcribe") as transcribe:
                with self.assertRaises(FileExistsError):
                    stt.main()
                transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
