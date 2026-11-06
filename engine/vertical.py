#!/usr/bin/env python3
"""Vertical videos 1080x1920 from a batch text (vertical/<batch>.md): voice timing -> composition -> render -> mix.

  python3 engine/vertical.py build vertical/example.md 1 yt            # cloned voice (voice.py) -> engine/example-s1-yt.html
  python3 engine/vertical.py build vertical/example.md 1 yt --estimate  # no voice yet: timing estimated from the text
  python3 engine/vertical.py build vertical/example.md 1 yt --cut DIR   # live voice: words.json + voice from cut.py for this video
  python3 engine/vertical.py build vertical/example.md 1 yt --dur=9     # a loop with one phrase: length fixed, no ending
  python3 engine/vertical.py silent example 7 yt 8.0 [--no-loop]        # no voice at all: scene s7.js, 8.0 s, loops by default
  python3 engine/vertical.py shots example-s1-yt 0.5 3 8 ...            # contact sheet without rendering
  python3 engine/vertical.py render example-s1-yt [--music track.mp3] [--mix-only]   # HyperFrames render -> strobe check -> mix
                                                                                     # a 3D scene (s<N>.mjs): render3d.mjs -> mix

Platforms: yt (YouTube Shorts), ig (Instagram Reels), tt (TikTok). The platform changes the ending
(block N.8 for yt, N.9 for ig/tt, N.9 falls back to N.8) and the button lib/vertical.js draws; nothing else.
Scenes: engine/scenes/<batch>/s<N>.js, a stub is created if missing. Captions are embedded always (lib/vertical.js).
Block N.0 is the slate for the cut, it never goes into the video.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import composition, estimate_audio, load_audio, scene_stub, trim, words_from  # noqa: E402
from common import BUILD, CFG, FPS, HERE, HF, RENDERS, SCENES, SR, norm, sounds, sync_style  # noqa: E402
from shots import shots  # noqa: E402
from tts_elevenlabs import parse_blocks, strip_triggers  # noqa: E402
from voice import cached_paragraph, find_said, paragraphs, tts_dir, written  # noqa: E402

ENDING = {"yt": "8", "ig": "9", "tt": "9"}
LEAD, GAP_PARA, GAP_BLOCK, GAP_END, TAIL = 0.12, 0.28, 0.38, 0.45, 1.8   # TAIL: the ending's button holds after the last word
GAP_SPREAD = 0.25   # pauses are not all the same length: +-25 % by paragraph, deterministic


def gap(base, key):
    u = int.from_bytes(hashlib.md5(key.encode()).digest()[:4], "little") / 2 ** 31 - 1
    return base * (1 + GAP_SPREAD * u)


def is_ending(block):
    return block.split(".")[1] in ("8", "9")


def snap_onsets(words, audio, win=0.01):
    """A word start from the TTS timing near a pause drifts from the sound by 0.1-0.6 s. If a start falls into
    silence: sound inside the word -> move forward to it; none -> back to the last onset after the pause.
    Triggers, sounds and captions follow it."""
    x = audio.mean(1) if audio.ndim > 1 else audio
    k = int(win * SR)
    rms = np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(k) / k, mode="same"))
    if rms.max() <= 0:
        return words
    loud = rms >= rms.max() * 0.08
    g = int(0.04 * SR)
    run = np.convolve(~loud, np.ones(g), mode="full")[: len(loud)]
    onsets = np.flatnonzero(loud & (np.roll(run, 1) >= g))
    prev = 0.0
    for w in words:
        i, j = int(w["s"] * SR), int(w["e"] * SR)
        if i >= len(loud) or (i >= 0 and not loud[i]):
            fwd = np.flatnonzero(loud[i:j])
            if len(fwd):
                w["s"] = (i + fwd[0]) / SR
            else:
                back = onsets[(onsets < i) & (onsets / SR > prev)]
                if len(back):
                    w["s"] = back[-1] / SR
                    w["e"] = min(w["e"], len(x) / SR)
        prev = w["s"]
    return words


def timing_payload(total, blocks, plat, loop=False):
    rules = sounds()
    return {"dur": total, "blocks": blocks, "fps": FPS, "platform": plat, "loop": loop,
            "channel": {k: v for k, v in (CFG.get("channel") or {}).items() if k != "_"},
            "captions": {k: v for k, v in (CFG.get("captions") or {}).items() if k != "_"},
            "sfx": {"main": rules["main"], "quiet": rules["quiet"], "gap": rules["gap"]}}


def write_composition(project, roll, plat, total, blocks, loop):
    cid = f"{project}-s{roll}-{plat}"
    scene = SCENES / project / f"s{roll}.js"
    scene_stub(scene, f"{project}, video {roll}")
    composition(cid, total, timing_payload(total, blocks, plat, loop), f"scenes/{project}/s{roll}.js", template="template-v.html")
    return cid


def voice_timeline(parts, total):
    """Place paragraphs into the output, padding silence or clipping at a loop's fixed end."""
    track = np.zeros(int(total * SR), dtype=np.float32)
    for start, audio in parts:
        i = int(round(start * SR))
        size = min(len(audio), len(track) - i)
        if size > 0:
            track[i:i + size] += audio[:size]
    return track


