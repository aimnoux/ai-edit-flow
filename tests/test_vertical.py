"""Offline regressions for selecting one vertical from a live batch recording."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import vertical


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is needed to read the synthetic voice recording")
class VerticalCutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reading = self.root / "batch.md"
        self.reading.write_text("""## 1. First
### 1.0
slate
### 1.1
[alpha]

[beta]
### 1.2
[gamma]
### 1.8
[youtube]

[extra]
### 1.9
[instagram]
## 2. Other
### 2.0
slate
### 2.1
other
### 2.8
bye
""")
        labels = [("1.0/0", "slate"), ("1.1/0", "alpha"), ("1.1/1", "beta"),
                  ("1.2/0", "gamma"), ("1.8/0", "youtube"), ("1.8/1", "extra"),
                  ("1.9/0", "instagram"), ("2.0/0", "slate"), ("2.1/0", "other"), ("2.8/0", "bye")]
        self.cut = self.root / "cut"
        self.cut.mkdir()
        audio = np.zeros(10 * vertical.SR, dtype=np.float32)
        words, self.levels = [], {}
        for i, (para, text) in enumerate(labels):
            start, end = i + 0.2, i + 0.6
            level = (i + 1) / 20
            audio[round(start * vertical.SR):round(end * vertical.SR)] = level
            words.append({"para": para, "block": para.split("/")[0], "w": text, "s": start, "e": end})
            self.levels[text] = level
        (self.cut / "words.json").write_text(json.dumps(words))
        wavfile.write(self.cut / "voice.wav", vertical.SR, audio)
        self.result = {}

        def composition(project, roll, platform, total, blocks, loop):
            self.result.update(total=total, blocks=blocks, loop=loop)
            return f"{project}-s{roll}-{platform}"

        for name, value in [("BUILD", self.root / "build"), ("sync_style", lambda: None),
                            ("write_composition", composition)]:
            guard = patch.object(vertical, name, value)
            guard.start()
            self.addCleanup(guard.stop)

    def check_platform(self, platform, ending):
        vertical.cmd_build(str(self.reading), "1", platform, "--cut", str(self.cut))
        sr, track = wavfile.read(vertical.BUILD / "batch" / f"batch-s1-{platform}-voice.wav")
        self.assertEqual(sr, vertical.SR)
        paras = [p for block in self.result["blocks"].values() for p in block]
        expected_words = ["alpha", "beta", "gamma", *ending]
        self.assertEqual([p["words"][0]["w"] for p in paras], expected_words)
        self.assertEqual(paras[0]["s"], vertical.LEAD)
        for p in paras:
            word = p["words"][0]
            center = round((word["s"] + word["e"]) / 2 * sr)
            self.assertAlmostEqual(float(track[center]), self.levels[word["w"]], places=6)
            self.assertEqual(p["triggers"], [{"w": word["w"], "t": word["s"]}])
            self.assertLessEqual(p["s"], word["s"])
            self.assertLess(word["s"], word["e"])
            self.assertLessEqual(word["e"], p["e"])
        for i, base in enumerate([vertical.GAP_PARA, vertical.GAP_BLOCK, vertical.GAP_END]):
            name = ["1.1-0", "1.1-1", "1.2-0"][i]
            self.assertAlmostEqual(paras[i + 1]["s"] - paras[i]["e"], vertical.gap(base, name), delta=0.002)
        self.assertAlmostEqual(self.result["total"] - paras[-1]["e"], vertical.TAIL, delta=1 / vertical.FPS)
        self.assertEqual(len(track), int(self.result["total"] * sr))
        self.assertFalse(np.any(track[:round(vertical.LEAD * sr)]))
        self.assertFalse(np.any(track[round(paras[-1]["e"] * sr):]))
        heard = set(np.rint(track[track > 0] * 1000).astype(int))
        self.assertEqual(heard, {round(self.levels[w] * 1000) for w in expected_words})

    def test_cut_selects_youtube_audio_and_remaps_timing(self):
        self.check_platform("yt", ["youtube", "extra"])

    def test_cut_selects_instagram_audio_and_remaps_timing(self):
        self.check_platform("ig", ["instagram"])

    def test_cut_selects_tiktok_audio_and_remaps_timing(self):
        self.check_platform("tt", ["instagram"])

    def test_cut_loop_omits_endings_and_clips_to_explicit_duration(self):
        vertical.cmd_build(str(self.reading), "1", "yt", "--cut", str(self.cut), "--dur=0.5")
        _, audio = wavfile.read(vertical.BUILD / "batch" / "batch-s1-yt-voice.wav")
        self.assertIs(self.result["loop"], True)
        self.assertNotIn("end", self.result["blocks"])
        self.assertEqual(len(audio), int(round(0.5 * vertical.FPS) / vertical.FPS * vertical.SR))
        self.assertAlmostEqual(float(np.max(audio)), 0.1, places=6)

    def test_cut_ending_falls_back_to_youtube(self):
        self.reading.write_text(self.reading.read_text().replace("### 1.9\n[instagram]\n", ""))
        vertical.cmd_build(str(self.reading), "1", "ig", "--cut", str(self.cut))
        self.assertEqual([p["words"][0]["w"] for p in self.result["blocks"]["end"]], ["youtube", "extra"])

    def test_cut_missing_selected_paragraphs_fails_clearly(self):
        (self.cut / "words.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "no words for video 1"):
            vertical.cmd_build(str(self.reading), "1", "yt", "--cut", str(self.cut))

    def test_render_keeps_music_path_relative_to_caller(self):
        composition = self.root / "batch-s1-yt.html"
        composition.write_text('{"loop": false}')
        with patch.object(vertical, "HERE", self.root), patch.object(vertical, "RENDERS", self.root / "renders"), \
                patch.object(vertical.subprocess, "run") as run:
            vertical.cmd_render("batch-s1-yt", "--mix-only", "--music", "fixtures/music.wav")
        command = run.call_args.args[0]
        self.assertIn(str(Path("fixtures/music.wav").resolve()), command)
        self.assertNotIn("fixtures/music.wav", command)


if __name__ == "__main__":
    unittest.main()
