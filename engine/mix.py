#!/usr/bin/env python3
"""Mix of a horizontal video: voice + sound effects at the scene cues + music with ducking.

  python3 engine/mix.py <slug> [--music track.mp3] [--music-db -15] [--duck 9]    -> engine/build/<slug>/mix.wav

Scenes write their cues into <script id="cues"> (kit.js sfx() -> finish.js); here headless Chrome reads
them from every chapter composition and shifts them by the chapter start. Levels: voice -16 LUFS, the
final -14 LUFS with true peak at -1.5 dBTP or lower after the codec (--target, --tp to change).
The sound bank (`Foley`), cue placement (`place`) and the final loudness (`finalize`) are shared with
mix_piece.py and compare.py. Sounds come from style/sound/ (see style/sound/README.md); a cue without a
file is skipped and counted.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, HERE, SR, STYLE, chrome_cmd, sounds  # noqa: E402

BANK = STYLE / "sound"
SFX_DB = -2.0        # overall effects level under the voice
MUSIC_DB = -15.0     # music: about -22 LUFS without voice after normalization
DUCK_DB = 9.0        # how far the music dips while the voice speaks
VOICE_LUFS = -16.0
TARGET_I, TARGET_TP = -14.0, -2.0   # TP with a margin: AAC adds 0.2-0.4 dB, we keep the result at -1.5 or lower


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def lufs(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    return float(found[-1]) if found else -70.0


def cues(cid):
    """Sound cues of a composition, as finish.js filtered them."""
    html = subprocess.run(chrome_cmd(
                           "--virtual-time-budget=4000", "--dump-dom", (HERE / f"{cid}.html").resolve().as_uri()),
                          capture_output=True, text=True, timeout=180).stdout
    m = re.search(r'<script type="application/json" id="cues">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else []


def _u(*key):
    """Deterministic number in -1..1 from a key (hash() changes between runs)."""
    h = hashlib.md5(":".join(map(str, key)).encode()).digest()
    return int.from_bytes(h[:4], "little") / 2 ** 31 - 1


def _peak100(x):
    k = min(len(x), int(0.1 * SR))
    return 10 * np.log10(np.convolve(x.mean(1) ** 2, np.ones(k) / k, mode="valid").max() + 1e-15)


def repitch(x, semis):
    """Pitch by +-semitones through resampling (a bit shorter or longer, like a real take)."""
    if abs(semis) < 1e-3:
        return x
    idx = np.arange(0, len(x) - 1, 2 ** (semis / 12))
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1)


def trim(x, q):
    """A cue with `len`: the sound is cut to len seconds with a fade on the second half."""
    if not q.get("len"):
        return x
    k = min(len(x), int(q["len"] * SR))
    x = x[:k].copy()
    f = k // 2
    x[k - f:] *= np.linspace(1, 0, f)[:, None]
    return x


class Foley:
    """The sound bank. A cue name maps through `alias` to a file; takes (<name>.mp3 and takes/<name>-<k>.mp3)
    rotate in order of use so one file never plays twice in a row; each use gets its own small variation of
    level and pitch; low hits get an attack layer (`attack`). Files that don't exist are reported once."""

    def __init__(self):
        self.rules = sounds()
        self.bank, self.count, self.missing = {}, {}, set()

    def name(self, label):
        return self.rules["alias"].get(label, label)

    def files(self, name):
        main = [p for ext in ("mp3", "wav", "ogg", "flac") for p in [BANK / f"{name}.{ext}"] if p.exists()]
        if not main:
            return []
        takes = sorted(p for ext in ("mp3", "wav") for p in (BANK / "takes").glob(f"{name}-[0-9]*.{ext}"))
        return main[:1] + takes

    def takes(self, name, hp=False):
        key = (name, hp)
        if key not in self.bank:
            files = self.files(name)
            xs = [load(f) for f in files]
            if len(xs) > 1:   # takes level with the first by 100 ms peak RMS: only vary_db adds spread
                ref = _peak100(xs[0])
                xs = [xs[0]] + [x * 10 ** ((ref - _peak100(x)) / 20) for x in xs[1:]]
            if hp:
                sos = butter(4, 150, "highpass", fs=SR, output="sos")
                xs = [sosfilt(sos, x, axis=0) for x in xs]
            self.bank[key] = xs
        return self.bank[key]

    def sound(self, q):
        """The sound for cue q at gain x vol, or None when the bank has no file for it."""
        name = self.name(q["name"])
        bank = self.takes(name)
        if not bank:
            self.missing.add(name)
            return None
        k = self.count.get(name, 0)
        self.count[name] = k + 1
        x = bank[k % len(bank)]
        if name in self.rules["attack"]:
            lay, share = self.rules["attack"][name]
            layer = self.takes(lay, hp=True)
            if layer:
                y = layer[k % len(layer)] * float(share)
                x = np.pad(x, ((0, max(0, len(y) - len(x))), (0, 0)))
                x[: len(y)] += y
        x = repitch(x, self.rules["vary_semitones"] * _u(name, k, "pitch")) * 10 ** (self.rules["vary_db"] * _u(name, k, "gain") / 20)
        gain = float(self.rules["gain"].get(name, self.rules["gain"].get(q["name"], 0.3)))
        return trim(x, q) * gain * q.get("vol", 1)


