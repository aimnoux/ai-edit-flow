---
name: render
description: Render drafts or final files, resume interrupted capture, render a stretch or create a before/after comparison. Audio changes use sound.
---

# Render

HyperFrames renders a composition frame by frame. Long renders run in the foreground with the log
in a file; never start a render in the
background with `&` inside a command: it is cancelled when the parent exits.

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
python engine/verify.py <id> --video out.mp4                          # cached checks, sheets and media metadata
ffmpeg -i out.mp4 -af ebur128=peak=true -f null - 2>&1 | tail -12       # -14 LUFS, true peak <= -1.5
```

Use the full composition id for a chapter or vertical render; `--chapter A B` scopes a stretch.
For an assembled horizontal file, verify the project with `--project <slug>` and separately match
its duration to `timing.json` (`total`); a mismatch can mean a missing chapter or short mix.
Complete the `review` workflow for any pending visual verdict before showing the result.

## Deliverables

Finished files stay in `engine/renders/<project>/`: `<slug>.mp4` and `<slug>.srt` for a horizontal video,
`<batch>-s<N>-<platform>.mp4` per vertical. If the person named another folder, copy there without moving the originals.
