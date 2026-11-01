#!/usr/bin/env python3
"""Contact sheet of a composition without rendering: frames at the given seconds on one image.

  python3 engine/shots.py <composition id> 1.5 12 30 ...     -> engine/build/frames/<id>.png
  SHOT_TAG=a python3 engine/shots.py ...                      -> <id>-a.png (parallel checks don't overwrite each other)

Each frame is a headless Chrome screenshot of the composition seeked to #t=<s>. Works for 16:9 and
9:16 (the size is read from the composition). Look at the sheet reduced; open a single frame only
for a detail.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, chrome_cmd  # noqa: E402


def size_of(cid):
    h = (HERE / f"{cid}.html").read_text(encoding="utf-8")
    root = re.search(r'id="root"[^>]*', h).group(0)
    return int(re.search(r'data-width="(\d+)"', root).group(1)), int(re.search(r'data-height="(\d+)"', root).group(1))


def shots(cid, times, out=None):
    w, h = size_of(cid)
    vertical = h > w
    out = out or HERE / "build" / "frames"
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    files = []
    for i, t in enumerate(times):
        f = tmp / f"{i:02d}.png"
        subprocess.run(chrome_cmd("--hide-scrollbars", f"--window-size={w},{h}", "--virtual-time-budget=6000", f"--screenshot={f}",
                        (HERE / f"{cid}.html").resolve().as_uri() + f"#t={max(float(t), 0.01)}"), capture_output=True, timeout=180)
        files.append(f)
    name = f"{cid}-{os.environ['SHOT_TAG']}.png" if os.environ.get("SHOT_TAG") else f"{cid}.png"
    dst = out / name
    tw = 360 if vertical else 640
    th = round(tw * h / w)
    cols = min(len(files), 5 if vertical else 3)
    args = sum([["-i", str(f)] for f in files], [])
    if len(files) == 1:
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-vf", f"scale={tw}:-1", str(dst)], check=True)
    else:
        sc = "".join(f"[{i}:v]scale={tw}:-1[v{i}];" for i in range(len(files)))
        layout = "|".join(f"{(i % cols) * tw}_{(i // cols) * th}" for i in range(len(files)))
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex",
                        f"{sc}{''.join(f'[v{i}]' for i in range(len(files)))}xstack=inputs={len(files)}:layout={layout}:fill=black[o]",
                        "-map", "[o]", str(dst)], check=True)
    return dst


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    print(shots(sys.argv[1], sys.argv[2:]))
