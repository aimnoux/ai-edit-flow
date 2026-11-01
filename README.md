# ai-edit-flow

**English** · [Русский](README.ru.md)

A starter kit for editing video with Claude Code. You record, Claude edits: cuts takes and pauses, cleans the voice, draws motion graphics in code, reviews frames, mixes sound and renders the final file. You never open a timeline.

## What this is

A skeleton of an editing pipeline that an agent runs end to end. It ships as a set of skills and scripts for Claude Code, from a raw recording to a finished video:

- **Cut** — removing bad takes, pauses and filler from the recording
- **Voice** — cleanup and, if you want, a clone of your voice for retakes
- **Graphics** — titles, charts and transitions written as code, not clicked together
- **Review** — a second agent checks sampled frames and scene transitions against a checklist before you see it
- **Sound** — music, effects and the mix
- **Render** — the final file, ready to upload

Two formats: horizontal video (16:9) and vertical (9:16, one build for Shorts, Reels and TikTok; the ending is a parameter, not a branch of code).

There is no visual style inside. The kit gives you the bones; your own look you grow with Claude, session by session. A dedicated skill interviews you and writes your style file.

## What it is not

Not a video editor and not a plugin for one. Not a model, not a service, no account. It is a repository you open in Claude Code and talk to.

## Install

You need: [Claude Code](https://claude.com/claude-code), git, Python 3.10+, Node.js 22+ and ffmpeg (including ffprobe). Rendering uses a dedicated `chrome-headless-shell`, downloaded by setup; your personal Google Chrome is not used. An [ElevenLabs](https://elevenlabs.io) key is optional: it powers speech-to-text for the cut, voice cloning and music.

```bash
git clone https://github.com/aimnoux/ai-edit-flow.git
cd ai-edit-flow
bash setup.sh
source .venv/bin/activate
```

`setup.sh` checks the required tools, creates a local `.venv` (or uses your already activated Python virtual environment), installs Python packages there, creates `.env` from `.env.example` and downloads the dedicated browser through `node engine/hf.mjs browser ensure`. It exits with an error if a required step fails. It does not install Python packages globally or run a render. Put your ElevenLabs key into `.env` if you have one. Then open the folder in Claude Code and say what you want: "set up my style", "here is my recording, cut it", "make a vertical from this text".

Activate the virtual environment before running Python scripts or opening Claude Code from the terminal, so child commands inherit its `PATH`. On Windows Git Bash use `source .venv/Scripts/activate`. If you used an existing environment, keep that one active instead. Rendering does not require an ElevenLabs key; speech-to-text, cloning and music generation use paid API services when you request them.

The kit was built on macOS. Linux and Windows adaptations have not been fully tested; Windows commands require Git Bash, native Python/Node.js and ffmpeg on `PATH`. The pinned browser download does not support Linux ARM64: provide a compatible dedicated `chrome-headless-shell` via `CHROME_PATH` in `.env`; setup will not install system Chromium. Older systems may also need a compatible shell build.

Browser lookup accepts `CHROME_PATH` first, then the HyperFrames cache (`~/.cache/hyperframes/chrome/chrome-headless-shell/`) and Puppeteer's headless-shell cache (`PUPPETEER_CACHE_DIR` or `~/.cache/puppeteer`). Only `chrome-headless-shell` executables are accepted, including symlink targets. Regular Chrome and Chrome for Testing desktop apps are not used. Each command uses an isolated temporary profile and cleans up its browser; the HyperFrames warm daemon is disabled.

## Recording and script format

A live recording may be audio or video. The cut writes `voice.wav` for audio-only input and `rough.mp4` for video, plus `words.json` and `edl.json`. Horizontal videos then use chapter padding; vertical videos take the cut directory directly with `vertical.py build ... --cut <dir>`.

Speech lives under `### N.M` headings. Separate paragraphs with a blank line; wrapping one paragraph across several source lines does not introduce an extra pause. `> ` notes, tables and headings are not spoken. Vertical batches use `N.0` for recording slates, `N.8` for the YouTube ending and `N.9` for the Instagram/TikTok ending.

## What is inside

```
.claude/skills/    nine skills: edit, cut, voice, graphics, vertical, review, sound, render, style
engine/            scripts (Python, Node) and a small library for compositions, no style in it
style/             your style: templates to fill
videos/<slug>/     a horizontal video: script, settings; recordings and voice are not in git
vertical/          vertical videos: one text file per batch
CLAUDE.md          how the agent works with you
```

Graphics are rendered with [HyperFrames](https://hyperframes.heygen.com) (HTML + GSAP compositions), pinned to one version in `package.json`.

## Status

Work in progress. The kit is being assembled alongside a free video course that walks through the whole pipeline. The course link will appear here.

MIT license.
