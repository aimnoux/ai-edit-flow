#!/usr/bin/env python3
"""Timeline of a horizontal video: voice track, word timing, chapter compositions.

  python3 engine/build.py <slug> --cut <dir>     # live voice: words.json + voice.wav|rough.mp4 from cut.py / pad_chapters.py
  python3 engine/build.py <slug> --tts           # cloned voice: videos/<slug>/tts/script-<voice>-<model>/ from voice.py
  python3 engine/build.py <slug> --estimate      # no voice yet: word timing estimated from the text, silent track

Chapters are the integer part of the script blocks (`### 2.3` is chapter 2); titles come from the
`## 2. Title` headings. videos/<slug>/video.json gives the silence before a chapter's first word (head)
and after its last word (tail), and the end tail.

Writes:
  engine/build/<slug>/timing.json        chapters (start, dur, title), paragraphs with words and triggers in seconds
  engine/build/<slug>/voice.wav          the whole voice track;  ch<N>-voice.wav  per chapter
  engine/build/<slug>/subtitles.srt      subtitles for the platform
  engine/<slug>-ch<N>.html               one composition per chapter from template.html, timing embedded
                                         (scene code: engine/scenes/<slug>/ch<N>.js, a stub is created if missing)
Style is copied into engine/lib/ (tokens.css, fonts/) and GSAP is fetched once (lib/vendor/).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, FPS, HERE, SCENES, SR, VIDEOS, duration, norm, slot, sounds, sync_style  # noqa: E402
from pad_chapters import head_of, tail_of, video_cfg  # noqa: E402
from tts_elevenlabs import chapter_titles, parse_blocks, strip_triggers  # noqa: E402
from voice import cached_paragraph, find_said, paragraphs as tts_paragraphs, tts_dir, written  # noqa: E402

GAP_PARA = 0.6      # pause between paragraphs of one block (cloned voice)
GAP_BLOCK = 0.8     # pause between blocks
WPS = 2.6           # words per second for --estimate


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim(x):
    """Cuts silence at both ends; returns (signal, seconds cut at the front)."""
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode="same")
    idx = np.where(env > 10 ** (-48 / 20))[0]
    if not len(idx):
        return x, 0.0
    a = max(0, idx[0] - int(0.03 * SR))
    b = min(len(x), idx[-1] + int(0.08 * SR))
    return x[a:b], a / SR


def words_from(alignment, offset):
    """Character timing of ElevenLabs -> words with start/end and the index of their first character."""
    chars = alignment["characters"]
    st, en = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    words, cur = [], None
    for i, ch in enumerate(chars):
        if ch.isspace():
            cur = None
            continue
        if cur is None:
            cur = {"w": "", "s": st[i] - offset, "e": en[i] - offset, "i": i}
            words.append(cur)
        cur["w"] += ch
        cur["e"] = en[i] - offset
    return words


def match_trigger(words, tw, cur):
    """Index of the word a trigger starts on, searching from cur (by a 4-letter prefix)."""
    toks = [norm(t) for t in tw.split()]
    for i in range(cur, len(words)):
        n = norm(words[i]["w"])
        if n and toks[0] and (n.startswith(toks[0][:4]) or toks[0].startswith(n[:4])):
            return i
    return -1


def frame(t):
    return round(t * FPS) / FPS


def from_cut(slug, src, script):
    """Live voice: words on the cut timeline, chapter edges around the inserted silence."""
    cfg = video_cfg(slug)
    words = json.loads((src / "words.json").read_text(encoding="utf-8"))
    voice_file = src / "voice.wav" if (src / "voice.wav").exists() else src / "rough.mp4"
    voice = load_audio(voice_file)
    total = frame(len(voice) / SR)
    paras, last = {}, None
    for w in words:
        key = w["para"] or last
        last = key
        if key:
            paras.setdefault(key, []).append(w)
    entries = []
    for key, ws in paras.items():
        bid, k = key.split("/")
        text, trig = strip_triggers(script[bid][int(k)])
        e = {"block": bid, "para": int(k), "text": text, "s": ws[0]["s"], "e": ws[-1]["e"],
             "words": [{"w": x["w"], "n": norm(x["w"]), "s": x["s"], "e": x["e"]} for x in ws], "triggers": []}
        cur = 0
        for tw, _ in trig:
            i = match_trigger(ws, tw, cur)
            if i < 0:
                print(f"  warning: trigger [{tw}] in {bid} not found in speech")
                continue
            e["triggers"].append({"w": tw, "t": ws[i]["s"]})
            cur = i + 1
        entries.append(e)
    entries.sort(key=lambda e: e["s"])
    starts, ends = {}, {}
    for e in entries:
        c = e["block"].split(".")[0]
        starts[c] = min(starts.get(c, 1e9), e["s"])
        ends[c] = max(ends.get(c, 0), e["e"])
    order = sorted(starts, key=lambda c: starts[c])
    edge = lambda i: frame(max(ends[order[i - 1]] + 0.2, starts[order[i]] - head_of(cfg, order[i])))
    chapters = []
    for i, c in enumerate(order):
        s0 = 0.0 if i == 0 else edge(i)
        s1 = edge(i + 1) if i + 1 < len(order) else total
        chapters.append({"num": c, "start": s0, "end": s1})
    return entries, voice, total, chapters


def from_paragraphs(slug, paras, script, audio_of):
    """Cloned or estimated voice: paragraphs laid out with head/tail per chapter and pauses between them."""
    cfg = video_cfg(slug)
    order = sorted({p["block"].split(".")[0] for p in paras}, key=int)
    entries, pieces, chapters, t = [], [], [], 0.0
    for c in order:
        ch_paras = [p for p in paras if p["block"].split(".")[0] == c]
        c_start = t
        t += head_of(cfg, c)
        for n, p in enumerate(ch_paras):
            audio, words, said = audio_of(p)
            dur = len(audio) / SR
            trig, cursor = [], 0
            for w, off in zip(p["triggers"], p["offs"]):
                k = find_said(said, w, max(cursor, off - 8))
                if k < 0:
                    k = find_said(said, w, cursor)
                if k < 0:
                    print(f"  warning: trigger [{w}] in {p['block']} not found")
                    continue
                cursor = k + 1
                ws = next(x for x in words if x["i"] + len(x["w"]) > k)
                trig.append({"w": w, "t": round(ws["s"] + t, 3)})
            words = written(words, p["text"], said)
            pieces.append((t, audio))
            entries.append({"block": p["block"], "para": p["para"], "text": p["text"], "s": round(t, 3), "e": round(t + dur, 3),
                            "words": [{"w": x["w"], "n": norm(x["w"]), "s": round(x["s"] + t, 3), "e": round(x["e"] + t, 3)} for x in words],
                            "triggers": trig})
            t += dur
            if n + 1 < len(ch_paras):
                t += GAP_PARA if ch_paras[n + 1]["block"] == p["block"] else GAP_BLOCK
        t += tail_of(cfg, c)
        t = c_start + frame(t - c_start)
        chapters.append({"num": c, "start": c_start, "end": t})
    chapters[-1]["end"] = t = frame(t + cfg["end"])
    voice = np.zeros(int(t * SR) + SR, dtype=np.float32)
    for s, a in pieces:
        i = int(round(s * SR))
        voice[i:i + len(a)] += a
    return entries, voice[: int(t * SR)], t, chapters


def tts_audio(tts, script_path, paras):
    def f(p):
        name = f"{p['block']}-{p['para']}"
        meta = cached_paragraph(script_path, p, paras)
        audio, off = trim(load_audio(tts / f"{name}.mp3"))
        return audio, words_from(meta["alignment"], off), meta["spoken"]
    return f


def estimate_audio(p):
    """Silent audio with word timing by word length: enough to lay out and check graphics before recording."""
    toks = p["text"].split()
    weights = [len(t) + 1 + (3 if t[-1] in ".!?" else 0) for t in toks]
    dur = max(0.8, len(toks) / WPS)
    words, acc, i = [], 0.0, 0
    for tok, w in zip(toks, weights):
        a = dur * acc / sum(weights)
        acc += w
        b = dur * acc / sum(weights)
        words.append({"w": tok, "s": round(a, 3), "e": round(b - 0.05, 3), "i": i})
        i += len(tok) + 1
    return np.zeros(int(dur * SR), dtype=np.float32), words, p["text"]


def srt_time(x):
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def write_srt(entries, path, width=42):
    """Subtitles: paragraphs split into pieces of up to `width` characters at word boundaries."""
    cues = []
    for p in entries:
        chunk = []
        for w in p["words"]:
            chunk.append(w)
            text = " ".join(x["w"] for x in chunk)
            if len(text) > width or w["w"][-1] in ".?!":
                cues.append((chunk[0]["s"], chunk[-1]["e"], text))
                chunk = []
        if chunk:
            cues.append((chunk[0]["s"], chunk[-1]["e"], " ".join(x["w"] for x in chunk)))
    out = [f"{n}\n{srt_time(a)} --> {srt_time(b + 0.15)}\n{text}\n" for n, (a, b, text) in enumerate(cues, 1)]
    path.write_text("\n".join(out), encoding="utf-8")


MODULE = ('<script type="importmap">{"imports": {"three": "./lib/vendor/three/three.module.js", '
          '"three/addons/": "./lib/vendor/three/addons/"}}</script>\n'
          '    <script type="module" src="%s"></script>')


def composition(cid, dur, timing, scene_path, template="template.html", extra=""):
    """A composition file from a template: timing, style slots, scene script. A 3D module s<N>.mjs next to the
    scene joins by itself."""
    tpl = (HERE / template).read_text(encoding="utf-8")
    module = Path(scene_path).with_suffix(".mjs")
    if (HERE / module).exists():
        extra += MODULE % module.as_posix()
    html = (tpl.replace("{{ID}}", cid).replace("{{DUR}}", f"{dur:.2f}")
               .replace("{{TIMING}}", json.dumps(timing, ensure_ascii=False))
               .replace("{{WORLD}}", slot("world" if template == "template.html" else "world-v"))
               .replace("{{OVERLAY}}", slot("overlay" if template == "template.html" else "overlay-v"))
               .replace("{{SCENE}}", scene_path).replace("{{EXTRA}}", extra))
    (HERE / f"{cid}.html").write_text(html, encoding="utf-8")


def scene_stub(path, what):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"/* {what}. Scene code: see the graphics skill and engine/lib/kit.js.\n"
                    f"   Timing by the voice: W(\"1.1\", \"phrase\") is the second a phrase starts, TR(\"1.1\", \"word\") a trigger word.\n"
                    f"   Example:\n"
                    f"   const sc = scene(0, D);\n"
                    f"   const r = rich(sc, \"The [word]\", \"h1\", {{ left: \"128px\", top: \"400px\" }});\n"
                    f"   reveal(r.words, 0.3); */\n", encoding="utf-8")
    print(f"  created a stub scene {path.relative_to(HERE)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cut", metavar="DIR", help="folder with words.json and voice.wav / rough.mp4")
    g.add_argument("--tts", action="store_true")
    g.add_argument("--estimate", action="store_true")
    a = ap.parse_args()
    vid = VIDEOS / a.slug
    script_text = (vid / "script.md").read_text(encoding="utf-8")
    script, titles = parse_blocks(script_text), chapter_titles(script_text)
    out = BUILD / a.slug
    out.mkdir(parents=True, exist_ok=True)
    sync_style()

    if a.cut:
        entries, voice, total, chapters = from_cut(a.slug, Path(a.cut), script)
    else:
        paras = tts_paragraphs(vid / "script.md")
        audio_of = tts_audio(tts_dir(vid / "script.md"), vid / "script.md", paras) if a.tts else estimate_audio
        entries, voice, total, chapters = from_paragraphs(a.slug, paras, script, audio_of)

    wavfile.write(out / "voice.wav", SR, voice)
    rules = sounds()
    for i, c in enumerate(chapters):
        c["id"] = f"ch{c['num']}"
        c["dur"] = round(c["end"] - c["start"], 3)
        c["title"] = titles.get(c["num"], "")
        seg = voice[int(c["start"] * SR): int(c["end"] * SR)]
        wavfile.write(out / f"{c['id']}-voice.wav", SR, seg)
        blocks = {}
        for e in entries:
            if e["block"].split(".")[0] != c["num"]:
                continue
            rel = {**e, "s": round(e["s"] - c["start"], 3), "e": round(e["e"] - c["start"], 3),
                   "words": [{**w, "s": round(w["s"] - c["start"], 3), "e": round(w["e"] - c["start"], 3)} for w in e["words"]],
                   "triggers": [{**t, "t": round(t["t"] - c["start"], 3)} for t in e["triggers"]]}
            blocks.setdefault(e["block"], []).append(rel)
        cid = f"{a.slug}-{c['id']}"
        scene = SCENES / a.slug / f"{c['id']}.js"
        scene_stub(scene, f"{a.slug}, chapter {c['num']}: {c['title']}")
        timing = {"dur": c["dur"], "blocks": blocks, "fps": FPS,
                  "chapter": {"num": c["num"], "title": c["title"], "index": i + 1, "count": len(chapters)},
                  "sfx": {"main": rules["main"], "quiet": rules["quiet"], "gap": rules["gap"]}}
        composition(cid, c["dur"], timing, f"scenes/{a.slug}/{c['id']}.js")
    (out / "timing.json").write_text(json.dumps(
        {"slug": a.slug, "total": total, "fps": FPS,
         "chapters": [{k: c[k] for k in ("id", "num", "title", "start", "dur")} for c in chapters],
         "paragraphs": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    write_srt(entries, out / "subtitles.srt")
    print(f"{a.slug}: {total / 60:.1f} min; " + ", ".join(f"{c['id']} {c['dur']:.1f}s" for c in chapters) +
          f"\ncompositions: engine/{a.slug}-ch*.html; voice and timing: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
