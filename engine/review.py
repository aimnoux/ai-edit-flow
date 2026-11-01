#!/usr/bin/env python3
"""Frame review of a composition before showing it: measure first, then look.

  python3 engine/review.py <composition id> [--chapter START END] [--video render.mp4] [-o folder]

Writes into engine/build/review/<name>/ (or -o):
  beats-N.jpg       every scene 0.3 s after its start and in its middle (scene() in kit.js registers scenes),
                    plus a regular grid: every 1.5 s in 9:16, every 3 s in 16:9
  seams-N.jpg       every cut: -0.2 s and +0.2 s
  phone-N.jpg       the beats frames at phone width: is the text readable on a phone
  REVIEW-INPUT.md   findings of `hyperframes check --json` (craft, layout, lint), and with --video: dead
                    stretches (> 3 s without change) and attention lulls (9:16 > 1.5 s, 16:9 > 3 s without
                    an event), the list of sheets for the reviewer

Then a fresh agent follows the review skill: it gets only REVIEW-INPUT.md, the sheets and the script text
of this stretch, and returns lines `t=... · where · problem -> fix · what to keep` ranked P0/P1/P2.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, HERE, run_chrome, run_hf  # noqa: E402
from compare import chapter  # noqa: E402

SKIP = {"film_silent", "nested_structure_needs_subcomposition"}   # sound is mixed outside the composition; the world is one layer by design
PAGE = 24


def label_font(size):
    """A font for the time stamps: Pillow's bundled one, no system paths."""
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def link(src, dst):
    """A symlink where possible, a copy where not (Windows without developer mode)."""
    try:
        os.symlink(src, dst, target_is_directory=src.is_dir())
    except (OSError, NotImplementedError):
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy(src, dst)


def project(cid, out, chap):
    """A temporary HyperFrames project: the composition as index.html, links to lib and scenes."""
    proj = out / "proj"
    shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True)
    for d in ["lib", "scenes", "assets"]:
        if (HERE / d).exists():
            link(HERE / d, proj / d)
    for f in ["hyperframes.json"]:
        if (HERE / f).exists():
            shutil.copy(HERE / f, proj / f)
    idx = proj / "index.html"
    comp = HERE / f"{cid}.html"
    if chap:
        chapter(comp, idx, *chap)
    else:
        shutil.copy(comp, idx)
    h = idx.read_text(encoding="utf-8")
    cid_in = re.search(r'data-composition-id="([^"]+)"', h).group(1)
    # the timeline is registered in finish.js; the static check looks for the registration in the composition itself
    tag = '<script src="lib/finish.js"></script>'
    idx.write_text(h.replace(tag, tag + f'\n    <script>window.__timelines["{cid_in}"] = window.__timelines["{cid_in}"];</script>', 1), encoding="utf-8")
    return proj


def scenes(proj):
    dom = run_chrome("--virtual-time-budget=6000", "--dump-dom", (proj / "index.html").resolve().as_uri()).stdout
    err = re.search(r'data-err="([^"]*)"', dom)
    if err:
        raise SystemExit("error in scenes: " + err.group(1))
    sc = json.loads(re.search(r'data-scenes="([^"]*)"', dom).group(1).replace("&quot;", '"'))
    root = re.search(r'id="root"[^>]*', dom).group(0)
    dur = float(re.search(r'data-duration="([\d.]+)"', root).group(1))
    vertical = int(re.search(r'data-height="(\d+)"', root).group(1)) > int(re.search(r'data-width="(\d+)"', root).group(1))
    return sorted(sc), dur, vertical


def snap(proj, times, dst, timeout=None):
    times = sorted({round(t, 2) for t in times})
    if not times:
        return []
    # Clear old captures: otherwise a second review may pair new times with stale images.
    if dst.exists():
        shutil.rmtree(dst)
    run_hf("snapshot", "--at", ",".join(map(str, times)), "--no-end", "--describe", "false", "-o", str(dst), str(proj),
           timeout=timeout).check_returncode()
    paths = sorted(dst.glob("*.png"), key=lambda p: float(re.search(r"at-([\d.]+)s", p.name).group(1)))
    if len(paths) != len(times):
        raise RuntimeError(f"Snapshot returned {len(paths)} frames for {len(times)} requested times")
    return list(zip(times, paths))


