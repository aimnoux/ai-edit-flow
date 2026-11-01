---
name: cut
description: Rough cut of a recording against the script. Use when the person sends a recording (audio or video) of them reading a script, asks to cut takes, pauses or fillers, mark retakes by hand, or asks how to record. Covers speech-to-text with word timestamps (engine/stt.py), the cut itself (engine/cut.py), manual take marking (drops.json), chapter padding (engine/pad_chapters.py) and the rough voice file the person listens to.
---

# Cut

Input: one recording and the script it was read from. Output: `rough.mp4` (the kept speech, pauses
normalized), `words.json` (every kept word with its time and script position) and `edl.json` (what was
dropped and why). The person listens to the rough cut and says "ok" or marks what to change.

## How to record (tell the person once, keep it in `style/visual.md` if they change it)

- One long take, all retakes in a row. Before a retake, say a slate out loud: "two six, take two"
  (block number, take). Mistakes don't need a stop: pause, repeat the phrase or the block.
- A quiet room, 10 seconds of silence at the start (room tone), windows closed, devices off.
- Phone or recorder 15-20 cm from the mouth, slightly to the side. Export lossless or the highest
  quality the app offers; no built-in enhancement at this stage.
- A paragraph in the script is a pause of 0.5-1 s; sentences inside a paragraph are read in a row.

## Steps

```
python3 engine/stt.py <recording> videos/<slug>/cut/stt.json               # words with timestamps (ElevenLabs Scribe)
python3 engine/cut.py <recording> videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut
python3 engine/pad_chapters.py <slug>                                      # silence between chapters for titles -> cut/pad/
```

- `stt.py` needs `ELEVENLABS_API_KEY` in `.env`. Any other speech-to-text works if it writes the same
  JSON (`words` with text/start/end/type).
- `cut.py` aligns speech to the script: when the speech jumps back in the text, the earlier attempt is a
  retake and goes; the last take stays. Broken words, fillers (`um`, `uh`; add your language's in
  `style/config.json` → `fillers`) and pauses longer than 0.45 s are cut. A script paragraph becomes
  0.6 s, inside a paragraph 0.25 s.
- Listen through `edl.json` first: every dropped word has a reason (`retake`, `broken`, `manual`).
  A kept slate or a lost sentence shows up here before anyone listens to the file.
- For a vertical batch the same commands run on `vertical/<batch>.md`; slates are blocks `N.0`.

## Manual takes (`drops.json`)

When the automatic alignment picks the wrong take (the person changed words, read a block three
times with variations), mark takes by hand: `videos/<slug>/drops.json` is a list of `[start, end]`
in seconds of the source to throw away. Then:

```
python3 engine/cut.py <recording> videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut --drop videos/<slug>/drops.json
```

With `--drop` the alignment is global (the speech is assumed monotonic after the drops), so the
script positions of words are reliable even when the wording drifted.

## The cleaned voice comes back

The person cleans `rough.mp4`'s audio in an external tool (`voice` skill) and returns a file of the
same length. Check it: duration within 0.05 s of the rough cut (`ffprobe`), and the offset by
cross-correlation if in doubt. Then `pad_chapters.py <slug> --voice <cleaned.wav>`: the timing depends
only on the cuts, so the cleaned voice drops in without a re-render.

## Where things land

```
videos/<slug>/cut/stt.json, rough.mp4, words.json, edl.json, filter.txt
videos/<slug>/cut/pad/words.json, voice.wav, rough.mp4        -> engine/build.py <slug> --cut videos/<slug>/cut/pad
```
