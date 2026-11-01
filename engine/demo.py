#!/usr/bin/env python3
"""Build the existing vertical example with synthetic word tones; no speech service or AI calls.

After setup: python engine/demo.py. --prepare-only builds audio/timing/HTML without a browser.
This is an intentionally rough 10 fps example, not speech or an approved production render.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, HERE, RENDERS, ROOT, SR
from render import render
from voice import paragraphs
import vertical


def fixture(script, directory):
    """Word tones with known boundaries replace a paid transcription/generation round trip."""
    words, pieces, position = [], [], 0
    for p in paragraphs(script):
        for text in p["text"].split():
            count = round(0.12 * SR)
            t = np.arange(count) / SR
            tone = (0.12 * np.sin(2 * np.pi * 330 * t) * np.sin(np.pi * np.arange(count) / count) ** 2).astype(np.float32)
            words.append({"w": text, "block": p["block"], "para": f"{p['block']}/{p['para']}",
                          "s": position / SR, "e": (position + count) / SR})
            pieces.extend((tone, np.zeros(round(0.03 * SR), dtype=np.float32)))
            position += count + len(pieces[-1])
    directory.mkdir(parents=True, exist_ok=True)
    wavfile.write(directory / "voice.wav", SR, np.concatenate(pieces))
    (directory / "words.json").write_text(json.dumps(words, indent=1), encoding="utf-8")
    return words


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    script = ROOT / "vertical/example.md"
    cut = BUILD / "demo/cut"
    fixture(script, cut)
    vertical.cmd_build(str(script), "1", "yt", "--cut", str(cut))
    cid = "example-s1-yt"
    if args.prepare_only:
        print(f"Prepared {HERE / (cid + '.html')} (no browser or API calls)")
        return
    output = RENDERS / "demo"
    output.mkdir(parents=True, exist_ok=True)
    video, result = output / "video.mp4", output / "demo.mp4"
    log = BUILD / "demo/render.log"
    # One owned software renderer, 10 fps, with a finite wrapper deadline; no production batch.
    completed = render(cid, video, "--fps", "10", "--quality", "draft", "--workers", "1",
                       "--no-browser-gpu", "--quiet", timeout=600)
    log.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
    if completed.returncode:
        raise SystemExit(f"Demo render failed; see {log}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i",
                    str(BUILD / "example" / f"{cid}-voice.wav"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(result)],
                   check=True, timeout=60)
    print(f"Synthetic demo (10 fps, word tones): {result}")


if __name__ == "__main__":
    main()
