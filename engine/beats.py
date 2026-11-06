#!/usr/bin/env python3
"""Hits and the drop of a music track as marks for a scene: the picture is built on them, the track is never moved.

  python engine/beats.py track.mp3 engine/scenes/<slug>/beats.json [--sheet marks.png] [--click check.wav] [--max 48]

Writes {"track", "duration", "bpm", "marks": [{"t", "name": "hit" | "drop", "strength"}]}. --sheet draws the marks on
the waveform to look at, --click puts a click on every mark to check by ear. Marks are an estimate: listen, then edit
the JSON by hand; a scene reads it through markTimes() in lib/motion.mjs.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import find_peaks, stft

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import load_audio  # noqa: E402
from common import SR  # noqa: E402

HOP = 512


def analyse(x, limit=48):
    """Hits are peaks of spectral flux; the drop is the largest jump of bass energy between two seconds around a moment."""
    _, _, spec = stft(x, SR, nperseg=2048, noverlap=2048 - HOP, boundary=None, padded=False)
    mag = np.abs(spec)
    rate = SR / HOP
    flux = np.maximum(np.diff(np.log1p(mag * 100), axis=1), 0).sum(0)
    flux = flux / (flux.max() or 1)
    peaks, props = find_peaks(flux, height=max(np.median(flux) * 3, 0.1), distance=int(0.12 * rate))
    order = np.argsort(props["peak_heights"])[::-1][:limit]
    # Frame k of the difference sits between windows k and k + 1, centered 1024 samples into the first of them.
    times = {round(float((peaks[i] + 1) / rate + 1024 / SR), 3): round(float(props["peak_heights"][i]), 3) for i in order}
    marks = [{"t": t, "name": "hit", "strength": s} for t, s in sorted(times.items())]

    bpm = None
    if len(flux) > rate * 4:
        ac = np.correlate(flux - flux.mean(), flux - flux.mean(), "full")[len(flux) - 1:]
        lo, hi = int(rate * 60 / 180), int(rate * 60 / 60)
        bpm = round(float(60 * rate / (lo + np.argmax(ac[lo:hi]))), 1)

    bass = mag[: max(2, int(150 / (SR / 2048)))].sum(0)
    win = int(2 * rate)
    if len(bass) > 2 * win and marks:
        csum = np.concatenate([[0], np.cumsum(bass)])
        k = np.arange(win, len(bass) - win)
        rise = (csum[k + win] - csum[k]) - (csum[k] - csum[k - win])
        at = (k[np.argmax(rise)] / rate) + 1024 / SR
        near = min(marks, key=lambda m: abs(m["t"] - at))["t"]   # the drop lands on the nearest real hit
        marks.append({"t": near if abs(near - at) < 0.6 else round(float(at), 3), "name": "drop", "strength": 1.0})
    return bpm, sorted(marks, key=lambda m: (m["t"], m["name"]))


def sheet(x, marks, path, w=1600, h=320):
    edges = np.linspace(0, len(x), w + 1).astype(int)
    peak = np.array([np.abs(x[a:b]).max() if b > a else 0 for a, b in zip(edges, edges[1:])])
    img = Image.new("RGB", (w, h), (20, 20, 20))
    d = ImageDraw.Draw(img)
    for i, v in enumerate(peak / (peak.max() or 1)):
        d.line([(i, h / 2 - v * h * 0.45), (i, h / 2 + v * h * 0.45)], fill=(150, 150, 150))
    for m in marks:
        px = m["t"] * SR / len(x) * w
        d.line([(px, 0), (px, h)], fill=(255, 212, 0) if m["name"] == "drop" else (255, 255, 255), width=3 if m["name"] == "drop" else 1)
    img.save(path)


def clicks(x, marks, path):
    n = int(0.03 * SR)
    tick = (0.6 * np.sin(2 * np.pi * 2000 * np.arange(n) / SR) * np.linspace(1, 0, n)).astype(np.float32)
    out = x * 0.6
    for m in marks:
        i = int(m["t"] * SR)
        out[i:i + n] += tick[: len(out[i:i + n])]
    wavfile.write(path, SR, np.clip(out, -1, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("track")
    ap.add_argument("out")
    ap.add_argument("--sheet")
    ap.add_argument("--click")
    ap.add_argument("--max", type=int, default=48, help="keep this many strongest hits")
    a = ap.parse_args()
    x = load_audio(a.track)
    bpm, marks = analyse(x, a.max)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"track": Path(a.track).name, "duration": round(len(x) / SR, 3), "bpm": bpm, "marks": marks}, indent=1), encoding="utf-8")
    if a.sheet:
        sheet(x, marks, a.sheet)
    if a.click:
        clicks(x, marks, a.click)
    drop = next((m["t"] for m in marks if m["name"] == "drop"), None)
    print(f"{out}: {len(marks)} marks, bpm {bpm}, drop {drop}")


if __name__ == "__main__":
    main()
