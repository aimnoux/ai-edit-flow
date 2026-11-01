#!/usr/bin/env python3
"""Voicing a script with a cloned voice (ElevenLabs), paragraph by paragraph.

  python3 engine/voice.py videos/<slug>/script.md            # horizontal video
  python3 engine/voice.py vertical/<batch>.md [1,3]          # vertical batch, optionally only these videos (and endings)

Each paragraph is one request with the neighbouring paragraphs as context (previous_text / next_text),
so pauses between paragraphs are placed by build.py and word timing is exact. Finished paragraphs are
not regenerated: a repeated run costs no credits. A paragraph whose text changed is re-voiced.

Writes next to the script, in tts/<script name>-<voice>-<model>/ (not in git):
  <block>-<paragraph>.mp3 + .json   audio and character timing ("spoken" is the text that was sent)

Voice, model and the pronunciation map come from style/config.json ("voice"). `say` maps a written
word to how it should be read ("ML": "em-el"); subtitles and the words scenes see stay as written.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CFG  # noqa: E402
from tts_elevenlabs import api_key, parse_blocks, strip_triggers, synthesize  # noqa: E402

VOICE_CFG = CFG.get("voice") or {}
VOICE = VOICE_CFG.get("voice_id") or ""
MODEL = VOICE_CFG.get("model_id") or "eleven_v3"
SAY = {k: v for k, v in (VOICE_CFG.get("say") or {}).items() if k != "_"}
_SAY_RE = re.compile("|".join(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])" for a in sorted(SAY, key=len, reverse=True))) if SAY else None
SLATE = re.compile(r"\.0$")   # N.0 blocks are slates for the cut, never voiced


def spoken_map(text):
    """Text for the voice and, for each of its characters, where it comes from in the source (start, end)."""
    if not _SAY_RE:
        return text, [(k, k + 1) for k in range(len(text))]
    out, src, pos = [], [], 0
    for m in _SAY_RE.finditer(text):
        out.append(text[pos:m.start()])
        src += [(k, k + 1) for k in range(pos, m.start())]
        out.append(SAY[m.group()])
        src += [(m.start(), m.end())] * len(SAY[m.group()])
        pos = m.end()
    out.append(text[pos:])
    src += [(k, k + 1) for k in range(pos, len(text))]
    return "".join(out), src


def spoken(text):
    return spoken_map(text)[0]


def written(words, text, said):
    """Words of the voice timing (over the spoken text `said`) -> as written in the script:
    "em-el engineer" -> "ML engineer", a replacement of two words becomes one word for the whole time.
    If the cached voice was made with other `say` rules and the text doesn't match, words stay as they are."""
    sp, src = spoken_map(text)
    if sp != said:
        return words
    out = []
    for w in words:
        span = src[w["i"]: w["i"] + len(w["w"])]
        if not span:
            out.append(w)
            continue
        a, b = min(x[0] for x in span), max(x[1] for x in span)
        if out and out[-1].get("_span") and out[-1]["_span"][0] <= a < out[-1]["_span"][1]:
            out[-1]["e"] = w["e"]
            continue
        out.append({**w, "w": text[a:b], "_span": (a, b)})
    for w in out:
        w.pop("_span", None)
    return out


def find_said(said, word, start=0):
    """Where in the spoken text a script word (a trigger) is, by the `say` rules or as written."""
    k = said.find(spoken(word), start)
    return k if k >= 0 else said.find(word, start)


def paragraphs(script_path):
    """Paragraphs of a script: block, index, text, triggers. Slates (N.0) are skipped."""
    out = []
    for bid, paras in parse_blocks(Path(script_path).read_text(encoding="utf-8")).items():
        if SLATE.search(bid):
            continue
        for k, raw in enumerate(paras):
            text, trig = strip_triggers(raw)
            out.append({"block": bid, "para": k, "text": text, "triggers": [w for w, _ in trig], "offs": [o for _, o in trig]})
    return out


def tts_dir(script_path):
    script_path = Path(script_path)
    return script_path.parent / "tts" / f"{script_path.stem}-{VOICE[:6]}-{MODEL}"


def is_ending(block):
    return block.split(".")[1] in ("8", "9")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if not VOICE:
        sys.exit("No voice: put voice_id into style/config.json (python3 engine/tts_elevenlabs.py --list-voices or --clone)")
    script = Path(sys.argv[1])
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set()
    paras = paragraphs(script)
    if only:
        paras = [p for p in paras if p["block"].split(".")[0] in only]
    key = api_key()
    out = tts_dir(script)
    out.mkdir(parents=True, exist_ok=True)
    (out / "paragraphs.json").write_text(json.dumps(paras, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(paras)} paragraphs, {sum(len(p['text']) for p in paras)} characters -> {out}")
    for i, p in enumerate(paras):
        name = f"{p['block']}-{p['para']}"
        mp3, js = out / f"{name}.mp3", out / f"{name}.json"
        old = json.loads(js.read_text(encoding="utf-8")) if js.exists() else {}
        if mp3.exists() and old.get("spoken") == spoken(p["text"]):
            continue
        roll = p["block"].split(".")[0]
        same = lambda j: 0 <= j < len(paras) and paras[j]["block"].split(".")[0] == roll and not is_ending(paras[j]["block"])
        prev = nxt = None
        if is_ending(p["block"]):   # an ending follows the body of its video: context is the body's last paragraph
            body = [q for q in paras[:i] if q["block"].split(".")[0] == roll and not is_ending(q["block"])]
            prev = spoken(body[-1]["text"]) if body else None
        else:
            prev = spoken(paras[i - 1]["text"]) if same(i - 1) else None
            nxt = spoken(paras[i + 1]["text"]) if same(i + 1) else None
        audio, alignment = synthesize(key, VOICE, MODEL, spoken(p["text"]), prev, nxt)
        mp3.write_bytes(audio)
        js.write_text(json.dumps({"spoken": spoken(p["text"]), "alignment": alignment}, ensure_ascii=False), encoding="utf-8")
        print(f"  {name} ok")


if __name__ == "__main__":
    main()
