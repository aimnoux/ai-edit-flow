---
name: edit
description: Start or continue a video project, choose horizontal or vertical workflow, and report the next step or available outputs. Route production work to its skill.
---

# Editing a video

You run the whole pipeline; the person records, listens, looks and says "ok". Every step ends with
something to look at or hear, and nothing goes to the person before the frame review (`review`).

## Before anything

1. Read `style/visual.md`. If it is still the template (hints in angle brackets, empty sections), there
   is no style yet: say so and run the `style` skill first. Never invent a look to fill the gap.
2. Read `style/config.json` (language, voice, channel).
3. Plan the video in 5-8 lines: format, source of the voice (recording or clone), chapters or the
   batch, what the person has to give you (a recording, a text, a cleaned voice). Continue when this scope is already authorized; otherwise get the "ok".

## Horizontal video, live voice (the main path)

| Step | Skill | What the person gets |
|---|---|---|
| 1. Script in `videos/<slug>/script.md` (format: `videos/README.md`) | `edit` | the script to read |
| 2. Recording: one long take, every retake starts with a spoken slate | `cut` | nothing yet |
| 3. Rough cut: `stt.py` → `cut.py`, retakes and pauses out | `cut` | `voice.wav` for audio, `rough.mp4` for video |
| 4. Voice cleanup (external tool), optional clone for retakes | `voice` | the cleaned voice back to you |
| 5. `pad_chapters.py` → `build.py --cut` → scenes in code | `graphics` | verified contact sheets |
| 6. Frame review by a fresh agent, fixes | `review` | nothing: it happens before the show |
| 7. Draft render of one chapter or the whole video, no music | `render` | an MP4 to watch |
| 8. Music options (3-4), sound effects, mix | `sound` | the options to pick from |
| 9. Final render, subtitles, loudness check | `render` | `engine/renders/<slug>/<slug>.mp4` + `.srt` |

Horizontal video with a cloned voice skips 2-4: `voice.py` on the script, then `build.py --tts`.
Before any recording you can build the graphics on estimated timing: `build.py --estimate`.

## Vertical video

Text in `vertical/<batch>.md` (format: `vertical/example.md`) → voice (clone, or a recording cut with
`cut.py` on the batch text) → `vertical.py build` for one platform → review → render → the other
platforms. Details: `vertical`.

A sketch with two voices or a 3D scene: same steps, voices in `voice`, drawing and render in `3d`. Needs a video card.

## Step boundaries

One step, one "ok": a render before the cut is approved is wasted work. A contact sheet or short
draft makes the next decision concrete. Shared timing, style, review and delivery rules are in the
automatically loaded `AGENTS.md`.

## What is ready

`videos/<slug>/cut/` (rough cut), `engine/build/<slug>/timing.json` (timeline), `engine/<slug>-ch*.html`
(compositions), `engine/renders/<slug>/` (renders). For vertical: `engine/<batch>-s<N>-<platform>.html`
and `engine/renders/<batch>/`. Answer "what is ready" from these, not from memory.
