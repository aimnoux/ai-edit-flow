# ai-edit-flow

**English** · [Русский](README.ru.md)

A starter kit for editing video with Claude Code. You record, Claude edits: cuts takes and pauses, cleans the voice, draws motion graphics in code, reviews frames, mixes sound and renders the final file. You never open a timeline.

## What this is

A skeleton of an editing pipeline that an agent runs end to end. It ships as a set of skills and scripts for Claude Code, from a raw recording to a finished video:

- **Cut** — removing bad takes, pauses and filler from the recording
- **Voice** — cleanup and, if you want, a clone of your voice for retakes
- **Graphics** — titles, charts and transitions written as code, not clicked together
- **Review** — a second agent checks every frame against a checklist before you see it
- **Sound** — music, effects and the mix
- **Render** — the final file, ready to upload

Two formats: horizontal video (16:9) and vertical (9:16, one build for Shorts, Reels and TikTok; the ending is a parameter, not a branch of code).

There is no visual style inside. The kit gives you the bones; your own look you grow with Claude, session by session. A dedicated skill interviews you and writes your style file.

## What it is not

Not a video editor and not a plugin for one. Not a model, not a service, no account. It is a repository you open in Claude Code and talk to.

## Install

You need: [Claude Code](https://claude.com/claude-code), git, Python 3.10+, Node.js 22+, ffmpeg and Google Chrome (or Chromium). An [ElevenLabs](https://elevenlabs.io) key is optional: it powers speech-to-text for the cut, voice cloning and music.

```bash
git clone https://github.com/aimnoux/ai-edit-flow.git
cd ai-edit-flow
bash setup.sh
```

`setup.sh` checks the tools, installs the Python packages and creates `.env` from `.env.example`. Put your ElevenLabs key into `.env` if you have one. Then open the folder in Claude Code and say what you want: "set up my style", "here is my recording, cut it", "make a vertical from this text".

The repository was built on macOS and then adapted for Linux and Windows, where it has not been tested yet; expect rough edges. On Windows run `setup.sh` and `engine/render.sh` from Git Bash. Paths to Chrome, fonts and caches are found automatically; if Chrome is not found, set `CHROME_PATH` in `.env`.

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
