#!/usr/bin/env python3
"""Rough cut of a recording against the script: last take wins, broken phrases and long pauses go.

  python3 engine/cut.py <recording> <stt.json> <script.md> <out_dir> [--audio clean.wav] [--drop drops.json] [--fps 30]

stt.json comes from engine/stt.py (word timestamps). Words are matched to the script: when the speech
jumps back in the text (a phrase started again, a retake), everything from the previous attempt that
got repeated is dropped, so the last take stays. Broken words ("today--"), fillers and pauses longer
than LONG_GAP are cut. A script paragraph becomes a GAP_PARA pause, inside a paragraph GAP_IN.

--drop drops.json: manual take marking instead of the automatic one, a list of [start, end] in
seconds of the source; words that start inside are dropped. Audio events from the transcript
([breath], [laughs]) are never bridged by a cut: the pause at their place is removed.
--audio: a cleaned track of the same length as the recording (used for the output and for the
speech mask); without it the recording's own audio is used.

Writes out_dir/words.json (words on the cut timeline with their script block and paragraph),
out_dir/edl.json (what was kept and what was dropped, with reasons), and out_dir/rough.mp4 for
video recordings or out_dir/voice.wav for audio-only recordings.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CFG, ffmpeg_filter_file, norm  # noqa: E402
from tts_elevenlabs import parse_blocks, strip_triggers  # noqa: E402

GAP_IN = 0.25      # pause inside a paragraph
GAP_PARA = 0.6     # pause between script paragraphs
PAD_IN, PAD_OUT = 0.06, 0.12
LONG_GAP = 0.45    # pauses longer than this are shortened
FILLERS = set(["uh", "um", "er", "erm", "ah", "mm", "hmm", "mhm"] + list(CFG.get("fillers") or []))   # your language's fillers: style/config.json -> fillers


def video_stream_index(path):
    """First actual video stream, ignoring an audio file's embedded cover art."""
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                             "stream=index:stream_disposition=attached_pic", "-of", "json", str(path)],
                            capture_output=True, text=True, check=True)
    return next((s["index"] for s in json.loads(result.stdout)["streams"]
                 if not s.get("disposition", {}).get("attached_pic")), None)


