---
name: cut
description: Cut retakes, pauses and fillers from audio or video against a script; handle recording guidance and manual take selection. Voice cleanup uses voice.
---

# Cut

Input: one audio or video recording and the script it was read from. Output: `voice.wav` for
audio-only input or `rough.mp4` for video (the kept speech, pauses normalized), `words.json`
(every kept word with its time and script position) and `edl.json` (what was dropped and why). The person listens to the rough cut and says "ok" or marks what to change.

## How to record (tell the person once, keep it in `style/visual.md` if they change it)

- One long take, all retakes in a row. Before a retake, say a slate out loud: "two six, take two"
  (block number, take). Mistakes don't need a stop: pause, repeat the phrase or the block.
- A quiet room, 10 seconds of silence at the start (room tone), windows closed, devices off.
- Phone or recorder 15-20 cm from the mouth, slightly to the side. Export lossless or the highest
  quality the app offers; no built-in enhancement at this stage.
- A paragraph in the script is a pause of 0.5-1 s; sentences inside a paragraph are read in a row.
  Separate paragraphs with a blank line. Consecutive source lines form one paragraph, without an
  extra pause; notes (`>`), tables and headings are not spoken.

## Steps

```
python engine/stt.py <recording> videos/<slug>/cut/stt.json               # words with timestamps (ElevenLabs Scribe)
python engine/cut.py <recording> videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut
python engine/pad_chapters.py <slug>                                      # silence between chapters for titles -> cut/pad/
```

- `stt.py` needs `ELEVENLABS_API_KEY` in `.env`. Any other speech-to-text works if it writes the same
  JSON (`words` with text/start/end/type).
- `cut.py` aligns speech to the script: when the speech jumps back in the text, the earlier attempt is a
  retake and goes; the last take stays. Broken words, fillers (`um`, `uh`; add your language's in
  `style/config.json` → `fillers`) and pauses longer than 0.45 s are cut. A script paragraph becomes
  0.6 s, inside a paragraph 0.25 s.
- Listen through `edl.json` first: every dropped word has a reason (`retake`, `broken`, `manual`).
  A kept slate or a lost sentence shows up here before anyone listens to the file.
- For a vertical batch run `stt.py` and `cut.py` on `vertical/<batch>.md`; slates are blocks `N.0`.
  Skip chapter padding: `python engine/vertical.py build vertical/<batch>.md N yt --cut <cut-dir>`
  selects the story and ending for that video from the batch cut.

## Manual takes (`drops.json`)

When the automatic alignment picks the wrong take (the person changed words, read a block three
times with variations), mark takes by hand: `videos/<slug>/drops.json` is a list of `[start, end]`
in seconds of the source to throw away. Then:

```
python engine/cut.py <recording> videos/<slug>/cut/stt.json videos/<slug>/script.md videos/<slug>/cut --drop videos/<slug>/drops.json
```

With `--drop` the alignment is global (the speech is assumed monotonic after the drops), so the
script positions of words are reliable even when the wording drifted.

## The cleaned voice comes back

The person cleans `voice.wav` (audio-only) or the audio of `rough.mp4` (video) in an external
tool (`voice` skill) and returns a file of the same length. Check it: duration within 0.05 s of the rough cut (`ffprobe`), and the offset by
cross-correlation if in doubt. Then `pad_chapters.py <slug> --voice <cleaned.wav>`: the timing depends
only on the cuts, so the cleaned voice drops in without a re-render.

## Where things land

```
videos/<slug>/cut/stt.json, voice.wav (audio) / rough.mp4 (video), words.json, edl.json, filter.txt
videos/<slug>/cut/pad/words.json, voice.wav, rough.mp4        -> engine/build.py <slug> --cut videos/<slug>/cut/pad
```
