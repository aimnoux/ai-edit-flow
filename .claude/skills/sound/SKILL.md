---
name: sound
description: Choose music, build the sound bank, place effects and fix mixing, ducking or loudness. Voice cleanup and cloning use voice.
---

# Sound

Three layers in the mix: the **voice** (cleaned, as is), **effects** at the cues scenes write, and
**music** under the voice with ducking. `engine/mix.py` mixes a horizontal video from
`build/<slug>/timing.json` and the chapter compositions; `engine/mix_piece.py` mixes one composition
(a vertical, a chapter, a test). Both read the bank in `style/sound/`.

## Cues in scenes

`sfx("name", t, vol, len)` in a scene puts a cue; `finish.js` filters them: cues named in
`style/sound/sounds.json` → `quiet` never play, between the rest at least `gap` seconds (1.2 by default);
when two collide the one in `main` (a hit, a stamp) wins. The mix skips a cue that has no file in the
bank and reports it: `no file in style/sound for: tap, stamp`.

The diet: sound belongs to the **main action and comes from the thing** in the frame (paper on a desk,
a phone put down, keys, a stamp), not to decoration. A tick on every line, a whoosh on every scene, a
synthesized "ding" on every appearance are slop (`review`, S-02). Seconds without any effect are normal.
A chat answer arrives silently unless the style says otherwise.

## The bank (`style/sound/`)

- One file per cue name (`tap.mp3`), extra takes in `takes/tap-1.mp3`, `takes/tap-2.mp3`: takes rotate so
  one file never plays twice in a row; each use gets a small variation of level and pitch.
- `sounds.json`: `gain` per sound (0..1, climax sounds 3-6 dB above the music under the voice, the rest
  level with it or quieter), `alias` (a cue name in scenes → a file), `attack` (a high-passed layer on
  low hits, phones don't play the low end), `main`, `quiet`, `gap`.
- Level files to about -20 dB RMS so gains mean the same across the bank. Soft attacks; a click is a
  mouse, not a trackpad; nothing sharp.
- Generating: ElevenLabs sound effects (`POST /v1/sound-generation`, a one-line prompt per sound,
  3 takes each), or any library the person has. Ask for the person's "ok" on a bank before mixing a video
  with it; show the takes as a short `compare.py seq` on the same picture.
- Extend the bank when a scene needs a sound that is not there, don't substitute a wrong one.

## Music

- 3-4 options for the person to choose from; a generated track per video (ElevenLabs Music,
  `POST /v1/music`, `force_instrumental: true`, length a bit over the video) or a licensed track.
  Prompt template, adjust the genre to the style layer:

  > Instrumental background music for a <pace> <genre> video. <mood words>, driving pulse at <BPM> BPM,
  > no vocals, sits under a voiceover. Starts sparse, the beat enters after a few bars, one short breakdown
  > in the middle where the drums drop out for two bars, then the groove returns, ends cleanly on a bar line.

- Generated tracks have holes and early fades: check with
  `ffmpeg -i track.mp3 -af silencedetect=n=-40dB:d=0.4 -f null -` before offering a track.
- A breakdown under the voice distracts: move it in the prompt, not in the mix.
- A loop (verticals without voice): a track exactly the loop's length as `.wav` mixes as is; otherwise
  a second past the end crossfades onto the start.

## Levels and checks

| What | Level |
|---|---|
| Voice | -16 LUFS integrated, 70 Hz high-pass |
| Music under the voice | about -22 to -25 LUFS without voice, 9 dB lower while the voice speaks (ducking) |
| Final | -14 LUFS, true peak ≤ -1.5 dBTP after the codec (the limiter targets -2) |
| A piece without voice and music | -20 LUFS: effects alone at -14 would hit |

```
python3 engine/mix.py <slug> --music track.mp3 [--music-db -15] [--duck 9]      # -> engine/build/<slug>/mix.wav
python3 engine/mix_piece.py <id> <video.mp4> <voice.wav> <music|-> <out.mp4> [--loop]
```

Both print the measured result (LUFS, true peak, LRA). Check the final file once more with
`ffmpeg -i out.mp4 -af ebur128=peak=true -f null -` when the platform complains about loudness.
Before/after of a mix on the same picture: `python3 engine/compare.py seq out.mp4 "BEFORE=a.mp4" "AFTER=b.mp4"`.
