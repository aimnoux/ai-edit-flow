# Visual style

<!-- TEMPLATE. The `style` skill fills this file with the person, section by section, over several
sessions. Until it is filled, there is no style: scenes use the neutral tokens from tokens.css and the
agent must ask before choosing a look. Delete the hints in angle brackets as you fill a section. -->

Single source of rules for everything that is seen and heard: horizontal and vertical video, covers,
thumbnails. Skills refer here and don't repeat. A correction from the person about the look goes
here as a general rule, not into a scene.

Palette and fonts in code: `style/tokens.css`. Voice, channel names and captions: `style/config.json`.
Background world of the frame: `style/world.html` (16:9) and `style/world-v.html` (9:16), overlays
on top of everything: `style/overlay.html`. Sound bank: `style/sound/`.

## Who speaks and to whom

<!-- Who the person is on camera (role, no company names if they prefer), who watches, what language
the viewer reads in the frame. One paragraph. -->

## Palette

<!-- 3 to 6 named colors with their roles: background, surface, main text, secondary text, accent.
Is the accent a color or light? What never appears (e.g. gradients, neon, a light theme)? -->

## Type

<!-- Display font, mono font, where each one is allowed. Sizes for the hero line, headings, body,
captions. Tracking limits. Where the font files live (`style/fonts/`), loaded in tokens.css. -->

## The world of the frame

<!-- What the frame is: a material, a desk, a room, a flat color, a texture. What a "thing" in this world
looks like (a document, a phone, a chat window): real product look or abstraction? Minimum size of the
main thing (e.g. 40 % of the frame). Light: one source or none, where it falls. -->

## Motion

<!-- Durations and easing for enter / exit / camera moves. What is forbidden (bounces, pulsing loops,
shakes, flashes). How things appear (push in, mask, wipe, stamp) and leave. How often a new event
must happen (e.g. every 1.5-3 s in 16:9, every 0.7-1.5 s in 9:16). -->

## Text in the frame

<!-- Language of everything readable. What goes on screen (a term, a number, a name) and what never
does (the sentence being spoken). Marker and strike-through look. Subtitles: embedded or not, where. -->

## Sound

<!-- What sounds: things in the frame or abstract effects. Music direction (genre, tempo, mood), where it
comes from. Levels if they differ from the kit defaults (voice -16 LUFS, final -14 LUFS, true peak
-1.5 dBTP). Minimum gap between effects. -->

## Vertical video

<!-- Safe zones for the platform UI, caption position, ending for each platform (what the viewer is
asked to do), loop rules for formats without voice. -->

## Review checklist, style layer

<!-- The general layer lives in the `review` skill. Here: what is "slop" for THIS style, with numbers so
the reviewer can measure. Examples: "marker is always <color>, any other color is P0", "corner radius of
our cards 12-16 px, larger is a default", "every readable text in <language>", "glow only on the one
active word", "no thing smaller than 40 % of the frame height". Each item: code (S-01, S-02, ...), one
line, what counts as P0. -->

- **S-01** <!-- ... -->
