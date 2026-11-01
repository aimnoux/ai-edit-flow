# engine/

Scripts and a small library for building videos. The project folder for HyperFrames is this one:
compositions (`<project>-ch1.html`, `<project>-s1-yt.html`) are generated here and ignored by git,
scenes live in `scenes/<project>/`, outputs in `build/` and `renders/`.

After `bash setup.sh`, activate `.venv` (`source .venv/bin/activate`, or
`source .venv/Scripts/activate` in Windows Git Bash). If setup used an already active virtual
environment, keep that one active. Run scripts from the repository root with
`python engine/<script>.py`; HyperFrames through
`node engine/hf.mjs <command>` (the version is pinned in `package.json`). Preview: `.claude/launch.json`,
`engine` (port 8790), or `python engine/serve.py`.

| File | What it does |
|---|---|
| `common.py` | Paths, `style/config.json`, dedicated headless-shell lookup and lifecycle, GSAP fetch, style sync into `lib/` |
| `tts_elevenlabs.py` | ElevenLabs API, script parsing (`parse_blocks`, `strip_triggers`), `--list-voices`, `--clone` |
| `stt.py` | Speech-to-text with word timestamps (ElevenLabs Scribe) -> JSON for `cut.py` |
| `cut.py` | Rough cut of a recording by the script: last take, no fillers, pauses shortened -> `words.json` and `voice.wav` (audio-only) / `rough.mp4` (video) |
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
| `hf.mjs` | Pinned HyperFrames CLI, isolated headless-shell and daemon cleanup |
| `lib/kit.js` | Timing by words (`W`, `WE`, `B`, `P`, `TR`), scenes, `rich`/`reveal`/`follow`, `glow`, lists, chapter title, `typeText`, camera |
| `lib/vertical.js` | 9:16: `slam`, `vtext`, `chip`, `vcard`, `chatWindow`, `docSheet`, `stamp`, `memeFrame`, captions, platform ending |
| `lib/finish.js` | Timeline registration, cue filter, scene bounds |
| `lib/style.css`, `lib/vertical.css` | Structure only; looks come from `lib/tokens.css` (copied from `style/`) |
| `template.html`, `template-v.html` | Layer skeleton: world (style slot) -> stage -> hud -> overlay (style slot) |

## Rendering browser

Only a dedicated `chrome-headless-shell` executable is accepted; personal Chrome and desktop
Chrome for Testing apps are never selected. `CHROME_PATH` in the environment or repository `.env`
selects a dedicated shell explicitly. Without it, lookup checks HyperFrames' cache at
`~/.cache/hyperframes/chrome/chrome-headless-shell/`, then Puppeteer's `chrome-headless-shell/`
cache (`PUPPETEER_CACHE_DIR` or `~/.cache/puppeteer`). Symlinks are checked by their resolved target.

```
node engine/hf.mjs browser ensure    # download only; no browser launch
python engine/common.py chrome     # print the selected dedicated executable
```

Use the wrapper for every HyperFrames command. It prevents system-browser fallback, uses a separate
temporary profile and cleans up its browser after the command; the warm daemon is disabled. Frame tools use the
same browser policy. Never substitute a direct `npx hyperframes` invocation.

macOS is the primary development platform; Linux and Windows support is not fully verified. Windows
scripts require Git Bash and native Python/Node.js/ffmpeg on `PATH`. Linux ARM64 requires a separately
supplied compatible `chrome-headless-shell` through `CHROME_PATH`: setup never installs or chooses
system Chromium. Downloads and older operating systems may need a compatible shell build.

## Script paragraphs

Spoken blocks use `### N.M` headings. A blank line starts a new paragraph; consecutive source lines
are joined into one paragraph. Notes (`>`), tables, headings and separator lines are excluded from
speech. Keep paragraph breaks deliberate: they control pauses, timing and the voice cache.

## Horizontal video, live voice

```
python engine/stt.py recording.m4a videos/<slug>/cut/stt.json
python engine/cut.py recording.m4a videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut [--drop videos/<slug>/drops.json]
python engine/pad_chapters.py <slug> [--voice cleaned.wav]
python engine/build.py <slug> --cut videos/<slug>/cut/pad
python engine/check.py --project <slug> --hf
python engine/shots.py <slug>-ch1 0.5 3 8
python engine/review.py <slug>-ch1
MUSIC=track.mp3 bash engine/render.sh <slug>
```

`cut.py` accepts audio-only and video recordings: its playable output is `voice.wav` for audio
and `rough.mp4` for video. Both share `words.json` and `edl.json`; `pad_chapters.py` accepts either
output and writes the padded `voice.wav`, `rough.mp4` and `words.json` used by `build.py`.

## Horizontal video, cloned voice

```
python engine/voice.py videos/<slug>/script.md
python engine/build.py <slug> --tts
bash engine/render.sh <slug>
```

## Vertical video

```
python engine/voice.py vertical/<batch>.md 1
python engine/vertical.py build vertical/<batch>.md 1 yt
python engine/vertical.py shots <batch>-s1-yt 0.5 3 8
python engine/review.py <batch>-s1-yt
python engine/vertical.py render <batch>-s1-yt [--music track.mp3]
```

Composition names: `<project>-ch<N>` for chapters of `videos/<project>/`, `<project>-s<N>-<platform>` for
vertical videos of `vertical/<project>.md`. `#t=<seconds>` in the preview URL seeks the timeline.

For live vertical voice, run `stt.py` and `cut.py` against the batch text, then use
`python engine/vertical.py build vertical/<batch>.md 1 yt --cut <cut-dir>`.
The cut directory may contain `voice.wav` (audio-only) or `rough.mp4` (video), plus `words.json`;
slates `N.0` are excluded and only this video's story and selected platform ending are assembled.

## Offline regression checks

With the Python environment active, run from the repository root:

```
python -m unittest discover -s tests -v
```

The regression suite uses synthetic media and mocked browser/API boundaries; it does not require an
ElevenLabs key or launch personal Chrome. It is separate from setup and rendering.
