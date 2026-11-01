# CLAUDE.md

A starter kit for editing video with Claude Code. The person records; you cut, voice, draw graphics
in code, review frames, mix sound and render. There is no visual style in this repository: the
person's style lives in `style/` and is built with the `style` skill. Never invent a look. If
`style/visual.md` is still the template, run `style` first.

## How to work with the person

- **Plan first, then the person's "ok", then actions.** Propose your own variant right away, don't
  hand the choice back. Inside an approved plan do the steps yourself. Ask only when you cannot move
  without the person, one question with the reason.
- Every step of a video ends with something to look at: a contact sheet, a draft render, a mix.
  **Review frames before showing anything** (`review` skill). The person sees work that already
  passed the checklist.
- After a chunk of work, report briefly: what was done, what to look at, what is next.
- Keep the person's feedback as a rule, not as a note: a correction about the look goes into
  `style/visual.md`, a correction about the process goes into the matching skill.
- Logs go to files; read the tail and the errors. Frames go to one contact sheet, reduced in size.
- Nothing from `.env` (keys) is printed or committed. Commit when the person asks.

## Task → skill

| Task | Skill |
|---|---|
| New video, where to start, order of steps, what is ready | `edit` |
| Cut takes and pauses out of a recording | `cut` |
| Clean the voice, clone it, re-voice a line | `voice` |
| Titles, charts, interfaces, transitions in code | `graphics` |
| Vertical video 9:16 (Shorts, Reels, TikTok) | `vertical` |
| Check frames before showing | `review` |
| Music, sound effects, mix, loudness | `sound` |
| Render, resume, final files | `render` |
| Build or change the person's style | `style` |

## Where things are

```
style/             the person's style: visual.md, tokens.css, config.json, sound/, world.html
videos/<slug>/     a horizontal video: script.md, video.json, drops.json; cut/, tts/ are not in git
vertical/          vertical videos: one .md per batch, tts/ is not in git
engine/            scripts, lib/, templates; scenes/<project>/, build/, renders/ (last two not in git)
engine/scenes/     your code per project: ch<N>.js for a horizontal video, s<N>.js for a vertical one
.claude/skills/    the skills above
package.json       the single HyperFrames version pin; scripts run it through engine/hf.mjs
```

## Rules that hold everywhere

- Graphics are code: HyperFrames compositions, GSAP timelines, deterministic (no `Date.now()`,
  no `Math.random()`, no network). Fonts and libraries are local.
- Timing comes from the voice: word timestamps, `W("1.2", "phrase")` in scenes. Never guess times.
- One HyperFrames version, pinned in `package.json`. Run it as `node engine/hf.mjs <command>`.
- After every change to a composition: `python3 engine/check.py <id> --hf` (script errors, then the
  HyperFrames lint), fix before showing.
- Paths through variables and auto-detection (Chrome, fonts, cache), nothing OS-specific in code.
- Finished files go to `engine/renders/<project>/`. Don't send files into the chat.
