# engine/

Scripts and a small library for building videos. The project folder for HyperFrames is this one:
compositions (`<project>-ch1.html`, `<project>-s1-yt.html`) are generated here and ignored by git,
scenes live in `scenes/<project>/`, outputs in `build/` and `renders/`.

After `bash setup.sh`, activate `.venv` (`source .venv/bin/activate`, or
`source .venv/Scripts/activate` in Windows Git Bash). If setup used an already active virtual
environment, keep that one active. Run scripts from the repository root with
`python engine/<script>.py`; HyperFrames through
`node engine/hf.mjs <command>` (the version is pinned in `package.json`). Preview in Claude Code: `.claude/launch.json`,
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
| `review.py`, `review_cache.py` | Cached sheets, integrity manifests and explicitly recorded reviewer conclusions |
| `verify.py` | One-command runtime/layout/review and optional final-file checks, with concise reports |
| `mix.py`, `mix_piece.py` | Mix: voice -16 LUFS, effects at cues from `style/sound/`, music with ducking, final -14 LUFS |
| `compare.py` | Before/after as one video: `stack`, `grid`, `seq`, `chapter`, `mix` |
| `render.py` | One composition through a stable isolated index project and the browser wrapper |
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
python engine/verify.py --project <slug>
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
python engine/verify.py <batch>-s1-yt
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

## One-command verification and review reuse

```
python engine/verify.py example-ch1
python engine/verify.py --project example
python engine/verify.py example-s1-yt --video engine/renders/example/example-s1-yt.mp4
python engine/verify.py example-ch1 --chapter 2 6 --json
```

Use this after changing a composition. The command runs the strict runtime/HyperFrames checks and
prepares beat, seam and phone sheets once. Successful unchanged inputs reuse the evidence. It does
not render, regenerate speech or call an AI reviewer. `--video` requires one composition and adds
ffprobe checks for video/audio streams, dimensions, frame rate and full composition duration; video
motion metrics are limited to `--chapter` when supplied. `--strict` makes warnings fail too.

Stdout is a short summary (or one JSON object with `--json`). Follow the emitted report, log and
review paths under `engine/build/`; full checker output and tracebacks stay in per-composition log
files. `passed` means automated checks passed. `ready_to_show` also requires a current explicit
`Verdict: PASS` from the independent reviewer. A recorded `Verdict: FAIL` makes verification fail.

The review skill sends only the evidence, script, style layer and its reference checklist to a fresh
reviewer. Save that answer to a file, then bind it to the exact verified target/scope:

```
python engine/review.py example-ch1 --record-review reviewer.md
```

Include the same `--chapter` and `--video` options used for verification. The file must contain
the `Fingerprint: <hash>` line copied from `REVIEW-INPUT.md` and exactly one `Verdict: PASS` or
`Verdict: FAIL` line. A conclusion from older inputs is rejected. Reuse never invents or changes the verdict.
`--force` regenerates evidence and invalidates any previous conclusion, even with identical inputs.

Freshness uses file contents, not timestamps: composition/timing, referenced scene/imports/assets,
shared code and templates, source script/settings, global style, review checklist, tool configuration,
browser binary and optional video, plus exact range. A shared style change invalidates every affected
composition; an unrelated chapter's scene change leaves other chapters reusable. Missing or changed
artifacts, corrupted manifests and changed verdict text cannot produce a valid cache hit. Unknown
external/dynamic dependencies block reusable approval and make verification fail with a reason;
make those dependencies local and explicit before recording a verdict. Use `--chapter START END`
to review a changed stretch; a full-composition review still needs its own current conclusion.

Review artifacts, manifests and logs stay in ignored `engine/build/`. Repeated unchanged verification
avoids capture and AI review work; actual model token savings depend on the task and session.

## Voice cache integrity

`voice.py` keys audio by the exact synthesis request: full voice ID, model, language (when sent),
settings from `style/config.json -> voice.settings`, pronounced text, neighbouring context and
output format. Indexed `<block>-<paragraph>` files remain compatible with the builders; reusable
requests also live under `cache/<sha256>`. Script insertions can reuse unchanged requests even when
paragraph indices shift. A partial batch selection keeps the full script context.

Audio hashes and complete finite character alignment are checked on every hit and before a builder
uses voice. A fully cached run needs no API key. Legacy text-only metadata cannot prove its request
and is regenerated once; budget for that before authorizing a paid run. Changed text can invalidate
its immediate neighbours too. Writes are atomic; `paragraphs.json` advances only after a successful
run. An interrupted run keeps completed content-addressed requests for the next attempt.

## Reproducible setup and portable adapters

Supported Python: 3.11–3.13 (SciPy's pinned version needs 3.11+). `requirements.txt` pins all Python
runtime dependencies; `npm ci --ignore-scripts` installs the integrity-locked Node graph. The wrapper
uses `npx --no-install` so it never silently downloads a different dependency graph at render time.
Every HyperFrames command has a 1800-second deadline; override `AEF_HF_TIMEOUT_SECONDS` with a
positive number up to 86400 for a deliberate long render. Timeout exits 124 and cleans the owned group.

`python engine/sync_skills.py --check` verifies the generated Claude adapter against `.agents/skills/`.
`python engine/contracts.py --json` emits schema-1 deterministic local contract probes.
`python engine/demo.py` builds the existing vertical example with synthetic word-tone audio and
renders one 10 fps draft with one worker. `--prepare-only` skips browser rendering. It never calls a
speech/model API; output stays in ignored `engine/build/` and `engine/renders/demo/`.

Render entry points stage the selected composition as `index.html` under ignored
`engine/build/render-projects/<id>/proj/`, with local libraries/assets. This also handles upstream
render phases that require a project index even with an explicit composition flag, preserves resume
paths and leaves unrelated preview indexes alone. Use `python engine/render.py <id> <out.mp4>` for
a single composition; horizontal and vertical render commands use it automatically.
