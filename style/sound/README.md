# Sound bank

Sound effects the mix places at the cues scenes write with `sfx("name", t)`. The bank is the
person's: the kit ships none. The `sound` skill helps to generate them (ElevenLabs sound effects
or any other tool), pick takes and set levels.

```
style/sound/
  sounds.json        levels, aliases, which cues are "main" (survive a collision) and "quiet"
  tap.mp3            one file per cue name
  takes/tap-1.mp3    extra takes of the same sound, rotate automatically
```

- Files are mono or stereo, any sample rate; `mix.py` resamples to 48 kHz.
- Level files to about −20 dB RMS so the gains in `sounds.json` mean the same across the bank.
- `gap` in `sounds.json`: minimum seconds between two effects; when two collide, the one listed
  in `main` stays, the other is dropped. `quiet` cues are never played (keep them in scenes for
  a style that wants them).
