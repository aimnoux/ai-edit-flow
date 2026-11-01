# Independent frame review

Read this reference only as the fresh reviewer. Apply the general checklist below and the project's
style layer from `style/visual.md`; judge the visible result, without scene code or builder history.

## How to look (for the reviewer)

Describe every frame of the beats sheet in one sentence as a stranger would, naming each object. Then
read the frames in order: does a stranger follow the story, does each frame follow from the previous?
Then go through "Check" item by item, and "Refuse" for what is on screen. Numbers in `REVIEW-INPUT.md`
beat the eye: a line held 0.6 s looks fine on a sheet. You don't hear the sound; say so and judge the cues
by their times.

## Check: visible only in the render

Composition
- **C-01** Pause test: any frame stopped at random looks intended, not caught mid-animation.
- **C-02** It reads as what it is. An object that needs explaining ("those rectangles are shelves") is P0.
- **C-03** One focus: the main thing is separated from the rest by brightness; the eye knows where to go.
- **C-04** The frame is filled: the main thing is at least 40 % of the height or width, not a speck in
  the middle, not only the top third.
- **C-05** Edges: nothing cut off, no text at the edge or under the platform UI (9:16: right and bottom),
  no service element half out of the frame. A key number of a thing is not cut by its own edge.
- **C-06** Without words: cover the text, mute the voice; the frames still tell the story.

Motion
- **M-01** Attention lulls (`REVIEW-INPUT.md`): more than 1.5 s without an event in 9:16, 3 s in 16:9, is P1.
  Fill with the camera moving to what is spoken, a thing, a marker; not with jitter.
- **M-02** Rhythm with stops: hit → hold 15-20 frames → build → hit. Everything moving all the time is P1.
- **M-03** Seams (the seams sheet): no jump, no empty frame between one thing leaving and the next
  arriving, no new text over the old one still fading.

Text
- **T-01** A line holds at least as long as it takes to read: 0.5 s + 0.3 s per word.
- **T-02** The phone sheet: everything that must be read is readable at 360 px width.
- **T-03** Text stands still while it is read: no drift after landing, no jump when more is typed, no
  motion blur on readable shots.

Frame and voice
- **V-01** The frame shows a term, a number, a name or a scheme, not the sentence being spoken.
- **V-02** The climax lands on its word: an answer, a number, a reveal, not 2-3 s before or after, and
  holds at least 1 s before a cut. A mark ("?", a marker) never before the thing it marks.

Physicality (3D, light, materials)
- **L-01** Things are physical: no parts through a body, a contact shadow under a thing, a camera
  that never passes through walls, nothing floating without a reason.
- **L-02** Light has a source: a switched-off lamp doesn't glow, paper has falloff, highlights don't
  cover text.
- **L-03** Fonts are loaded before the frame: no font swap mid-shot.
- **L-04** After a re-render every frame resembles its neighbours: no frame from another moment.

Sound (by cues)
- **S-01** The hit is on the word, not before or after; a ring doesn't run through a cut.

## Refuse: the defaults a generated video falls into

Composition
- **C-07** Everything centered; three cards in a row; a KPI grid; "big number + caption" instead of a thing.
- **C-08** An empty shell waiting seconds for its content (a chat window, a grid); a highlighted cell
  with nothing in it while the example sits in a caption.
- **C-09** Frame zero is empty; every scene starts from an empty frame.
- **C-10** A foreground object blocks the main thing on the camera path; an empty room with one desk.
- **C-11** A metaphor that needs decoding instead of showing what the viewer already saw; "X ≠ Y" on
  chips where X and Y are different kinds of things; a hook about something not in the frame.
- **C-12** The same thing in the hook and in the story with different content; the climax repeats an
  earlier frame instead of a new event on the word.
- **C-13** A template ending: a fade to black, a flat gradient instead of the world, gradient text, a
  spinning counter of random symbols; a card standing 3 s unchanged under the call. The ending is made
  of the video's own things.
- **C-14** A thing's text under the captions or under a chip; a dark bar across the frame under the captions.
- **C-15** A detail of an illustration contradicts the story's hero; a printed label cut to syllables by
  edges or flags.
- **C-16** A vertical with no voice and no sound under a meme; the hook not in the first spoken line;
  a cheat sheet as a table instead of a scene per item; two texts typing at the same time.

Motion
- **M-04** The only entrance is a fade with an upward shift. There are line masks, clip-path, reframing,
  overlap, focus, a shadow; a thing can be put down.
- **M-05** Only opacity animates. Animate meaning: scale from the source, a shared element between
  frames, light moving from thing to thing.
- **M-06** The same entrance for every scene and thing; every exit the same throw to the left.
- **M-07** Everything at once, or everything on one soft curve at one speed. Curves by role: entrance
  sharp start and long settle, exit accelerating, camera soft at both ends, the main move longest.
- **M-08** Exit as long as the entrance. Exit shorter, 0.35-0.5 s, but not a click; frame changes and
  zooms 0.6-1.0 s, soft in-out.
- **M-09** A cascade on everything (title words, scheme details). Only on a real list, 0.3 s in all.
- **M-10** Bounces and springs; breathing, pulsing, blinking loops; a slow push-in; text drifting while
  it is read; linear motion on anything but mechanics (a tape, a progress bar); camera drift.