def sheets(frames, out, name, width, cols):
    from PIL import Image, ImageDraw
    font = label_font(22 if width > 300 else 16)
    paths = []
    for k in range(0, len(frames), PAGE):
        part = frames[k:k + PAGE]
        ims = []
        for t, p in part:
            im = Image.open(p).convert("RGB")
            im = im.resize((width, round(im.height * width / im.width)))
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 96, 30], fill=(0, 0, 0))
            d.text((6, 4), f"{t:.1f}s", font=font, fill=(255, 255, 255))
            ims.append(im)
        if not ims:
            continue
        h = ims[0].height
        rows = -(-len(ims) // cols)
        sheet = Image.new("RGB", (cols * width + (cols - 1) * 6, rows * h + (rows - 1) * 6), (60, 60, 60))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * (width + 6), (i // cols) * (h + 6)))
        dst = out / f"{name}-{k // PAGE + 1}.jpg"
        sheet.save(dst, quality=85)
        paths.append(dst)
    return paths


def check(proj):
    r = run_hf("check", "--json", str(proj), timeout=180)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"hyperframes check gave no JSON: {(r.stderr or r.stdout)[-300:]}")
    if not isinstance(d, dict) or not any(isinstance(d.get(k), dict) for k in ("lint", "runtime", "layout")):
        raise RuntimeError("hyperframes check returned an incomplete report")
    lines = []
    for k in ["lint", "runtime", "layout", "motion", "contrast", "craft"]:
        for f in (d.get(k) or {}).get("findings") or []:
            if f.get("code") in SKIP:
                continue
            lines.append(f"- t={f.get('time', 0):.1f}s · {k}/{f.get('code')} ({f.get('severity')}) · {(f.get('message') or '')[:220]}")
    if r.returncode and not lines:
        raise RuntimeError(f"hyperframes check failed ({r.returncode}): {r.stderr[-300:]}")
    return lines


def dead(video, floor=10, span=3.0):
    """Stretches longer than span seconds where the frame doesn't change: the local difference of neighbouring
    frames stays under floor after a blur (grain gives 1-5, a word or a line appearing gives 10+). The bottom
    10 % of the frame is ignored: a progress bar there would hide every pause."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                        "crop=iw:ih*0.9:0:0,scale=320:-1,format=gray,gblur=sigma=2,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YMAX:file=-",
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stdout
    ts = re.findall(r"pts_time:([\d.]+)", r)
    ys = re.findall(r"YMAX=([\d.]+)", r)
    out, start = [], None
    for t, y in zip(map(float, ts), map(float, ys)):
        if y < floor:
            start = t if start is None else start
        else:
            if start is not None and t - start > span:
                out.append((start, t))
            start = None
    if start is not None and ts and float(ts[-1]) - start > span:
        out.append((start, float(ts[-1])))
    return out


def lulls(video, span=1.5, floor=1.5):
    """Attention lulls: stretches longer than span seconds where less than floor % of the frame changes (bottom
    10 % ignored). A couple of typed letters, a cursor or a grey highlight is not an event; a thing entering,
    a reframe, a marker is."""
    vf = ("crop=iw:ih*0.9:0:0,scale=270:-1,format=gray,gblur=sigma=1.5,tblend=all_mode=difference,"
          "lutyuv=y='if(gt(val,24),255,0)',signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-")
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf, "-an", "-f", "null", "-"], capture_output=True, text=True).stdout
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]
    ys = [float(x) / 255 * 100 for x in re.findall(r"YAVG=([\d.]+)", r)]
    out, last = [], 0.0
    for t, y in zip(ts, ys):
        if y >= floor:
            if t - last > span:
                out.append((last, t))
            last = t
    if ts and ts[-1] - last > span:
        out.append((last, ts[-1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cid")
    ap.add_argument("--chapter", nargs=2, type=float, help="only this stretch, seconds")
    ap.add_argument("--video")
    ap.add_argument("-o")
    a = ap.parse_args()
    name = a.cid + (f"-{a.chapter[0]:.0f}-{a.chapter[1]:.0f}" if a.chapter else "")
    out = Path(a.o).resolve() if a.o else BUILD / "review" / name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.jpg"):
        f.unlink()
    proj = project(a.cid, out, a.chapter)
    sc, dur, vertical = scenes(proj)
    step = 1.5 if vertical else 3.0
    beats = [t for s, e in sc for t in (s + 0.3, (s + e) / 2) if 0 <= t < dur]
    beats += [t for t in (k * step + 0.5 for k in range(int(dur / step))) if all(abs(t - u) >= 0.4 for u in beats)]
    seams = [t for s, _ in sc if s > 0.3 for t in (s - 0.2, s + 0.2) if t < dur]
    fb = snap(proj, beats, out / "frames-beats")
    fs = snap(proj, seams, out / "frames-seams")
    w, cols = (270, 8) if vertical else (480, 4)
    made = sheets(fb, out, "beats", w, cols) + sheets(fs, out, "seams", w, 8 if vertical else 6) + sheets(fb, out, "phone", 180 if vertical else 360, 10 if vertical else 6)
    found = check(proj)
    stills = dead(a.video) if a.video else None
    md = [f"# Review: {name}", "", f"Duration {dur:.1f} s, scenes {len(sc)}, {'9:16' if vertical else '16:9'}.", "",
          "## Sheets", *[f"- {p.name}" for p in made], "",
          "## hyperframes check --json", *(found or ["- no findings"]), ""]
    if stills is not None:
        md += ["## Dead stretches in the render (> 3 s without change)", *([f"- {s:.1f}-{e:.1f} s ({e - s:.1f} s)" for s, e in stills] or ["- none"]), ""]
        span = 1.5 if vertical else 3.0
        gaps = lulls(a.video, span)
        md += [f"## Attention lulls (> {span:g} s without an event: less than 1.5 % of the frame changes)",
               *([f"- {s:.1f}-{e:.1f} s ({e - s:.1f} s)" for s, e in gaps] or ["- none"]), ""]
    (out / "REVIEW-INPUT.md").write_text("\n".join(md), encoding="utf-8")
    shutil.rmtree(proj, ignore_errors=True)
    print(out / "REVIEW-INPUT.md")


if __name__ == "__main__":
    main()
