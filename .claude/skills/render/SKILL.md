---
name: render
description: Rendering and the final files. Use when the person asks to render, re-render a chapter or a stretch, resume a render that broke off, make a draft to watch, a before/after comparison, or asks where the finished video is. Covers HyperFrames rendering through engine/hf.mjs (segmented capture, --resume, timeouts), engine/render.sh for a whole horizontal video, engine/vertical.py render, logs, the strobe check, verifying the final file and where deliverables land.
---

# Render

HyperFrames renders a composition frame by frame in a dedicated `chrome-headless-shell`; the kit runs it at the pinned
version through `node engine/hf.mjs` (never `npx hyperframes@...` by hand: the version lives in
`package.json`). Long renders run in the foreground with the log in a file; never start a render in the
background with `&` inside a command: it is cancelled when the parent exits.

Run `bash setup.sh` and activate its Python environment first. `node engine/hf.mjs browser ensure`
downloads the dedicated browser without launching it. `CHROME_PATH` may select another compatible
`chrome-headless-shell` executable; never point it at personal Chrome. The wrapper and frame tools
use isolated temporary profiles, clean up their browser after each command and disable the HyperFrames warm daemon. Do not use direct `npx hyperframes` commands or a running desktop browser.
Linux ARM64 requires a separately supplied compatible shell; setup does not install system Chromium.

## Horizontal video

```
bash engine/render.sh <slug>                 # all chapters -> mix -> engine/renders/<slug>/<slug>.mp4 + .srt
bash engine/render.sh <slug> ch2 ch3         # only these chapters, then reassemble
MUSIC=track.mp3 bash engine/render.sh <slug>
```

- `build.py` must have run first (timing, voice tracks, compositions). The script renders each chapter
  with `HF_SEGMENTED_CAPTURE=true` (long compositions render in segments and can resume), mixes with
  `mix.py`, concatenates, muxes, copies the subtitles.
- A chapter that broke off: run the same HyperFrames command from the log with `--resume`; it continues
  from the last finished segment. The log is `engine/build/<slug>/render-<chapter>.log`.
- A heavy scene that doesn't load: raise `--browser-timeout`, `--protocol-timeout`,
  `--player-ready-timeout` on `node engine/hf.mjs render`.
- One chapter by hand: `node engine/hf.mjs render -c engine/<slug>-ch2.html -o engine/renders/<slug>/ch2.mp4 --fps 25`.

## Vertical video

```
python engine/vertical.py render <batch>-s1-yt [--music track.mp3]     # render -> strobe check -> mix
python engine/vertical.py render <batch>-s1-yt --mix-only              # the picture is fine, only the sound changed
```

The strobe check fails the render when a frame comes from another moment (a resumed segment out of
sync): re-render that video. Draft to watch: render as usual, the mix is quick.

## A stretch, a draft, a comparison

- A stretch of a composition as its own file: `python engine/compare.py chapter engine/<id>.html engine/<id>-part.html 12 30`,
  then render `-c engine/<id>-part.html`. Cues and the timeline are shifted to the stretch.
- Before/after as **one** video, never two files: `compare.py stack before.mp4 after.mp4 out.mp4`
  (16:9 stacked, 9:16 side by side, labels in the corner), `compare.py grid` for four variants,
  `compare.py seq` for the same picture with different sound.

## Verify the final file

```
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of default=nw=1 out.mp4
ffmpeg -i out.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12       # -14 LUFS, true peak <= -1.5
python engine/review.py <id> --video out.mp4                           # dead stretches and lulls in the render
```

Duration matches `timing.json` (`total`) or the composition's `data-duration`; a mismatch means a
chapter is missing from the concat or the mix is short.

## Deliverables

Finished files stay in `engine/renders/<project>/`: `<slug>.mp4` and `<slug>.srt` for a horizontal video,
`<batch>-s<N>-<platform>.mp4` per vertical. Say the path. Don't attach videos to the chat, don't copy them
elsewhere unless the person named a folder; then copy, don't move.
