---
name: voice
description: Clean recorded speech, clone a voice, voice scripts, fix pronunciation or revoice lines. Troubleshoot ElevenLabs failures; recording cuts use cut.
---

# Voice

Two sources of voice, never mixed inside one video: a **live recording** (cut with `cut`, cleaned by
the person) or a **clone** (ElevenLabs, voiced paragraph by paragraph with word timing). A course,
a trailer, a batch of verticals: each is one source throughout. A dialogue of two voices is always
voiced (below), never cut from a recording.

## Cleaning a live recording

The person cleans the rough cut's audio in a dedicated tool and sends the file back. Recommend one
tool and stick to it; Cleanvoice does the whole job (noise, mouth sounds, levels) in one pass;
Adobe Podcast Enhance and iZotope RX are alternatives. Settings that matter:

- Breaths stay natural (off or "natural"): a voice without breaths sounds synthetic.
- No speed change, no pitch change: the timing of the cut must survive.
- The output length equals the input length within 0.05 s. Check with `ffprobe`; a drift means
  the tool trimmed silence, ask for the untrimmed export.
- Don't propose a chain of ffmpeg filters, a voice isolator or "underwater" music under the voice
  instead of cleaning: the mix (`sound`) takes the cleaned voice as is.

## Cloning (optional)

```
python3 engine/tts_elevenlabs.py --clone <sample.m4a> --name "<name>"   # instant clone -> voice_id
python3 engine/tts_elevenlabs.py --list-voices
python3 engine/tts_elevenlabs.py --say "A test line." --voice <id> --out test.mp3
```

A good sample: 1-5 minutes of clean speech in the person's normal delivery, no music, no room echo.
The `voice_id` goes into `style/config.json` → `voice.voice_id`, together with `model_id` (`eleven_v3`
by default; `eleven_multilingual_v2` when the language needs it) and the language in `language`.
Ask before cloning: it costs credits and the person may not want a clone at all.

## Voicing with the clone

```
python3 engine/voice.py videos/<slug>/script.md          # all paragraphs -> videos/<slug>/tts/<name>-<voice>-<model>/
python3 engine/voice.py vertical/<batch>.md 3,4          # only videos 3 and 4 of the batch
```

- Each paragraph is one request with its neighbours as context, so intonation flows and word timing
  is exact. Paragraphs are cached by the full request (voice/model/settings, text and neighbours), with
  audio hashes and validated timestamps. Changed context revoices affected neighbours too; unchanged
  runs need no key. To force one request, delete its indexed mp3/JSON and matching `cache/<hash>` pair.
  Legacy text-only caches regenerate once; account for that before authorizing a paid run.
- Pauses: a paragraph in the script is a pause; punctuation and an ellipsis inside a paragraph make
  short ones. Break tags are not reliable, don't use them.
- **Pronunciation map** `style/config.json` → `voice.say`: `"ML": "em el"`, `"GPT": "gee pee tee"`.
  The text in the frame and the subtitles stay as written; only the voice reads the replacement.
  Abbreviations, product names and anything the model reads in the wrong language go here.
- Speed stays at 1.0; if the person wants faster, cut pauses, don't stretch the voice.

## Two voices: a sketch

A line starts with a speaker, `{tag}` right after the name is the intonation (format: `vertical/sketch.md`):

```
boss: {annoyed} Who spent the whole [budget] overnight?

dev: {whispers} Another [subagent].
```

- Speakers live in `style/config.json` → `voice.speakers`: `"boss": { "voice_id": "...", "settings": {} }`. An empty
  `voice_id` means the main `voice.voice_id`; `settings` replace the main ones for this speaker. Add or rename
  speakers there **before** voicing. Pick the second voice with `--list-voices`; the run warns if two speakers share one.
- `{tag}` goes to the model as the audio tag `[tag]` and is cut from the text, the word timing and the captions. Tags
  work on `eleven_v3` only, other models read them out, so the run stops. One or more tags, only at the start of a line:
  anywhere else, or after an unknown speaker, the run stops before any paid request. Split a line in two for a change of mood.
- Cache by voice: the key holds voice, tag and text. A new voice for one speaker revoices that speaker only; a new tag
  revoices that line only. Neighbours are context without tags.
- `who` reaches the scene in `TM.blocks`; `speakerWords(TM.blocks, "boss")` feeds `mouth()` for a 3D character (`3d`).
- Lines are not levelled against each other: check a shout next to a whisper by ear before the mix.

## When ElevenLabs fails

- An HTML page instead of JSON means the network is filtered (region, VPN, proxy). **Three attempts
  at most**, then stop and tell the person, even if they asked not to be interrupted. Never fall
  back to a system voice silently.
- Credits are shared by voice, speech-to-text and music. Say how many characters a run will use
  (`voice.py` prints it) before a big batch.

## Where things land

Voiced paragraphs next to the script in `tts/` (not in git), `.mp3` + `.json` per paragraph. `build.py --tts`
and `vertical.py build` read them. Timing is read from the voice, never typed by hand.