def cmd_build(reading, roll, plat, *rest):
    reading = Path(reading)
    project = reading.stem
    loop = next((float(a.split("=")[1]) for a in rest if a.startswith("--dur=")), None)
    estimate = "--estimate" in rest
    cut_dir = next((Path(rest[i + 1]) for i, a in enumerate(rest) if a == "--cut"), None)
    allp = paragraphs(reading)
    num = str(roll)
    body = [p for p in allp if p["block"].split(".")[0] == num and not is_ending(p["block"])]
    if not body:
        sys.exit(f"no video {roll} in {reading}")
    eid = next((e for e in (f"{num}.{ENDING[plat]}", f"{num}.8") if any(p["block"] == e for p in allp)), None)
    end = [p for p in allp if p["block"] == eid]
    if not end and loop is None:
        sys.exit(f"no ending {num}.{ENDING[plat]} (or {num}.8) in {reading}")
    seq = body + ([dict(p, src=eid, block="end") for p in end] if loop is None else [])
    sync_style()
    (BUILD / project).mkdir(parents=True, exist_ok=True)

    if cut_dir:
        return build_from_cut(project, roll, plat, seq, cut_dir, loop)
    tts = tts_dir(reading)
    t, voice, blocks = LEAD, [], {}
    for n, p in enumerate(seq):
        name = f"{p.get('src', p['block'])}-{p['para']}"
        if estimate:
            audio, words, said = estimate_audio(p)
        else:
            source = dict(p, block=p.get("src", p["block"]))
            meta = cached_paragraph(reading, source, allp)
            audio, off = trim(load_audio(tts / f"{name}.mp3"))
            words = snap_onsets(words_from(meta["alignment"], off), audio)
            said = meta["spoken"]
        trig, cursor = [], 0
        for w, off in zip(p["triggers"], p["offs"]):
            k = find_said(said, w, max(cursor, off - 8))
            if k < 0:
                k = find_said(said, w, cursor)
            if k < 0:
                print(f"  warning: trigger [{w}] in {name} not found")
                continue
            cursor = k + 1
            ws = next(x for x in words if x["i"] + len(x["w"]) > k)
            trig.append({"w": w, "t": round(ws["s"] + t, 3)})
        words = written(words, p["text"], said)
        voice.append((t, audio))
        dur = len(audio) / SR
        blocks.setdefault(p["block"], []).append({
            "block": p["block"], "who": p.get("who"), "text": p["text"], "s": round(t, 3), "e": round(t + dur, 3),
            "words": [{"w": x["w"], "n": norm(x["w"]), "s": round(x["s"] + t, 3), "e": round(x["e"] + t, 3)} for x in words],
            "triggers": trig})
        t += dur
        if n + 1 < len(seq):
            nxt = seq[n + 1]["block"]
            t += gap(GAP_END if nxt == "end" else GAP_PARA if nxt == p["block"] else GAP_BLOCK, name)
    total = round((t + TAIL if loop is None else loop) * FPS) / FPS
    track = voice_timeline(voice, total)
    cid = write_composition(project, roll, plat, total, blocks, bool(loop))
    wavfile.write(BUILD / project / f"{cid}-voice.wav", SR, track[: int(total * SR)])
    print(f"{cid}: {total:.1f} s" + (" (estimated timing)" if estimate else ""))


