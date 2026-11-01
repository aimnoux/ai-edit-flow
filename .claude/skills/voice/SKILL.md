---
name: voice
description: The voice of a video. Use when the person asks to clean a recording, clone their voice, voice a script or a vertical batch with the clone, re-voice one line, fix how a word is pronounced, or when ElevenLabs fails. Covers cleanup recommendations, cloning (engine/tts_elevenlabs.py --clone), voicing with word timing (engine/voice.py), the pronunciation map in style/config.json, credits and the attempt limit.
---

# Voice

Two sources of voice, never mixed inside one video: a **live recording** (cut with `cut`, cleaned by
the person) or a **clone** (ElevenLabs, voiced paragraph by paragraph with word timing). A course,
a trailer, a batch of verticals: each is one source throughout.

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
  is exact. Paragraphs are cached: a second run voices only what changed. To re-voice a line, change
  its text (or delete its mp3) and run again.
- Pauses: a paragraph in the script is a pause; punctuation and an ellipsis inside a paragraph make
  short ones. Break tags are not reliable, don't use them.
- **Pronunciation map** `style/config.json` → `voice.say`: `"ML": "em el"`, `"GPT": "gee pee tee"`.
  The text in the frame and the subtitles stay as written; only the voice reads the replacement.
  Abbreviations, product names and anything the model reads in the wrong language go here.
- Speed stays at 1.0; if the person wants faster, cut pauses, don't stretch the voice.

## When ElevenLabs fails

- An HTML page instead of JSON means the network is filtered (region, VPN, proxy). **Three attempts
  at most**, then stop and tell the person, even if they asked not to be interrupted. Never fall
  back to a system voice silently.
- Credits are shared by voice, speech-to-text and music. Say how many characters a run will use
  (`voice.py` prints it) before a big batch.

## Where things land

Voiced paragraphs next to the script in `tts/` (not in git), `.mp3` + `.json` per paragraph. `build.py --tts`
and `vertical.py build` read them. Timing is read from the voice, never typed by hand.
