# engine/

Scripts and a small library for building videos. The project folder for HyperFrames is this one:
compositions (`<project>-ch1.html`, `<project>-s1-yt.html`) are generated here and ignored by git,
scenes live in `scenes/<project>/`, outputs in `build/` and `renders/`.

Run every script from the repository root with `python3 engine/<script>.py`; HyperFrames through
`node engine/hf.mjs <command>` (the version is pinned in `package.json`). Preview: `.claude/launch.json`,
`engine` (port 8790), or `python3 engine/serve.py`.

| File | What it does |
|---|---|
| `common.py` | Paths, `style/config.json`, Chrome lookup, GSAP fetch, style sync into `lib/` |
| `tts_elevenlabs.py` | ElevenLabs API, script parsing (`parse_blocks`, `strip_triggers`), `--list-voices`, `--clone` |
| `stt.py` | Speech-to-text with word timestamps (ElevenLabs Scribe) -> JSON for `cut.py` |
| `cut.py` | Rough cut of a recording by the script: last take, no fillers, pauses shortened -> `words.json`, `rough.mp4` |
| `pad_chapters.py` | Silence between chapters of a live-voice cut for titles and outros (`video.json`) |
| `voice.py` | Cloned voice paragraph by paragraph with word timing, cached |
| `build.py` | Horizontal video: timeline, chapter compositions, voice tracks, subtitles (`--cut`, `--tts`, `--estimate`) |
| `vertical.py` | Vertical video: `build`, `silent`, `shots`, `render` |
| `check.py` | Script errors in compositions and the cue count, headless Chrome, no render |
| `shots.py` | Contact sheet of frames at given seconds |
| `review.py` | Sheets and `REVIEW-INPUT.md` for the frame review |
| `mix.py`, `mix_piece.py` | Mix: voice -16 LUFS, effects at cues from `style/sound/`, music with ducking, final -14 LUFS |
| `compare.py` | Before/after as one video: `stack`, `grid`, `seq`, `chapter`, `mix` |
| `render.sh` | Full render of a horizontal video: chapters -> mix -> final MP4 and SRT |
| `serve.py` | Preview server without caching |
| `hf.mjs` | HyperFrames CLI at the pinned version |
| `lib/kit.js` | Timing by words (`W`, `WE`, `B`, `P`, `TR`), scenes, `rich`/`reveal`/`follow`, `glow`, lists, chapter title, `typeText`, camera |
| `lib/vertical.js` | 9:16: `slam`, `vtext`, `chip`, `vcard`, `chatWindow`, `docSheet`, `stamp`, `memeFrame`, captions, platform ending |
| `lib/finish.js` | Timeline registration, cue filter, scene bounds |
| `lib/style.css`, `lib/vertical.css` | Structure only; looks come from `lib/tokens.css` (copied from `style/`) |
| `template.html`, `template-v.html` | Layer skeleton: world (style slot) -> stage -> hud -> overlay (style slot) |

## Horizontal video, live voice

```
python3 engine/stt.py recording.m4a videos/<slug>/cut/stt.json
python3 engine/cut.py recording.m4a videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut [--drop videos/<slug>/drops.json]
python3 engine/pad_chapters.py <slug> [--voice cleaned.wav]
python3 engine/build.py <slug> --cut videos/<slug>/cut/pad
python3 engine/check.py --project <slug> --hf
python3 engine/shots.py <slug>-ch1 0.5 3 8
python3 engine/review.py <slug>-ch1
MUSIC=track.mp3 bash engine/render.sh <slug>
```

## Horizontal video, cloned voice

```
python3 engine/voice.py videos/<slug>/script.md
python3 engine/build.py <slug> --tts
bash engine/render.sh <slug>
```

## Vertical video

```
python3 engine/voice.py vertical/<batch>.md 1
python3 engine/vertical.py build vertical/<batch>.md 1 yt
python3 engine/vertical.py shots <batch>-s1-yt 0.5 3 8
python3 engine/review.py <batch>-s1-yt
python3 engine/vertical.py render <batch>-s1-yt [--music track.mp3]
```

Composition names: `<project>-ch<N>` for chapters of `videos/<project>/`, `<project>-s<N>-<platform>` for
vertical videos of `vertical/<project>.md`. `#t=<seconds>` in the preview URL seeks the timeline.
