#!/usr/bin/env python3
"""Voicing a script with a cloned voice (ElevenLabs), paragraph by paragraph.

  python3 engine/voice.py videos/<slug>/script.md            # horizontal video
  python3 engine/voice.py vertical/<batch>.md [1,3]          # vertical batch, optionally only these videos (and endings)

Each paragraph is one request with the neighbouring paragraphs as context (previous_text / next_text),
so pauses between paragraphs are placed by build.py and word timing is exact. Finished paragraphs are
not regenerated when their full request is unchanged: cached runs need no API key.
Changed text, neighbours, voice, model or settings revoice the affected requests.

Writes next to the script, in tts/<script name>-<voice>-<model>/ (not in git):
  <block>-<paragraph>.mp3 + .json   audio and character timing ("spoken" is the text that was sent)

Voice, model and the pronunciation map come from style/config.json ("voice"). `say` maps a written
word to how it should be read ("ML": "em-el"); subtitles and the words scenes see stay as written.

Dialogue: a paragraph `boss: {angry} Text` is voiced by voice.speakers.boss (voice_id and settings; an
empty voice_id means voice.voice_id). {angry} goes to the model as the audio tag [angry] and is cut from
the text, the timing and the subtitles. The cache key holds the voice and the tag, so changing one
speaker's voice revoices only that speaker's lines.
"""
import json
import hashlib
import math
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CFG  # noqa: E402
from tts_elevenlabs import LINE, SPEAKERS, api_key, parse_blocks, split_line, strip_triggers, synthesize, synthesis_request  # noqa: E402

VOICE_CFG = CFG.get("voice") or {}
VOICE = VOICE_CFG.get("voice_id") or ""
MODEL = VOICE_CFG.get("model_id") or "eleven_v3"
SETTINGS = {k: v for k, v in (VOICE_CFG.get("settings") or {}).items() if k != "_"}
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
    """Paragraphs of a script: block, index, speaker, tags, text, triggers. Slates (N.0) are skipped."""
    out = []
    for bid, paras in parse_blocks(Path(script_path).read_text(encoding="utf-8")).items():
        if SLATE.search(bid):
            continue
        for k, raw in enumerate(paras):
            who, tags, line = split_line(raw, SPEAKERS)
            text, trig = strip_triggers(line)
            out.append({"block": bid, "para": k, "text": text, "triggers": [w for w, _ in trig], "offs": [o for _, o in trig],
                        "who": who, "tags": tags})
    # Inside a dialogue a line with an unknown name would be read aloud together with the name.
    dialogue = {p["block"].split(".")[0] for p in out if p["who"]}
    for p in out:
        if p["block"].split(".")[0] in dialogue and not p["who"] and LINE.match(p["text"]):
            raise ValueError(f"Unknown speaker in {p['block']}: {p['text'][:70]!r}. Add it to style/config.json -> voice.speakers.")
    return out


def voice_of(p):
    return (SPEAKERS.get(p.get("who")) or {}).get("voice_id") or VOICE


def settings_of(p):
    own = (SPEAKERS.get(p.get("who")) or {}).get("settings") or {}
    return {k: v for k, v in own.items() if k != "_"} or SETTINGS


def tag_prefix(p):
    """Audio tags in front of the spoken text. Only eleven_v3 performs them; other models read them out."""
    if p.get("tags") and not MODEL.startswith("eleven_v3"):
        raise ValueError(f"Tags in {p['block']} need the eleven_v3 model, not {MODEL}")
    return "".join(f"[{t}] " for t in p.get("tags") or [])


def cut_prefix(alignment, prefix):
    """The tag comes back as the first characters of the timing and has no sound: words start with the speech."""
    if "".join(alignment["characters"][:len(prefix)]) != prefix:
        raise ValueError(f"Tag {prefix!r} is not at the start of the timing")
    return {k: v[len(prefix):] for k, v in alignment.items()}


def tts_dir(script_path):
    script_path = Path(script_path)
    return script_path.parent / "tts" / f"{script_path.stem}-{VOICE[:6]}-{MODEL}"


def is_ending(block):
    return block.split(".")[1] in ("8", "9")


def request_for(paras, i):
    """Use the complete script so selecting a batch subset cannot alter its context."""
    p = paras[i]
    roll = p["block"].split(".")[0]
    same = lambda j: (0 <= j < len(paras) and paras[j]["block"].split(".")[0] == roll
                      and not is_ending(paras[j]["block"]))
    prev = nxt = None
    if is_ending(p["block"]):
        body = [q for q in paras[:i] if q["block"].split(".")[0] == roll and not is_ending(q["block"])]
        prev = spoken(body[-1]["text"]) if body else None
    else:
        prev = spoken(paras[i - 1]["text"]) if same(i - 1) else None
        nxt = spoken(paras[i + 1]["text"]) if same(i + 1) else None
    return synthesis_request(voice_of(p), MODEL, tag_prefix(p) + spoken(p["text"]), prev, nxt, settings_of(p))