def build_from_cut(project, roll, plat, seq, cut_dir, loop):
    """Select this video's paragraphs from a batch cut and rebuild its voice timeline."""
    words = json.loads((cut_dir / "words.json").read_text(encoding="utf-8"))
    voice_file = cut_dir / "voice.wav" if (cut_dir / "voice.wav").exists() else cut_dir / "rough.mp4"
    audio = load_audio(voice_file)
    blocks, pieces = {}, []
    by_para = {}
    for i, w in enumerate(words):
        if w.get("para"):
            by_para.setdefault(w["para"], []).append(i)
    for p in seq:
        src = p.get("src", p["block"])
        indices = by_para.get(f"{src}/{p['para']}", [])
        if not indices:
            print(f"  warning: no words for {src} paragraph {p['para']} in the cut")
            continue
        first, last = indices[0], indices[-1]
        # Keep a little articulation around the timestamped speech, without picking up
        # a neighbouring slate, video or alternate ending from the batch recording.
        start = max(0, words[first]["s"] - 0.03, words[first - 1]["e"] if first else 0)
        stop = min(len(audio) / SR, words[last]["e"] + 0.08,
                   words[last + 1]["s"] if last + 1 < len(words) else len(audio) / SR)
        a, b = int(round(start * SR)), int(round(stop * SR))
        if b <= a:
            raise ValueError(f"no audio for {src} paragraph {p['para']} in the cut")
        pieces.append((p, [words[i] for i in indices], audio[a:b], a / SR))
    if not pieces:
        raise ValueError(f"no words for video {roll} in the cut")

    t, voice = LEAD, []
    for n, (p, source_words, part, offset) in enumerate(pieces):
        src = p.get("src", p["block"])
        dur = len(part) / SR
        ws = [{**w, "s": round(w["s"] - offset + t, 3), "e": round(w["e"] - offset + t, 3)}
              for w in source_words]
        trig, cur = [], 0
        for tw in p["triggers"]:
            toks = [norm(t) for t in tw.split()]
            for i in range(cur, len(ws)):
                key = norm(ws[i]["w"])
                if key and toks[0] and (key.startswith(toks[0][:4]) or toks[0].startswith(key[:4])):
                    trig.append({"w": tw, "t": ws[i]["s"]}); cur = i + 1; break
            else:
                print(f"  warning: trigger [{tw}] in {src} not found in speech")
        blocks.setdefault(p["block"], []).append({
            "block": p["block"], "who": p.get("who"), "text": p["text"], "s": round(t, 3), "e": round(t + dur, 3),
            "words": [{"w": x["w"], "n": norm(x["w"]), "s": x["s"], "e": x["e"]} for x in ws], "triggers": trig})
        voice.append((t, part))
        t += dur
        if n + 1 < len(pieces):
            nxt = pieces[n + 1][0]["block"]
            name = f"{src}-{p['para']}"
            t += gap(GAP_END if nxt == "end" else GAP_PARA if nxt == p["block"] else GAP_BLOCK, name)
    total = round((t + TAIL if loop is None else loop) * FPS) / FPS
    cid = write_composition(project, roll, plat, total, blocks, bool(loop))
    wavfile.write(BUILD / project / f"{cid}-voice.wav", SR, voice_timeline(voice, total))
    print(f"{cid}: {total:.1f} s (live voice)")


