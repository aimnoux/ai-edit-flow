---
status: example
rolls: [1]
---

# Vertical batch: a sketch with two voices

The format of `vertical/example.md` plus speakers. A line starts with a speaker from
`style/config.json` -> `voice.speakers`; `{tag}` right after the name is the intonation. Tags go to
the voice only, the frame and the captions never show them. Scene: `engine/scenes/sketch/s1.js` (flat
layer) and `s1.mjs` (3D). Try it without a voice:

`python engine/vertical.py build vertical/sketch.md 1 yt --estimate`, then
`node engine/render3d.mjs sketch-s1-yt --draft`.

## 1. The missing budget

### 1.0

Video one.

### 1.1

boss: {annoyed} Who spent the whole [budget] overnight?

dev: {nervous} Not me. It was the [subagent].

### 1.2

boss: {suspicious} And who started the subagent?

dev: {whispers} Another [subagent].

### 1.3

boss: {shouting} And who started that one?

dev: {calm} Your [agent], boss.

### 1.8

dev: Tap [like] before he reads the bill.
