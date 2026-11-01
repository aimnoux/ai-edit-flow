---
name: vertical
description: Vertical video 9:16 for YouTube Shorts, Instagram Reels and TikTok. Use when the person asks for a short, a reel, a vertical, a batch of them, a loop or a meme format, or to fix one. Covers the batch text format, voice (clone or a recording), engine/vertical.py (build, silent, shots, render), the 9:16 safe zones, embedded captions, the ending per platform, loops without voice, the strobe check and the mix.
---

# Vertical video

One build serves all platforms; the platform (`yt`, `ig`, `tt`) only changes the ending. Scenes are
`engine/scenes/<batch>/s<N>.js` on top of `lib/kit.js` and `lib/vertical.js`. The look is the
person's `style/`: if it is empty, run `style` first.

## Text

`vertical/<batch>.md`, format in `vertical/example.md`: `## N. Title`, blocks `### N.1 ...` for the story,
`N.0` the slate (for a recording), `N.8` the ending for Shorts, `N.9` for Reels and TikTok (falls back to
`N.8`). A story is 25-30 s, 55-65 words; the first line is the most surprising fact, the twist is the last
line, nothing after it. Triggers in [brackets] on the words where something happens in the frame.

Endings are one short line. Shorts may ask for a like or a subscription. Reels and TikTok treat
requests to like, share, save or tag as engagement bait and show such videos less: there, follow or a
plain closing line only.

## Voice

Clone: `python3 engine/voice.py vertical/<batch>.md [1,2]`. Recording: the person reads the whole
batch in one take with slates, then `cut.py` on the batch text (see `cut`) and `vertical.py build ... --cut <dir>`.
Before any voice: `--estimate` builds with timing estimated from the text to try the scene.

## Build, look, render

```
python3 engine/vertical.py build vertical/<batch>.md 1 yt            # -> engine/<batch>-s1-yt.html, build/<batch>/<id>-voice.wav
python3 engine/check.py <batch>-s1-yt --hf
python3 engine/vertical.py shots <batch>-s1-yt 0.5 3 6 9 12 15        # contact sheet
python3 engine/review.py <batch>-s1-yt                               # then the review skill
python3 engine/vertical.py render <batch>-s1-yt [--music track.mp3]   # HyperFrames render -> strobe check -> mix
```

- **One platform first.** Build and show Shorts (`yt`); after the "ok", the other platforms without a
  second approval. A remake of a batch: first one video before/after (`compare.py stack`), then the rest.
- Render runs segmented and resumable; a frame from another moment (a stroboscope) fails the render on
  purpose, re-render that video. Logs: `engine/build/<batch>/render-<id>.log`.
- The result: `engine/renders/<batch>/<id>.mp4` (voice -16 LUFS, effects at cues, music with ducking,
  final -14 LUFS, true peak ≤ -1.5 dBTP).

## The frame 1080×1920

- Safe zone: graphics between 230 and 1180 in height and up to 930 in width; captions from 1250;
  below and to the right sits the platform UI. `VX = 500` is the center for graphics.
- **Something new every 0.7-1.5 s**, by content and cuts on the word, not by shaking. Flashes, zoom
  kicks, scene drift and hits on every trigger are off in the kit on purpose.
- Captions are embedded always (`liveCaptions()` in the template): phrases of 3-4 words, the spoken
  word lights up. The stage dissolves above the caption zone so things don't sit under them. A line
  never ends on a weak word (`style/config.json` → `captions.weak` for the language).
- The thing is the frame: a phone, a document, a chat built as the real product, at least 50 % of the
  frame; small details are reached with the camera (`camTo`), not with bigger text.
- Text over the background: a term, a number, a name; the voice is already in the captions.
- The climax on the word (`stamp`, a value changing) holds at least 1 s; the stamp is the one hit with
  a sound in the video.

## Building blocks (`lib/vertical.js`, plus everything in `kit.js`)

```
slam(sc, "WORD", t, { y, size, out })      vtext(sc, "words for [hello]", y, size, { id: "1.1" | t })
chip(sc, text, x, y, t)  vcard(sc, label, value, x, y, w, t)  plusUp(sc, "+1", x, y, t)
chatWindow(sc, x, y, w, h, title).show(t).say("user" | "bot", text, t0, t1)
docSheet(sc, x, y, w, [lines], t)  stamp(sc, "TEXT", x, y, t)
memeFrame("one phrase on top")             a format without captions: the phrase carries it
platformEnding()                           automatic from block N.8 / N.9; own look via window.END_CTA
```

## Formats without voice

`python3 engine/vertical.py silent <batch> 7 yt 8.0` builds an 8-second loop: scene `s7.js`, frame
`dur` equals frame 0, sound = effects at cues, mixed as a loop (`mix_piece.py --loop`). `--no-loop` for a
one-shot. A loop with one spoken phrase: `build ... --dur=9`. Music for a loop: a track exactly the
loop's length (`.wav`) mixes as is.