def request_key(request):
    return hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def valid_alignment(meta):
    try:
        a = meta["alignment"]
        chars, starts, ends = (a[k] for k in ("characters", "character_start_times_seconds", "character_end_times_seconds"))
        return (isinstance(chars, list) and isinstance(starts, list) and isinstance(ends, list)
                and bool(chars) and all(isinstance(c, str) and len(c) == 1 for c in chars)
                and "".join(chars) == meta["spoken"] and len(chars) == len(starts) == len(ends)
                and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in starts + ends)
                and all(a <= b for a, b in zip(starts, ends))
                and all(a <= b for a, b in zip(starts, starts[1:]))
                and all(a <= b for a, b in zip(ends, ends[1:])))
    except (KeyError, TypeError, ValueError):
        return False


def read_cache(mp3, js, request):
    """Legacy text-only caches cannot prove voice, settings or context; regenerate them once."""
    try:
        audio = mp3.read_bytes()
        meta = json.loads(js.read_text(encoding="utf-8"))
        if (not audio or not isinstance(meta, dict) or meta.get("request") != request
                or meta.get("cache_key") != request_key(request)
                or meta.get("audio_sha256") != hashlib.sha256(audio).hexdigest()
                or meta.get("prefix", "") + meta["spoken"] != request["body"]["text"] or not valid_alignment(meta)):
            return None
        return meta
    except (OSError, ValueError, TypeError, KeyError):
        return None


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_meta(path, meta):
    atomic_bytes(path, json.dumps(meta, ensure_ascii=False, indent=1, allow_nan=False).encode())


def cached_paragraph(script, p, paras=None):
    """Consumers must reject stale indexed audio rather than build it into a new script."""
    paras = paragraphs(script) if paras is None else paras
    i = next(i for i, q in enumerate(paras) if q["block"] == p["block"] and q["para"] == p["para"])
    name = f"{p['block']}-{p['para']}"
    directory = tts_dir(script)
    meta = read_cache(directory / f"{name}.mp3", directory / f"{name}.json", request_for(paras, i))
    if meta is None:
        raise ValueError(f"Missing or stale voice {name}; run python engine/voice.py {script}")
    return meta


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    script = Path(sys.argv[1])
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set()
    paras = paragraphs(script)
    selected = [(i, p) for i, p in enumerate(paras) if not only or p["block"].split(".")[0] in only]
    if not all(voice_of(p) for _, p in selected):
        sys.exit("No voice: put voice_id into style/config.json (python3 engine/tts_elevenlabs.py --list-voices or --clone)")
    voices = {p["who"]: voice_of(p) for _, p in selected if p["who"]}
    if len(set(voices.values())) < len(voices):
        print(f"  warning: speakers share one voice: {', '.join(sorted(voices))}; see voice.speakers in style/config.json")
    key = None  # Fully cached runs need no credentials or network.
    out = tts_dir(script)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(selected)} paragraphs, {sum(len(p['text']) for _, p in selected)} characters -> {out}")
    # Snapshot every valid indexed entry before an insertion can overwrite its old index.
    for js in out.glob("*.json"):
        try:
            candidate = json.loads(js.read_text(encoding="utf-8"))
            request = candidate.get("request") if isinstance(candidate, dict) else None
            meta = read_cache(js.with_suffix(".mp3"), js, request) if isinstance(request, dict) else None
            if meta:
                cache = out / "cache" / request_key(request)
                atomic_bytes(cache.with_suffix(".mp3"), js.with_suffix(".mp3").read_bytes())
                write_meta(cache.with_suffix(".json"), meta)
        except (OSError, ValueError, TypeError, KeyError):
            continue
    for i, p in selected:
        name = f"{p['block']}-{p['para']}"
        mp3, js = out / f"{name}.mp3", out / f"{name}.json"
        request = request_for(paras, i)
        cache = out / "cache" / request_key(request)
        old = read_cache(cache.with_suffix(".mp3"), cache.with_suffix(".json"), request)
        if old:
            atomic_bytes(mp3, cache.with_suffix(".mp3").read_bytes())
            write_meta(js, old)
            continue
        key = key or api_key()
        body = request["body"]
        audio, alignment = synthesize(key, request["voice"], MODEL, body["text"], body.get("previous_text"),
                                      body.get("next_text"), body.get("voice_settings"))
        prefix = tag_prefix(p)
        meta = {"spoken": body["text"][len(prefix):], "alignment": cut_prefix(alignment, prefix), "prefix": prefix, "request": request,
                "cache_key": request_key(request), "audio_sha256": hashlib.sha256(audio).hexdigest()}
        if not audio or not valid_alignment(meta):
            raise ValueError(f"{name}: empty audio or invalid character timing from API")
        atomic_bytes(cache.with_suffix(".mp3"), audio)
        write_meta(cache.with_suffix(".json"), meta)
        atomic_bytes(mp3, audio)
        write_meta(js, meta)
        print(f"  {name} ok")
    write_meta(out / "paragraphs.json", paras)


if __name__ == "__main__":
    main()