def place(cues, n, foley=None, shift=0.0, fx=None):
    """Effects at their cues into a track of n samples (shift = chapter start). Returns (track, placed, foley)."""
    foley = foley or Foley()
    fx = np.zeros((n, 2)) if fx is None else fx
    count = 0
    for q in sorted(cues, key=lambda q: q["t"]):
        a = int((shift + q["t"]) * SR)
        if 0 <= a < n:
            x = foley.sound(q)
            if x is None:
                continue
            x = x * 10 ** (SFX_DB / 20)
            b = min(n, a + len(x))
            fx[a:b] += x[: b - a]
            count += 1
    return fx, count, foley


def measure(path):
    """Final: integrated loudness, true peak, LRA (ebur128 with true peak)."""
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    s = out[out.rindex("Summary:"):]
    return (float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)), float(re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", s).group(1)),
            float(re.search(r"LRA:\s+(-?[\d.]+) LU", s).group(1)))


def finalize(pre, out, video=None, target=TARGET_I, tp=TARGET_TP):
    """premix -> final at `target` LUFS: a linear gain plus a peak limiter at `tp` dB (4x oversampled, so it
    catches inter-sample peaks); with `video` an mp4 with AAC, otherwise wav. If the codec pushes the true peak
    above -1.5 dBTP, the ceiling drops by the difference; loudness the limiter ate is added back."""
    i0 = measure(pre)[0]
    if i0 < -60:   # silence (no voice, no effects, no music): nothing to normalize
        if video:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(pre), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
        else:
            shutil.copy(pre, out)
        return i0, -99.0, 0.0
    gain, ceil = target - i0, tp
    for _ in range(4):
        chain = (f"volume={gain:.2f}dB,aresample=192000,"
                 f"alimiter=limit={10 ** (ceil / 20):.4f}:attack=1:release=80:level=false:latency=true,aresample={SR}")
        if video:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(pre), "-map", "0:v", "-map", "1:a",
                            "-c:v", "copy", "-af", chain, "-ar", str(SR), "-c:a", "aac", "-b:a", "256k", "-shortest",
                            "-movflags", "+faststart", str(out)], check=True)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pre), "-af", chain, "-ar", str(SR), "-c:a", "pcm_s24le",
                            str(out)], check=True)
        i, tpk, lra = measure(out)
        if tpk <= -1.5 and abs(i - target) <= 0.1:
            break
        if tpk > -1.5:
            ceil -= tpk + 1.6
        gain += target - i
    return i, tpk, lra


def env_follow(x, attack=0.08, release=0.6):
    """Voice envelope for ducking."""
    a = np.abs(x).astype(np.float64)
    hop = 480
    blocks = a[: len(a) // hop * hop].reshape(-1, hop).max(1)
    out = np.zeros_like(blocks)
    ka, kr = np.exp(-hop / SR / attack), np.exp(-hop / SR / release)
    v = 0.0
    for i, b in enumerate(blocks):
        v = ka * v + (1 - ka) * b if b > v else kr * v + (1 - kr) * b
        out[i] = v
    env = np.repeat(out, hop)[: len(x)] if len(out) else np.zeros(len(x))
    return np.pad(env, (0, max(0, len(x) - len(env))), mode="edge")


def duck(music, voice, db=DUCK_DB):
    env = env_follow(voice.mean(1))[: len(music)]
    return music * 10 ** (-db * np.clip(env / 0.05, 0, 1) / 20)[:, None]


def voice_track(path, n):
    """Voice at VOICE_LUFS with a 70 Hz high-pass, padded or cut to n samples."""
    v = load(path)[:n]
    v = np.pad(v, ((0, n - len(v)), (0, 0)))
    if np.abs(v).max() > 0:
        v = v * 10 ** ((VOICE_LUFS - lufs(path)) / 20)
        v = sosfilt(butter(2, 70, "highpass", fs=SR, output="sos"), v, axis=0)
    return v


def music_track(path, n, db=MUSIC_DB, fade_in=1.5, fade_out=4.0):
    """One track looped or cut to the whole length, normalized, with fades."""
    raw = load(path)
    raw = raw * 10 ** ((-20.0 - lufs(path)) / 20) * 10 ** (db / 20)
    if len(raw) < n:
        reps = -(-n // len(raw))
        raw = np.concatenate([raw] * reps)
    m = raw[:n].copy()
    fi, fo = int(fade_in * SR), int(fade_out * SR)
    m[:fi] *= np.linspace(0, 1, fi)[:, None]
    m[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--music")
    ap.add_argument("--music-db", type=float, default=MUSIC_DB)
    ap.add_argument("--duck", type=float, default=DUCK_DB)
    ap.add_argument("--target", type=float, default=TARGET_I)
    a = ap.parse_args()
    b = BUILD / a.slug
    timing = json.loads((b / "timing.json").read_text(encoding="utf-8"))
    n = int(timing["total"] * SR)
    voice = voice_track(b / "voice.wav", n)
    fx, foley, count = np.zeros((n, 2)), Foley(), 0
    for c in timing["chapters"]:
        fx, k, foley = place(cues(f"{a.slug}-{c['id']}"), n, foley, shift=c["start"], fx=fx)
        count += k
    music = duck(music_track(a.music, n, a.music_db), voice, a.duck) if a.music else np.zeros((n, 2))
    wavfile.write(b / "premix.wav", SR, (voice + fx + music).astype(np.float32))
    i, tp, lra = finalize(b / "premix.wav", b / "mix.wav", target=a.target)
    miss = f"; no file in style/sound for: {', '.join(sorted(foley.missing))}" if foley.missing else ""
    print(f"effects placed: {count}{miss}; result {i:.1f} LUFS, true peak {tp:.1f} dBTP, LRA {lra:.1f} LU -> {b / 'mix.wav'}")


if __name__ == "__main__":
    main()