def cmd_silent(project, roll, plat, dur, *rest):
    """A video without voice (a meme, a loop): length given, no captions, no ending; sound = effects at the cues.
    A loop: frame `dur` equals frame 0, mix_piece.py --loop wraps the effect tails."""
    sync_style()
    total = round(float(dur) * FPS) / FPS
    (BUILD / project).mkdir(parents=True, exist_ok=True)
    cid = write_composition(project, roll, plat, total, {}, "--no-loop" not in rest)
    wavfile.write(BUILD / project / f"{cid}-voice.wav", SR, np.zeros(int(total * SR), dtype=np.float32))
    print(f"{cid}: {total:.2f} s, no voice" + (", not a loop" if "--no-loop" in rest else ""))


def strobe(video):
    """Frames from another moment (a stroboscope): a frame that differs from both neighbours much more than they differ
    from each other. Happens when a segmented render resumes wrong."""
    log = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                          "scale=270:-1,format=gray,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    d = [float(x) for x in re.findall(r"YAVG=([\d.]+)", log)]
    return [round(i / FPS, 2) for i in range(1, len(d) - 1) if d[i] > 1.5 * (d[i - 1] + d[i + 1]) + 3 and d[i + 1] > 3 * d[i - 1] + 3]


def cmd_render(cid, *flags):
    """HyperFrames render (segmented, resumable) -> strobe check -> mix with voice, cues and optional music.
    A composition with a 3D module renders on the video card through render3d.mjs instead."""
    project = cid.rsplit("-s", 1)[0]
    out_dir = RENDERS / project
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = out_dir / f"{cid}-video.mp4"
    music = next((flags[i + 1] for i, a in enumerate(flags) if a == "--music"), "-")
    if music != "-":
        music = str(Path(music).resolve())  # mixing runs from engine/, the caller supplies a root-relative path
    html = (HERE / f"{cid}.html").read_text(encoding="utf-8")
    if "--mix-only" not in flags and 'type="module"' in html:
        log = BUILD / project / f"render-{cid}.log"
        with open(log, "w") as lf:
            r = subprocess.run(["node", str(HERE / "render3d.mjs"), cid, f"--out={vid}"], cwd=HERE, stdout=lf, stderr=subprocess.STDOUT)
        if r.returncode:
            sys.exit(f"3D render failed, see {log} (the same command continues from the last frame)")
    elif "--mix-only" not in flags:
        import os
        log = BUILD / project / f"render-{cid}.log"
        with open(log, "w") as lf:
            r = subprocess.run([sys.executable, str(HERE / "render.py"), cid, str(vid), "--fps", str(FPS), "--quiet",
                                     *[f for f in flags if f == "--resume"]],
                               cwd=HERE, stdout=lf, stderr=subprocess.STDOUT, env={**os.environ, "HF_SEGMENTED_CAPTURE": "true"})
        if r.returncode:
            sys.exit(f"render failed, see {log} (retry with --resume to continue from the last segment)")
        bad = strobe(vid)
        if bad:
            sys.exit(f"frames from another moment at {bad} s: re-render (python3 engine/vertical.py render {cid}) and check again")
    loop = '"loop": true' in html
    out = out_dir / f"{cid}.mp4"
    subprocess.run([sys.executable, str(HERE / "mix_piece.py"), cid, str(vid), str(BUILD / project / f"{cid}-voice.wav"),
                    music, str(out), *(["--loop"] if loop else [])], cwd=HERE, check=True)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    c, *a = sys.argv[1:]
    cmds = {"build": lambda: cmd_build(*a), "silent": lambda: cmd_silent(*a),
            "shots": lambda: print(shots(a[0], a[1:])), "render": lambda: cmd_render(*a)}
    if c not in cmds:
        sys.exit(__doc__)
    cmds[c]()
