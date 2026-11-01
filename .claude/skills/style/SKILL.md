---
name: style
description: Building and keeping the person's visual and sound style, session by session. Use when style/visual.md is still the template, when the person wants to set up, change or discuss their look (palette, fonts, the world of the frame, motion, sound, captions, endings), says "set up my style", gives feedback about how something looks, or when another skill finds no style to work from. Writes style/visual.md, style/tokens.css, style/config.json, style/world.html, style/overlay.html, the sound bank plan and the style layer of the review checklist.
---

# Style

The kit has no look. The person's look lives in `style/` and grows one decision at a time; your job is
to ask, propose, write it down and test it in a real frame. A style assembled wholesale from other
people's references comes out as a template; grow from one strong decision and add the next only when
the previous one is in a rendered frame.

## Files

```
style/visual.md       the rules in words: who, palette, type, the world, motion, text, sound, vertical, review layer
style/tokens.css      the same in code: colors, fonts (@font-face from style/fonts/), sizes, radii, glow
style/config.json     language, voice (id, model, pronunciation), channel (name, avatar), captions (weak words)
style/world.html      the background world of a 16:9 frame (HTML/SVG inside #world); style/world-v.html for 9:16
style/overlay.html    what sits over everything (grain, vignette); style/overlay-v.html for 9:16
style/sound/          the bank and sounds.json (see the sound skill)
style/fonts/, style/assets/   font files, avatar and images the style uses (copied into engine/lib/ at build)
```

`build.py` and `vertical.py` copy tokens, fonts and assets into `engine/lib/` and paste the world and
overlay slots into the templates; nothing in `engine/` has to change for a style.

## The first session (about an hour, in steps, an "ok" after each)

1. **Who and for whom.** Who the person is on camera, who watches, on what device, in what language
   the viewer reads the frame. Write the first section of `visual.md`.
2. **One decision that defines the look.** Not a mood board: one thing. Examples of the kind of
   decision: "the frame is a real desk under one lamp and everything is a physical object on it", "black
   background, white type, one accent color and nothing else", "every scene is a screenshot of a real
   product, zoomed by the camera". Offer three such decisions, each with what it forbids. The person
   picks one; it goes into "The world of the frame".
3. **Palette and type.** 3-6 colors with roles, contrast of secondary text ≥ 4.5:1 on the background,
   one display face and one mono face, local files in `style/fonts/` (OFL or licensed; never a CDN).
   Write `tokens.css`. Sizes: the floor for readable text is 28 px at 1080 height (phones), the main
   line at least 64 px in 16:9.
4. **Test on the example.** `python3 engine/build.py example --estimate`, `python3 engine/shots.py example-ch1 1 4 7`,
   and the vertical example. Look at the sheet with the person. Adjust tokens, not scenes.
5. **Motion.** Durations and curves (the kit's defaults are in `kit.js`: EASE, DUR), the list of what is
   forbidden (bounces, pulses, drift, flashes are off already), how things enter and leave, the event
   rate (1.5-3 s in 16:9, 0.7-1.5 s in 9:16 unless the person wants calmer).
6. **Text in the frame.** Language, marker look (`--marker`), strike-through, what never goes on screen.
7. **Sound.** Does a thing sound or an effect? Music direction. The first five sounds of the bank
   (`sound` skill makes them).
8. **Vertical.** Endings per platform (what the viewer is asked), captions, the channel name and
   avatar in `config.json`.
9. **Review layer.** 5-10 lines with codes `S-01...`: what is slop for this style, with numbers, and
   what is P0. These are the items the reviewer checks on top of the general list.

Each later session takes one section further or records a decision from feedback.

## World and overlay

`world.html` is the content of the `#world` layer: HTML and SVG, sized to 1920×1080 (1080×1920 in
`world-v.html`), static or lit by CSS. Keep it cheap to render: no heavy filters over the full frame on
every frame, bake a texture into an image in `style/assets/` when a filter is slow. `overlay.html` is
what sits above the scenes (`#overlay`): a vignette, grain, a frame. Both are optional; an empty style
has an empty world and the background color of `--bg`.

## Keeping the style

- **Feedback becomes a rule.** "The marker is too pale" → the marker color in `tokens.css` and a line in
  `visual.md`; the scene changes with it. Never fix only the scene.
- **One rule, one place**: words in `visual.md`, values in `tokens.css`; no duplicates across skills.
- **Decisions not to revisit**: keep a short list at the end of `visual.md` ("we tried a light theme,
  rejected") so a later session doesn't propose them again.
- Short: no history, no dates, no quotes. The history is in git.
- A new format (a new kind of vertical, a new thing in the world) is a few lines in `visual.md` and a
  function in `engine/scenes/<project>/things.js` or `style/things.js`; the kit stays as it is.
