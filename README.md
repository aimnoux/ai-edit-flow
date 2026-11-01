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

There is no visual style inside. The kit gives you the bones; your own look you grow with Claude, session by session. A dedicated skill interviews you and writes your style file.

## What it is not

Not a video editor and not a plugin for one. Not a model, not a service, no account. It is a repository you open in Claude Code and talk to.

## Status

Work in progress. The kit is being assembled alongside a free video course that walks through the whole pipeline. The install guide and the course link will appear here.
