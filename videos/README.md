# videos/

One folder per horizontal video, named by a short slug:

```
videos/<slug>/
  script.md      what is said, in `### N.M` blocks; chapters are `## N. Title` (see example/)
  video.json     head/tail silence per chapter, end tail
  drops.json     takes to drop from the recording, [[start, end], ...] in seconds of the source
  cut/           output of engine/cut.py: rough.mp4, words.json, edl.json   (not in git)
  tts/           cached paragraphs of a cloned voice (engine/voice.py)        (not in git)
```

Scenes for the video: `engine/scenes/<slug>/ch<N>.js`, one per chapter. Compositions and renders:
`engine/build/<slug>/`, `engine/renders/<slug>/`.

`example/` is a complete small script. `python3 engine/build.py example --estimate` builds its
compositions without a recording, with word timing estimated from the text, so you can try the
graphics pipeline before recording anything.
