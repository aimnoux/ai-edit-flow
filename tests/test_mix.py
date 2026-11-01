"""Short music fades, loop crossfades and effect wrapping, without browser or paid services."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import mix
import mix_piece


class MusicTrackTests(unittest.TestCase):
    def check_fades(self, seconds):
        with patch.object(mix, "load", return_value=np.ones((mix.SR // 8, 2))), \
                patch.object(mix, "lufs", return_value=-20.0):
            music = mix.music_track("synthetic.wav", round(seconds * mix.SR), db=0)
        self.assertEqual(music.shape, (round(seconds * mix.SR), 2))
        self.assertTrue(np.isfinite(music).all())
        self.assertFalse(music[0].any())
        self.assertFalse(music[-1].any())
        self.assertGreater(music.max(), 0)

    def test_quarter_second_music_fades(self):
        self.check_fades(0.25)

    def test_one_second_music_fades(self):
        self.check_fades(1.0)

    def test_three_second_music_fades(self):
        self.check_fades(3.0)

    def test_five_second_music_fades(self):
        self.check_fades(5.0)


class MixPieceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def check_piece(self, seconds, loop, source_seconds):
        n = round(seconds * mix.SR)
        raw = np.ones((round(source_seconds * mix.SR), 2))
        # An effect lasting through two seams must be summed into the first sample three times.
        def effects(_marks, size):
            fx = np.zeros((size, 2))
            fx[0] = 1
            if loop:
                fx[n] = 2
                fx[2 * n] = 3
            return fx, 1, SimpleNamespace(missing=set())

        cues = self.root / "cues.json"
        cues.write_text("[]")
        argv = ["mix_piece.py", "test", "video.mp4", "voice.wav", "music.wav", "out.mp4",
                "--cues", str(cues), *(["--loop"] if loop else [])]
        replacements = {
            "BUILD": self.root, "duration": lambda _: seconds, "load": lambda _: raw,
            "lufs": lambda _: -25.0, "voice_track": lambda *_: np.zeros((n, 2)),
            "finalize": lambda *_args, **_kwargs: (-14, -2, 0), "place": effects,
        }
        with ExitStack() as stack:
            for name, value in replacements.items():
                stack.enter_context(patch.object(mix_piece, name, value))
            stack.enter_context(patch.object(sys, "argv", argv))
            mix_piece.main()
        sr, track = wavfile.read(self.root / "test-premix.wav")
        self.assertEqual(sr, mix.SR)
        self.assertEqual(track.shape, (n, 2))
        self.assertTrue(np.isfinite(track).all())
        self.assertAlmostEqual(float(track[0, 0]), 7 if loop else 1)
        if loop:
            self.assertGreaterEqual(track[n // 2, 0], 1)
        else:
            self.assertEqual(track[-1, 0], 0)

    def test_one_second_piece_fades(self):
        self.check_piece(1, False, 3)

    def test_quarter_second_piece_fades(self):
        self.check_piece(0.25, False, 3)

    def test_quarter_second_loop_crossfade_and_effect_wrap(self):
        self.check_piece(0.25, True, 3)

    def test_matching_half_second_music_loop_and_effect_wrap(self):
        self.check_piece(0.5, True, 0.5)

    def check_ffmpeg_piece(self, seconds, loop):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg and ffprobe are needed for the offline integration test")
        video, voice, music, out = [self.root / name for name in ("video.mp4", "voice.wav", "music.wav", "out.mp4")]
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=s=16x16:r=24:d={seconds}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
        wavfile.write(voice, mix.SR, np.zeros(round(seconds * mix.SR), dtype=np.float32))
        tone = (0.05 * np.sin(2 * np.pi * 440 * np.arange(3 * mix.SR) / mix.SR)).astype(np.float32)
        wavfile.write(music, mix.SR, tone)
        marks = self.root / "cues.json"
        marks.write_text("[]")
        script = Path(mix_piece.__file__).resolve()
        args = ["test", str(video), str(voice), str(music), str(out), "--cues", str(marks)]
        if loop:
            args.append("--loop")
        # main writes its scratch file under BUILD; redirect that path into the fixture.
        code = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv.pop(1)); "
                "import mix_piece; mix_piece.BUILD=Path(sys.argv.pop(1)); mix_piece.main()")
        command = [sys.executable, "-c", code, str(script.parent), str(self.root), *args]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)]))
        self.assertEqual({s["codec_type"] for s in metadata["streams"]}, {"audio", "video"})
        audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        self.assertAlmostEqual(float(audio["duration"]), seconds, delta=0.05)

    def test_real_ffmpeg_one_second_piece_with_frozen_cues(self):
        self.check_ffmpeg_piece(1, False)

    def test_real_ffmpeg_quarter_second_loop_with_frozen_cues(self):
        self.check_ffmpeg_piece(0.25, True)


if __name__ == "__main__":
    unittest.main()
