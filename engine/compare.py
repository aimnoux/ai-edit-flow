#!/usr/bin/env python3
"""Before/after comparisons as one video (never two files side by side in a chat).

  python3 engine/compare.py chapter <full.html> <piece.html> <start> <end>        # a stretch as its own composition
  python3 engine/compare.py mix <composition.html> <video.mp4> <voice.wav> <music|-> <offset> <out.mp4>
  python3 engine/compare.py stack <before.mp4> <after.mp4> <out.mp4> [BEFORE AFTER]   # 16:9 stacked, 9:16 side by side
  python3 engine/compare.py grid <out.mp4> "A=a.mp4" "B=b.mp4" "C=c.mp4" "D=d.mp4"    # four variants in a 2x2 grid, audio of the last
  python3 engine/compare.py seq <out.mp4> "BEFORE=a.mp4" "AFTER=b.mp4" ...             # one after another: same picture, different sound

chapter: the root timeline and the cues are shifted to the stretch start; render it as usual with
`node engine/hf.mjs render -c`. mix: voice and music are cut from `offset`, effects by the composition's cues,
levels as in mix_piece.py. stack: labels in the corner, audio track 1 is "after", track 2 "before".
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE  # noqa: E402


def chapter(src, dst, a, b):
    h = Path(src).read_text(encoding="utf-8")
    full = re.search(r'id="root"[^>]*data-duration="([\d.]+)"', h).group(1)
    h = h.replace(f'data-duration="{full}"', f'data-duration="{b - a:.2f}"')
    cid = re.search(r'data-composition-id="([^"]+)"', h).group(1)
    shift = f"""<script>{{
  // compare.py chapter: the root timeline plays [{a}, {b}] of the full composition, cues are shifted
  const a = {a}, b = {b};
  const M = gsap.timeline({{ paused: true }});
  M.add(TL.tweenFromTo(a, b, {{ ease: "none", duration: b - a }}), 0);
  window.__timelines["{cid}"] = M;
  const q = JSON.parse(document.getElementById("cues").textContent).filter((c) => c.t >= a && c.t < b);
  document.getElementById("cues").textContent = JSON.stringify(q.map((c) => Object.assign(c, {{ t: +(c.t - a).toFixed(3) }})));
  const sc = JSON.parse(document.documentElement.dataset.scenes || "[]").filter(([s, e]) => e > a && s < b);
  document.documentElement.dataset.scenes = JSON.stringify(sc.map(([s, e]) => [+Math.max(0, s - a).toFixed(3), +Math.min(b - a, e - a).toFixed(3)]));
  const m = location.hash.match(/t=([\\d.]+)/); M.seek(m ? +m[1] : 0);
}}</script>"""
    tag = '<script src="lib/finish.js"></script>'
    assert tag in h, "no finish.js in the composition"
    Path(dst).write_text(h.replace(tag, tag + "\n    " + shift, 1), encoding="utf-8")
    print(dst, f"{b - a:.2f} s")


def mix(html, video, voice_p, music_p, off, out):
    import numpy as np
    from scipy.io import wavfile
    from common import SR, chrome_cmd, duration
    from mix import duck, finalize, load, lufs, place, voice_track
    dur = duration(video)
    n, a = int(dur * SR), int(off * SR)
    cut = lambda x: np.pad(x[a:a + n], ((0, max(0, n - len(x[a:a + n]))), (0, 0)))
    full = voice_track(voice_p, a + n)
    voice = cut(full)
    dom = subprocess.run(chrome_cmd("--virtual-time-budget=6000",
                          "--dump-dom", Path(html).resolve().as_uri()), capture_output=True, text=True).stdout
    cues = json.loads(re.search(r'id="cues">(.*?)</script>', dom, re.S).group(1))
    fx, count, _ = place(cues, n)
    music = np.zeros((n, 2))
    if music_p != "-":
        music = cut(load(music_p)) * 10 ** ((-25 + float(os.environ.get("MUSIC_DB", 0)) - lufs(music_p)) / 20)
        music = duck(music, voice)
    pre = Path(tempfile.mkdtemp()) / "premix.wav"
    wavfile.write(pre, SR, (voice + fx + music).astype(np.float32))
    i, tp, _ = finalize(pre, out, video)
    print(out, f"effects {count}; {i:.1f} LUFS, true peak {tp:.1f} dBTP")


def label(text, path):
    from PIL import Image, ImageDraw
    from review import label_font
    font = label_font(34)
    w, h = font.getbbox(text)[2] + 32, 58
    im = Image.new("RGBA", (w, h), (0, 0, 0, 160))
    ImageDraw.Draw(im).text((16, 10), text, font=font, fill=(255, 255, 255, 255))
    im.save(path)


def stack(before, after, out, la="BEFORE", lb="AFTER"):
    wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                         before], capture_output=True, text=True).stdout.strip().split(",")
    vertical = int(wh[1]) > int(wh[0])
    w, st = (720, "hstack") if vertical else (1280, "vstack")
    tmp = Path(tempfile.mkdtemp())
    label(la, tmp / "a.png"); label(lb, tmp / "b.png")
    fc = (f"[0:v]scale={w}:-2[a0];[a0][2:v]overlay=24:24[a];"
          f"[1:v]scale={w}:-2[b0];[b0][3:v]overlay=24:24[b];[a][b]{st}[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", before, "-i", after, "-i", str(tmp / "a.png"), "-i", str(tmp / "b.png"),
                    "-filter_complex", fc, "-map", "[v]", "-map", "1:a?", "-map", "0:a?",
                    "-metadata:s:a:0", f"title={lb.lower()}", "-metadata:s:a:1", f"title={la.lower()}", "-disposition:a:1", "0",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart", out], check=True)
    print(out)


def seq(out, parts):
    """Variants one after another in one video: for sound on the same picture, or several variants of one stretch."""
    tmp = Path(tempfile.mkdtemp())
    args, fc, cat = [], "", ""
    for i, (text, f) in enumerate(parts):
        label(text, tmp / f"{i}.png")
        args += ["-i", f]
    for i in range(len(parts)):
        args += ["-i", str(tmp / f"{i}.png")]
    n = len(parts)
    for i in range(n):
        fc += f"[{i}:v][{n + i}:v]overlay=24:24,setsar=1[v{i}];"
        cat += f"[v{i}][{i}:a]"
    fc += f"{cat}concat=n={n}:v=1:a=1[v][au]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-map", "[au]",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "256k",
                    "-movflags", "+faststart", out], check=True)
    print(out)


def grid(out, parts):
    """Four variants at once in a 2x2 grid (9:16 at 540x960 each, 16:9 at 960x540), labelled; audio of the last."""
    tmp = Path(tempfile.mkdtemp())
    wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                         parts[0][1]], capture_output=True, text=True).stdout.strip().split(",")
    w, h = (540, 960) if int(wh[1]) > int(wh[0]) else (960, 540)
    args, fc = [], ""
    for i, (text, f) in enumerate(parts):
        label(text, tmp / f"{i}.png")
        args += ["-i", f]
    for i in range(len(parts)):
        args += ["-i", str(tmp / f"{i}.png")]
    n = len(parts)
    for i in range(n):
        fc += f"[{i}:v]scale={w}:{h},setsar=1[s{i}];[s{i}][{n + i}:v]overlay=16:16[v{i}];"
    fc += "".join(f"[v{i}]" for i in range(n)) + f"xstack=inputs={n}:layout=0_0|{w}_0|0_{h}|{w}_{h}[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-map", f"{n - 1}:a?",
                    "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    c, a = sys.argv[1], sys.argv[2:]
    if c == "chapter":
        chapter(a[0], a[1], float(a[2]), float(a[3]))
    elif c == "mix":
        mix(a[0], a[1], a[2], a[3], float(a[4]), a[5])
    elif c == "stack":
        stack(*a[:5])
    elif c == "grid":
        grid(a[0], [x.split("=", 1) for x in a[1:]])
    elif c == "seq":
        seq(a[0], [x.split("=", 1) for x in a[1:]])
    else:
        sys.exit(__doc__)
