#!/usr/bin/env python3
"""Mix of one composition (a vertical video, a chapter, a test piece): voice + effects at the cues + music.

  python3 engine/mix_piece.py <composition id> <video.mp4> <voice.wav> <music|-> <out.mp4> [--cues cues.json] [--loop] [--music-db -25]

Levels as in mix.py: voice -16 LUFS, music about -25 LUFS without voice and 9 dB lower under it, the
final -14 LUFS with true peak at -1.5 dBTP or lower after AAC. `-` instead of music: no music. --cues:
frozen cues instead of reading the composition (before/after comparisons on the same cues).
Without voice and without music the final is quieter, -20 LUFS: effects alone at -14 would hit.
--loop: a looping piece; effect tails past the end wrap to the beginning so the seam has no cut.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, SR, duration  # noqa: E402
from mix import cues, duck, finalize, load, lufs, place, voice_track  # noqa: E402

MUSIC_LUFS = -25.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cid"); ap.add_argument("video"); ap.add_argument("voice"); ap.add_argument("music"); ap.add_argument("out")
    ap.add_argument("--cues")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--music-db", type=float, default=MUSIC_LUFS)
    a = ap.parse_args()
    marks = json.loads(Path(a.cues).read_text(encoding="utf-8")) if a.cues else cues(a.cid)
    n = int(duration(a.video) * SR)
    fit = lambda x: np.pad(x[:n], ((0, max(0, n - len(x))), (0, 0)))

    voice = voice_track(a.voice, n)
    silent = not np.abs(voice).max() > 0
    tail = 4 * SR if a.loop else 0
    fx, count, foley = place(marks, n + tail)
    if tail:
        fx[:tail] += fx[n:]
    fx = fx[:n]

    music = np.zeros((n, 2))
    if a.music != "-":
        raw = load(a.music) * 10 ** ((a.music_db - lufs(a.music)) / 20)
        xf = int(1.0 * SR)
        if a.loop and abs(len(raw) - n) < SR // 50:
            music = fit(raw)   # the track is already a loop of the piece's length: no crossfade, no fades
        elif a.loop and len(raw) >= n + xf:
            music = raw[:n].copy()   # a second of the track past the end crossfades onto the beginning
            w = np.linspace(0, np.pi / 2, xf)[:, None]
            music[:xf] = music[:xf] * np.sin(w) + raw[n:n + xf] * np.cos(w)
        else:
            music = fit(raw)
            fi, fo = int(0.8 * SR), int(2.0 * SR)
            music[:fi] *= np.linspace(0, 1, fi)[:, None]
            music[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
        music = duck(music, voice)

    BUILD.mkdir(exist_ok=True)
    pre = BUILD / f"{a.cid}-premix.wav"
    wavfile.write(pre, SR, (voice + fx + music).astype(np.float32))
    i, tp, lra = finalize(pre, a.out, a.video, **({"target": -20.0} if silent and a.music == "-" else {}))
    miss = f"; no file in style/sound for: {', '.join(sorted(foley.missing))}" if foley.missing else ""
    print(f"{a.out}: effects {count}{miss}; result {i:.1f} LUFS, true peak {tp:.1f} dBTP, LRA {lra:.1f} LU")


if __name__ == "__main__":
    main()
