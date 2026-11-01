"""Offline audio/video cut smoke tests using generated tones, never external APIs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
import cut
import pad_chapters


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class CutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / "recording.m4a"
        self.video = self.root / "recording.mp4"
        self.run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-c:a", "aac", str(self.audio))
        # Put audio first to verify that video is selected by stream index, not index 0.
        self.run_ffmpeg("-i", str(self.audio), "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=30:d=3",
                        "-map", "0:a", "-map", "1:v", "-c:a", "copy", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(self.video))
        self.script = self.root / "script.md"
        self.script.write_text("### 1.1\nHello\nworld.\n")
        self.transcript = self.root / "stt.json"
        self.transcript.write_text(json.dumps({"words": [
            {"text": "Hello", "start": 0.25, "end": 0.6, "type": "word"},
            {"text": "[breath]", "start": 1.0, "end": 1.2, "type": "audio_event"},
            {"text": "world", "start": 1.5, "end": 1.8, "type": "word"},
        ]}))

    def run_ffmpeg(self, *args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True)

    def probe(self, path):
        return json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                                          "-of", "json", str(path)], check=True,
                                         capture_output=True, text=True).stdout)

    def run_cut(self, source, name, *extra):
        out = self.root / name
        with patch.object(sys, "argv", ["cut.py", str(source), str(self.transcript), str(self.script), str(out), *extra]):
            cut.main()
        words = json.loads((out / "words.json").read_text())
        self.assertEqual([w["w"] for w in words], ["Hello", "world"])
        self.assertEqual({w["para"] for w in words}, {"1.1/0"})
        self.assertTrue(all(set(w) == {"w", "s", "e", "block", "para"} for w in words))
        self.assertTrue(all(w["s"] < w["e"] for w in words))
        edl = json.loads((out / "edl.json").read_text())
        self.assertEqual(len(edl["segments"]), 2)
        self.assertEqual(edl["dropped"], [])
        target = out / ("voice.wav" if source == self.audio else "rough.mp4")
        self.assertAlmostEqual(float(self.probe(target)["format"]["duration"]), edl["duration"], delta=0.08)
        return out

    def test_audio_only_cut_and_default_chapter_padding(self):
        out = self.run_cut(self.audio, "audio-cut")
        self.assertFalse((out / "rough.mp4").exists())
        streams = self.probe(out / "voice.wav")["streams"]
        self.assertEqual([s["codec_type"] for s in streams], ["audio"])
        self.assertEqual(streams[0]["sample_rate"], "48000")
        self.assertEqual(streams[0]["channels"], 1)
        with patch.object(sys, "argv", ["pad_chapters.py", "fixture", "--cut", str(out)]), \
                patch.object(pad_chapters, "video_cfg", return_value={"head": {}, "tail": {}, "end": 0.1}):
            pad_chapters.main()
        self.assertTrue((out / "pad/voice.wav").is_file())
        self.assertTrue((out / "pad/rough.mp4").is_file())
        self.assertEqual(json.loads((out / "pad/words.json").read_text()),
                         json.loads((out / "words.json").read_text()))

    def test_video_cut_preserves_video_and_words_contract(self):
        out = self.run_cut(self.video, "video-cut")
        self.assertEqual({s["codec_type"] for s in self.probe(out / "rough.mp4")["streams"]}, {"audio", "video"})

    def test_cleaned_audio_override_still_outputs_audio_only(self):
        out = self.run_cut(self.audio, "clean-cut", "--audio", str(self.audio))
        self.assertEqual([s["codec_type"] for s in self.probe(out / "voice.wav")["streams"]], ["audio"])

    def test_reusing_cut_directory_does_not_keep_stale_playable_output(self):
        out = self.run_cut(self.audio, "reused-cut")
        self.assertTrue((out / "voice.wav").exists())
        self.run_cut(self.video, "reused-cut")
        self.assertFalse((out / "voice.wav").exists())
        self.assertTrue((out / "rough.mp4").exists())


if __name__ == "__main__":
    unittest.main()
