#!/usr/bin/env python3
"""Speech-to-text with word timestamps for the cut: ElevenLabs Scribe.

  python3 engine/stt.py <recording.m4a|mp4|wav> <out.json> [--lang en]

Writes out.json in the format cut.py reads:
  {"text": "...", "words": [{"text": "hello", "start": 1.23, "end": 1.51, "type": "word"}, ...]}
`type` is "word" for speech, "audio_event" for noises the model marked ([laughs], [breath]);
spacing entries are dropped.

Another STT engine plugs in by writing the same JSON: only `words` with text/start/end/type matter.
Audio is extracted with ffmpeg to a mono 16 kHz mp3 first, so a long video upload stays small.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LANG  # noqa: E402
from tts_elevenlabs import API, api_key, check_response  # noqa: E402


def transcribe(path, lang=None, model="scribe_v1"):
    key = api_key()
    tmp = Path(tempfile.mkdtemp()) / "audio.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(tmp)], check=True)
    data = {"model_id": model, "timestamps_granularity": "word", "tag_audio_events": "true", "diarize": "false"}
    if lang:
        data["language_code"] = lang
    with open(tmp, "rb") as f:
        r = requests.post(f"{API}/speech-to-text", headers={"xi-api-key": key}, data=data,
                          files={"file": ("audio.mp3", f, "audio/mpeg")}, timeout=1800)
    check_response(r, "speech-to-text")
    d = r.json()
    words = [{"text": w.get("text", ""), "start": w.get("start"), "end": w.get("end"), "type": w.get("type", "word")}
             for w in d.get("words", []) if w.get("type") != "spacing"]
    return {"text": d.get("text", ""), "language": d.get("language_code"), "words": words}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("out")
    ap.add_argument("--lang", default=LANG, help="ISO code; empty string lets the model detect")
    a = ap.parse_args()
    d = transcribe(a.recording, a.lang or None)
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(1 for w in d["words"] if w["type"] == "word")
    print(f"{n} words -> {a.out}")


if __name__ == "__main__":
    main()
