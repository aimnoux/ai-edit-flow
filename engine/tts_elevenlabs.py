#!/usr/bin/env python3
"""ElevenLabs helpers shared by voice.py, stt.py and vertical.py, plus a small CLI.

  python3 engine/tts_elevenlabs.py --list-voices
  python3 engine/tts_elevenlabs.py --clone recording.m4a --name "My voice"   # instant clone -> voice_id
  python3 engine/tts_elevenlabs.py --say "A test line" --voice <id> [--model eleven_v3] [--out test.mp3]

The key comes from ELEVENLABS_API_KEY (environment or .env in the repository root).
Script parsing (`parse_blocks`, `strip_triggers`) lives here too because every script reads it.
"""
import argparse
import base64
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CFG, LANG  # noqa: E402

API = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = (CFG.get("voice") or {}).get("model_id") or "eleven_v3"


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("No ELEVENLABS_API_KEY: put it into .env in the repository root")
    return key


def parse_blocks(script_text):
    """{'1.1': ['paragraph', ...], ...} in script order: speech only, no notes.
    A block is `### N.M`; blank lines separate paragraphs, wrapped lines join with spaces.
    Notes, tables and headings end the current paragraph; chapter/block headings end the block."""
    blocks = {}
    current, lines = None, []

    def flush():
        if lines:
            blocks[current].append(" ".join(lines))
            lines.clear()

    for raw in script_text.splitlines():
        line = raw.strip()
        heading = re.match(r"^(#{1,6})(?:\s+|$)", line)
        if heading:
            flush()
            block = re.match(r"^###\s+(\d+\.\d+)(?:\s|$)", line)
            if block:
                current = block.group(1)
                blocks[current] = []
            elif len(heading.group(1)) <= 3:
                current = None
            continue
        if not line or line.startswith((">", "|", "---")):
            flush()
        elif current is not None:
            lines.append(line)
    flush()
    return blocks


def chapter_titles(script_text):
    """{'1': 'The question', ...} from `## N. Title` headings."""
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"^## (\d+)\.\s+(.+)$", script_text, re.M)}


def strip_triggers(text):
    """Removes [brackets]; returns the text and (word, offset) of every trigger."""
    out, triggers, pos = [], [], 0
    for m in re.finditer(r"\[([^\]]+)\]", text):
        out.append(text[pos:m.start()])
        offset = sum(map(len, out))
        triggers.append((m.group(1), offset))
        out.append(m.group(1))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out), triggers


def post(url, **kw):
    """POST with retries: the connection sometimes drops mid-generation."""
    for attempt in range(3):
        try:
            return requests.post(url, timeout=600, **kw)
        except requests.ConnectionError:
            if attempt == 2:
                raise
            print("  connection dropped, retrying")


def check_response(r, what):
    """Exit with a readable message on an API error or on an HTML page instead of JSON
    (a network filter or a blocked region answers with HTML)."""
    if "html" in r.headers.get("content-type", ""):
        sys.exit(f"{what}: ElevenLabs answered with an HTML page instead of data. Check the network (VPN, proxy) and try again; stop after three failed attempts and tell the person.")
    if not r.ok:
        sys.exit(f"{what}: {r.status_code} {r.text[:300]}")


def synthesis_request(voice, model, text, previous=None, nxt=None, settings=None):
    """The exact non-secret request, shared with the content-addressed audio cache."""
    body = {"text": text, "model_id": model}
    if not model.startswith("eleven_multilingual"):
        body["language_code"] = LANG
    if previous:
        body["previous_text"] = previous
    if nxt:
        body["next_text"] = nxt
    if settings:
        body["voice_settings"] = settings
    return {"voice": voice, "body": body, "params": {"output_format": "mp3_44100_128"}}


def synthesize(key, voice, model, text, previous=None, nxt=None, settings=None):
    """One paragraph with character timestamps. previous/nxt give the model the neighbours for intonation."""
    request = synthesis_request(voice, model, text, previous, nxt, settings)
    r = post(f"{API}/text-to-speech/{voice}/with-timestamps", headers={"xi-api-key": key},
             json=request["body"], params=request["params"])
    check_response(r, "text-to-speech")
    data = r.json()
    return base64.b64decode(data["audio_base64"], validate=True), data["alignment"]


def list_voices(key):
    r = requests.get(f"{API}/voices", headers={"xi-api-key": key}, timeout=60)
    r.raise_for_status()
    for v in r.json()["voices"]:
        labels = ", ".join(f"{k}: {x}" for k, x in (v.get("labels") or {}).items())
        print(f"{v['voice_id']}  {v['name']}  [{v.get('category')}]  {labels}")


def clone(key, sample, name):
    with open(sample, "rb") as f:
        r = requests.post(f"{API}/voices/add", headers={"xi-api-key": key},
                          data={"name": name, "description": "Instant clone made by ai-edit-flow"},
                          files={"files": (Path(sample).name, f)}, timeout=300)
    if not r.ok:
        sys.exit(f"Clone failed: {r.status_code} {r.text[:300]}")
    vid = r.json()["voice_id"]
    print(f"voice_id: {vid}\nPut it into style/config.json -> voice.voice_id")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list-voices", action="store_true")
    p.add_argument("--clone", metavar="SAMPLE", help="create an instant clone from a recording (1-5 minutes of clean speech)")
    p.add_argument("--name", default="My voice")
    p.add_argument("--say", help="synthesize one line as a test")
    p.add_argument("--voice", default=(CFG.get("voice") or {}).get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID"))
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--out", default="test.mp3")
    a = p.parse_args()
    key = api_key()
    if a.list_voices:
        return list_voices(key)
    if a.clone:
        return clone(key, a.clone, a.name)
    if a.say:
        if not a.voice:
            p.error("--voice <id> is needed (from --list-voices or --clone, or style/config.json)")
        audio, _ = synthesize(key, a.voice, a.model, a.say)
        Path(a.out).write_bytes(audio)
        return print(a.out)
    p.print_help()


if __name__ == "__main__":
    main()
