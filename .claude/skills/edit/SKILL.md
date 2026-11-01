---
name: edit
description: The entry point for making a video with this kit. Use when the person wants a new video, asks where to start, what the next step is, or what is ready. Sets the format (horizontal 16:9 or vertical 9:16), the order of steps with the person's "ok" on each, and where the finished files land. Hands each step to its own skill (cut, voice, graphics, vertical, review, sound, render) and sends to style first when the style is still empty.
---

# Editing a video

You run the whole pipeline; the person records, listens, looks and says "ok". Every step ends with
something to look at or hear, and nothing goes to the person before the frame review (`review`).

## Before anything

1. Read `style/visual.md`. If it is still the template (hints in angle brackets, empty sections), there
   is no style yet: say so and run the `style` skill first. Never invent a look to fill the gap.
2. Read `style/config.json` (language, voice, channel) and `CLAUDE.md` of this repository.
3. Plan the video in 5-8 lines: format, source of the voice (recording or clone), chapters or the
   batch, what the person has to give you (a recording, a text, a cleaned voice). Get the "ok".

## Horizontal video, live voice (the main path)

| Step | Skill | What the person gets |
|---|---|---|
| 1. Script in `videos/<slug>/script.md` (format: `videos/README.md`) | `edit` | the script to read |
| 2. Recording: one long take, every retake starts with a spoken slate | `cut` | nothing yet |
| 3. Rough cut: `stt.py` → `cut.py` → `rough.mp4`, retakes and pauses out | `cut` | `rough.mp4` to listen to |
| 4. Voice cleanup (external tool), optional clone for retakes | `voice` | the cleaned voice back to you |
| 5. `pad_chapters.py` → `build.py --cut` → scenes in code | `graphics` | contact sheets (`shots.py`) |
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

## Rules of the process

- **One step, one "ok".** Don't run ahead: a render before the cut is approved is wasted time.
- **Show, don't tell.** A contact sheet beats a description; a 20-second draft beats a plan.
- **Timing comes from the voice.** Never place a scene by guessed seconds; use `W()`, `TR()`, `B()`.
- **Review before the show.** Every build that changes timing or layout goes through `review` first.
- **No new style on the fly.** A wish about the look ("make it warmer") goes into `style/visual.md`
  as a rule through the `style` skill, then into scenes.
- **Finished files** stay in `engine/renders/<project>/`; say the path, don't send the file into the chat.
- **Logs** of renders and long commands go to files; read the tail. Frames go to one reduced sheet.

## What is ready

`videos/<slug>/cut/` (rough cut), `engine/build/<slug>/timing.json` (timeline), `engine/<slug>-ch*.html`
(compositions), `engine/renders/<slug>/` (renders). For vertical: `engine/<batch>-s<N>-<platform>.html`
and `engine/renders/<batch>/`. Answer "what is ready" from these, not from memory.
