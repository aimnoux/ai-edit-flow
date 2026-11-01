#!/usr/bin/env python3
"""Silence between chapters of a live-voice cut: room for a chapter title and an outro.

  python3 engine/pad_chapters.py <slug> [--cut videos/<slug>/cut] [--voice clean.wav] [--out videos/<slug>/cut/pad] [--speed 1.0]

Takes words.json from the cut (words on the cut timeline with script blocks) and a voice of the same
length (the cleaned one, or rough.mp4 from the cut), inserts silence between chapters so that from the
last word of a chapter to the first word of the next there is TAIL of the previous + HEAD of the next
(videos/<slug>/video.json), and `end` seconds at the end. Writes words.json, voice.wav and rough.mp4
(black frame + voice) for build.py --cut.

--speed speeds the speech up (atempo, pitch unchanged) and compresses word timing; the pauses between
chapters stay in real seconds. The voice can be swapped later for another processing of the same cut:
timing depends only on the cuts, so a cleaned voice drops in without a re-render.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import VIDEOS, duration, ffmpeg_filter_file  # noqa: E402


def video_cfg(slug):
    p = VIDEOS / slug / "video.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    head, tail = d.get("head") or {}, d.get("tail") or {}
    return {"head": {k: float(v) for k, v in head.items() if k != "_"}, "tail": {k: float(v) for k, v in tail.items() if k != "_"},
            "end": float(d.get("end", 3.0))}


def head_of(cfg, ch):
    return cfg["head"].get(ch, cfg["head"].get("default", 1.2))


def tail_of(cfg, ch):
    return cfg["tail"].get(ch, cfg["tail"].get("default", 1.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--cut")
    ap.add_argument("--voice", help="cleaned voice of the same length as the cut; default: the cut's rough.mp4")
    ap.add_argument("--out")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    cfg = video_cfg(a.slug)
    src = Path(a.cut) if a.cut else VIDEOS / a.slug / "cut"
    out = Path(a.out) if a.out else src / "pad"
    out.mkdir(parents=True, exist_ok=True)
    words = json.loads((src / "words.json").read_text(encoding="utf-8"))
    ch = lambda w: (w["block"] or "").split(".")[0]
    for w in words:
        w["s"], w["e"] = w["s"] / a.speed, w["e"] / a.speed

    # insertion points: just after the last word of a chapter, length of the insert
    cuts, prev = [], None
    for i, w in enumerate(words):
        c = ch(w)
        if prev is not None and c and c != ch(words[prev]) and ch(words[prev]):
            gap = w["s"] - words[prev]["e"]
            need = tail_of(cfg, ch(words[prev])) + head_of(cfg, c)
            if need > gap:
                cuts.append((words[prev]["e"] + min(0.3, gap / 2), need - gap))
        if c:
            prev = i
    voice = a.voice or str(src / "rough.mp4")
    if a.speed != 1.0:
        sped = out / "voice-speed.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", voice, "-af", f"atempo={a.speed}", "-ac", "1", "-ar", "48000",
                        "-c:a", "pcm_s24le", str(sped)], check=True)
        voice = str(sped)
    dur = duration(voice)

    shift = lambda t: t + sum(d for at, d in cuts if at <= t)
    for w in words:
        w["s"], w["e"] = round(shift(w["s"]), 3), round(shift(w["e"]), 3)
    (out / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=0), encoding="utf-8")

    # voice: pieces between insertion points + silence of the needed length, a tail at the end
    pts = [0.0] + [at for at, _ in cuts] + [dur]
    fc, labels = [], []
    for k in range(len(pts) - 1):
        fc.append(f"[0:a]atrim={pts[k]:.3f}:{pts[k + 1]:.3f},asetpts=PTS-STARTPTS[p{k}];")
        labels.append(f"[p{k}]")
        pad = cuts[k][1] if k < len(cuts) else cfg["end"]
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{pad:.3f}[z{k}];")
        labels.append(f"[z{k}]")
    fc.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[o]")
    (out / "fc_pad.txt").write_text("".join(fc), encoding="utf-8")
    ffmpeg_filter_file(["-i", voice], out / "fc_pad.txt", ["-map", "[o]", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le", str(out / "voice.wav")])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=1280x720:r=25", "-i", str(out / "voice.wav"),
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "256k", str(out / "rough.mp4")], check=True)
    total = dur + sum(d for _, d in cuts) + cfg["end"]
    print(f"inserts {len(cuts)}: " + ", ".join(f"{at:.1f}+{d:.1f}" for at, d in cuts) + f"; end tail {cfg['end']:.0f} s; total {total:.1f} s -> {out}")


if __name__ == "__main__":
    main()