def speech_mask(path, hop=0.02):
    """Per 20 ms: is there voice here, by loudness of the (cleaned) audio."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    n = int(hop * 16000)
    rms = np.sqrt((x[: len(x) // n * n].reshape(-1, n) ** 2).mean(1))
    ref = np.percentile(rms, 95)
    return rms > ref * 0.1, hop


def silent(mask, hop, a, b):
    """Pause [a, b] without speech: voice in less than 10 % of the frames."""
    i, j = int(a / hop), int(b / hop)
    seg = mask[i:j]
    return len(seg) == 0 or seg.mean() < 0.1


def script_words(path):
    out = []  # (word key, block, "block/paragraph")
    for bid, paras in parse_blocks(Path(path).read_text(encoding="utf-8")).items():
        for k, raw in enumerate(paras):
            text, _ = strip_triggers(raw)
            for w in text.split():
                n = norm(w)
                if n:
                    out.append((n, bid, f"{bid}/{k}"))
    return out


def similar(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    k = min(len(a), len(b), 5)
    return k >= 3 and a[:k] == b[:k]


def align(words, sw):
    """Every spoken word -> position in the script (or None), monotonic with jumps back."""
    pos, out = 0, []
    for i, w in enumerate(words):
        n = norm(w["text"])
        nxt = norm(words[i + 1]["text"]) if i + 1 < len(words) else ""
        best = None
        for j in range(pos, min(len(sw), pos + 8)):          # forward: the usual case
            if similar(n, sw[j][0]):
                best = j
                break
        if best is None:
            # backward: a phrase restarted; the word and the one after it must both match the script
            for j in range(pos - 1, max(-1, pos - 80), -1):
                if similar(n, sw[j][0]) and (not nxt or any(similar(nxt, sw[q][0]) for q in range(j + 1, min(len(sw), j + 3)))):
                    best = j
                    break
        out.append(best)
        if best is not None:
            pos = best + 1
    return out


def align_global(words, keep, sw):
    """Manual mode: takes are already dropped, speech is monotonic; align the kept words to the whole
    script (difflib on word prefixes); unmatched words inherit the position of the neighbour on the left."""
    import difflib
    key = lambda n: n[:5]
    ids = [i for i in range(len(words)) if keep[i]]
    a = [key(norm(words[i]["text"])) for i in ids]
    b = [key(x[0]) for x in sw]
    idx = [None] * len(words)
    for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for q in range(m.size):
            idx[ids[m.a + q]] = m.b + q
    last = None
    for i in ids:
        if idx[i] is None:
            idx[i] = last
        last = idx[i]
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("stt"); ap.add_argument("script"); ap.add_argument("out")
    ap.add_argument("--audio", help="cleaned audio of the same length as the recording")
    ap.add_argument("--drop", help="JSON list of [start, end]: manual take marking")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    raw_words = json.loads(Path(a.stt).read_text(encoding="utf-8"))["words"]
    words = [w for w in raw_words if w.get("type") == "word" and norm(w["text"])]
    events = [(w["start"], w["end"]) for w in raw_words if w.get("type") == "audio_event"]
    drops = [tuple(r[:2]) for r in json.loads(Path(a.drop).read_text(encoding="utf-8"))] if a.drop else []
    sw = script_words(a.script)
    idx = align(words, sw)

    keep = [True] * len(words)
    reason = [""] * len(words)
    # a jump back in the script = a retake: drop the previous attempt from the same position
    hi = -1
    for i, j in enumerate(idx):
        if drops:
            break
        if j is None:
            continue
        if j <= hi:
            for p in range(i - 1, -1, -1):
                if idx[p] is not None and idx[p] < j:
                    break
                if keep[p]:
                    keep[p], reason[p] = False, "retake"
        hi = max(hi, j) if j > hi else j
    for i, w in enumerate(words):
        if any(s <= w["start"] < e for s, e in drops):
            keep[i], reason[i] = False, "manual"
    # broken words and fillers
    for i, w in enumerate(words):
        t = w["text"]
        if t.endswith("--") or t.endswith("—") or norm(t) in FILLERS:
            keep[i], reason[i] = False, "broken"
    if drops:
        idx = align_global(words, keep, sw)

    # segments: runs of kept words, pauses shortened
    mask, hop = speech_mask(a.audio or a.video)
    # STT sometimes stretches a word over the pause after it: trim word edges by the voice mask
    for w in words:
        i, j = int(w["start"] / hop), int(w["end"] / hop)
        voiced = mask[i:j].nonzero()[0]
        if len(voiced):
            holes = [k for k in range(len(voiced) - 1) if (voiced[k + 1] - voiced[k]) * hop > 0.3]
            last = voiced[holes[0]] if holes else voiced[-1]
            if (j - i - 1 - last) * hop > 0.3:
                w["end"] = (i + last + 1) * hop + 0.05
            if voiced[0] * hop > 0.3:
                w["start"] = (i + voiced[0]) * hop - 0.05
    kept = [i for i in range(len(words)) if keep[i]]
    if not kept:
        sys.exit("nothing kept: check the script and the transcript")
    segs = []
    for n, i in enumerate(kept):
        w = words[i]
        s, e = w["start"] - PAD_IN, w["end"] + PAD_OUT
        if i > 0 and not keep[i - 1]:
            s = max(s, words[i - 1]["end"])
        if i + 1 < len(words) and not keep[i + 1]:
            e = min(e, words[i + 1]["start"])
        pe = words[kept[n - 1]]["end"] if n else 0
        event = any(a0 < w["start"] and a1 > pe for a0, a1 in events)
        if segs and n and kept[n - 1] == i - 1 and not event and (w["start"] - pe <= LONG_GAP or not silent(mask, hop, pe + 0.05, w["start"] - 0.05)):
            segs[-1]["e"] = e
            segs[-1]["last"] = i
            continue
        if segs:
            prev = kept[n - 1]
            para_prev = sw[idx[prev]][2] if idx[prev] is not None else None
            para_cur = sw[idx[i]][2] if idx[i] is not None else None
            segs[-1]["gap_after"] = GAP_PARA if para_prev and para_cur and para_prev != para_cur else GAP_IN
        segs.append({"s": max(0.0, s), "e": e, "first": i, "last": i, "gap_after": 0.0})
    # after a segment keep the needed pause out of the real silence that follows
    for k, sg in enumerate(segs[:-1]):
        limit = segs[k + 1]["s"]
        nxt = sg["last"] + 1
        if nxt < len(words) and not keep[nxt]:
            limit = min(limit, words[nxt]["start"] - 0.02)
        limit = min([limit] + [a0 for a0, _ in events if a0 >= sg["e"] - 0.01])
        room = limit - sg["e"]
        sg["e"] += max(0.0, min(sg["gap_after"] - PAD_IN - PAD_OUT, room))

    total = sum(sg["e"] - sg["s"] for sg in segs)
    cut_words, off = [], 0.0
    for sg in segs:
        for q in range(sg["first"], sg["last"] + 1):
            if keep[q]:
                w = words[q]
                j = idx[q]
                cut_words.append({"w": w["text"], "s": round(off + w["start"] - sg["s"], 3), "e": round(off + w["end"] - sg["s"], 3),
                                  "block": sw[j][1] if j is not None else None, "para": sw[j][2] if j is not None else None})
        off += sg["e"] - sg["s"]
    (out / "words.json").write_text(json.dumps(cut_words, ensure_ascii=False, indent=0), encoding="utf-8")
    dropped = [{"t": round(words[i]["start"], 2), "word": words[i]["text"], "why": reason[i]} for i in range(len(words)) if not keep[i]]
    (out / "edl.json").write_text(json.dumps({"segments": [{"s": round(x["s"], 3), "e": round(x["e"], 3),
        "text": " ".join(words[q]["text"] for q in range(x["first"], x["last"] + 1) if keep[q])} for x in segs],
        "dropped": dropped, "duration": round(total, 2)}, ensure_ascii=False, indent=1), encoding="utf-8")

    # render: trim every piece + concat, short fades at the audio joins
    vi = video_stream_index(a.video)
    has_video = vi is not None
    parts, inputs = [], ["-i", a.video] + (["-i", a.audio] if a.audio else [])
    ai = "1:a" if a.audio else "0:a:0"
    for k, sg in enumerate(segs):
        d = sg["e"] - sg["s"]
        if has_video:
            parts.append(f"[0:{vi}]trim={sg['s']:.3f}:{sg['e']:.3f},setpts=PTS-STARTPTS,fps={a.fps}[v{k}];")
        parts.append(f"[{ai}]atrim={sg['s']:.3f}:{sg['e']:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"afade=t=in:d=0.01,afade=t=out:st={max(0, d - 0.015):.3f}:d=0.015[a{k}];")
    cat = "".join((f"[v{k}]" if has_video else "") + f"[a{k}]" for k in range(len(segs)))
    fc = "".join(parts) + f"{cat}concat=n={len(segs)}:v={int(has_video)}:a=1" + ("[v]" if has_video else "") + "[a];[a]loudnorm=I=-16:TP=-1.5:LRA=11[an]"
    (out / "filter.txt").write_text(fc, encoding="utf-8")
    if has_video:
        target = out / "rough.mp4"
        output_args = ["-map", "[v]", "-map", "[an]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        target = out / "voice.wav"
        output_args = ["-map", "[an]", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s24le"]
    ffmpeg_filter_file(inputs, out / "filter.txt", [*output_args, str(target)])
    # A reused cut directory must not let downstream builders prefer an older audio-only result.
    (out / ("voice.wav" if has_video else "rough.mp4")).unlink(missing_ok=True)
    print(f"segments {len(segs)}, dropped words {len(dropped)}, duration {total:.1f} s -> {target}")


if __name__ == "__main__":
    main()