- **M-11** Several camera moves in 2 s (on a climax: one move and stop); the camera standing while
  letters type or a cursor blinks; leaving before the result line; a thing flying out half typed.
- **M-12** A push-in that stops short (at the width of the sheet) or overshoots (text wider than ×1.3-1.4);
  cuts off the first letters; enlargement by a cut instead of a move.

Text
- **T-04** The main thing small: axes and categories of a scheme, the climax (answer, verdict, number)
  at body size or a label at 8 % of the frame, the conclusion as a small line at the bottom, the first
  frame of a vertical in small lines.
- **T-05** Typing: a user's question typing for seconds in the input (in a chat the sent bubble is
  visible); letter by letter at an even pace; a word jumping to the next line (an AI answer streams:
  `typeText(..., { stream: true })`); a code comment typing under the voice as a caption.
- **T-06** A counter: digits shivering in width (tabular or mono digits), values that are powers of two,
  a caption for the wrong phase, a counter passing the spoken order of magnitude later than the word.
- **T-07** Fonts as costume: an interface in mono, mono labels over every block, corner labels, "01 / 02";
  a serif italic title for mood.
- **T-08** Neighbouring sizes closer than ×1.25; tracking tighter than -0.04 em.
- **T-09** A caption ending on a conjunction or an article, a hanging word; a column where every line
  wraps; a page in two languages; one entity under different names on labels and in the voice.
- **T-10** Readable text in a language the viewer doesn't read: chats, letters, interfaces, labels,
  documents. The style layer names the language; what is foreign is translated. P0 when it stands out.

Frame and voice
- **V-03** Text echo: the frame types what is being said; a title that doubles the caption.
- **V-04** A document shows a result before the word it is found on: before the word a "?", the value
  lands on the word.

Light and color
- **L-05** Glow, flares, rings and particles for decoration; a glowing ball without a source; a running
  sheen nobody asked for. The style layer says what glow, if any, is the style.
- **L-06** Gradient text; purple gradients and cyan on dark; a cream background.
- **L-07** A marker of several colors on one sheet; a marker that goes out while the word is spoken.
- **L-08** The marker on the wrong thing: longer than the text or over empty space; a whole line when one
  word is spoken; a column instead of a pair of lines; a highlight the product doesn't have; every
  earlier marker still on when returning to a document.
- **L-09** A strike-through in red or "by hand"; green and red more than once per video; color on a thing
  that has none; one color in two meanings; one emphasis device in two meanings in a row.
- **L-10** Chromatic aberration doubling text in the middle of the frame.

Graphics
- **G-01** An object made of rectangles instead of a recognizable thing (shelves, a cart, a brain of
  nodes); geography from sharp polygons; indicators as a grid of dots; a rocket's fire as a trail.
- **G-02** A placeholder instead of a thing: a grey frame with a label, empty grey cells, a spinner, a
  cover as a gradient square with stripes, a catalog of single-color tiles, a body in impossible
  proportions, a crowd of nameless objects with grey bars for labels.
- **G-03** A product replica that doesn't live like the product: resets between lines; the answer
  appears in a jump, not a stream; scroll runs over a pinned header; a log with time going backwards;
  a made-up system label; code without a code block; a preview as a slideshow.
- **G-04** A summary card: a sheet of the script's conclusions or UI checkmarks instead of the document
  and the interface the viewer already saw.
- **G-05** Glass, pill chips, cards inside cards; a "ghost card" (a thin border and a wide shadow: one or
  the other); corner radii larger than the style layer allows.
- **G-06** A colored stripe on the side of a card; an icon in a tile above a heading (an icon goes inline).
- **G-07** Frames and HUD for decoration, ticks and rulers that measure nothing; a grid or stripes on a
  background that is not a map or a drawing.
- **G-08** A crooked "hand-drawn" SVG and noise over the frame: an illustration or clean geometry.
- **G-09** A circle instead of an object's contour; a circled outline instead of a marker.
- **G-10** Emoji and symbols (✓ ✗ ★) instead of icons: one library, one stroke width.
- **G-11** A scheme that lies by its form: a line chart for what is not a time series; labels of the next
  state on the previous one; a change whose size contradicts the words; 3D bars hiding each other.

Sound (notes for the builder)
- **S-02** A sound on every cut, synthesized dings, a tick on every appearance. Sound belongs to the main
  action and comes from the thing; one hit per vertical.

## Answer format

Start with `Fingerprint: <hash>` copied exactly from `REVIEW-INPUT.md`, followed by exactly one
`Verdict: PASS` or `Verdict: FAIL`. PASS requires no unresolved P0 and all P1
chosen for correction resolved; FAIL identifies remaining blockers. A machine pass is not this verdict.

One line per problem, with the code when there is one:

```
t=4.2s · where · M-08 problem → the exact fix · what not to touch
```

Ranks:
- **P0** breaks understanding or a rule: unreadable, wrong, broken, a "ban" item of the style layer,
  slop in the main frame.
- **P1** weakens: a dead stretch, a weak climax, a jump at a seam.
- **P2** polish.

No scores "out of 10": a score finds nothing to fix. At the end: new signs for the style layer (group and
wording), if any, and the weakest frame with what to change given more time.
