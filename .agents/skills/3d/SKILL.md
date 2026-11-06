---
name: 3d
description: Build and render three.js scenes, characters and pure WebGL shader worlds with motion blur, depth of field and soft shadows. Flat graphics use graphics; the two-voice sketch text uses voice and vertical.
---

# 3D and shaders

Same idea as every other layer: a page the renderer seeks frame by frame. Only the way of drawing changes.
**Needs a video card.** macOS with Metal is verified; Windows and Linux are not. Check with
`node engine/render3d.mjs --doctor`. Inside an agent sandbox the browser cannot reach the GPU: run these
commands outside it. Never start a render with `&`. Look comes from `style/`: colors through tokens only.

## Which layer

| Need | Take | Why |
|---|---|---|
| Text, charts, interfaces | `graphics` (GSAP) | Fastest, sharpest; no 3D for what a flat page can do |
| Things, people, rooms, a camera around them | three.js, `lib/three3d.mjs` | Real objects with light and shadow, cheap to draft |
| A thing under text and captions | Mixed frame | The canvas lies in `#world`, everything readable stays HTML on top |
| A world without borders: endless city, liquid, clouds, space | Shader, `lib/shader.mjs` | The whole world is a formula, no geometry; the slowest render |

A thing or a person: three.js. A world with no edges: shader. Don't mix them in one page.

## three.js scene

`engine/scenes/<batch>/s<N>.mjs` next to the flat `s<N>.js`: `vertical.py build` adds the import map and the module by
itself. Reference: `engine/scenes/sketch/` with `vertical/sketch.md`.

```
const st = stage({ reach: 4, floor: false });     canvas in #world, camera, key light, fill, ACES
color("--acc")                                     a style token as a THREE.Color; never a literal
new RoundedBoxGeometry(...)                        soft edges instead of hard boxes
const cam = spline([[t, view(target, dist, az, el), stop], ...]);   camera through keys, times from words: B(), P(), W()
drive(0, D, (t) => { aim(st.camera, cam(t)); ...; st.renderer.render(st.scene, st.camera); });
pin(st, node, point, dx, dy)                       a flat HTML label follows a 3D point
mouth(speakerWords(TM.blocks, "boss"))             t -> mouth opening 0..1 from word timestamps
talking(words)                                     t -> smooth 0..1 over whole phrases: head turns, light, camera
```

`kit.js` globals work in the module. `stage()` options are documented above it: `spp`, `shutter`, `dof`, `soft`, `env`, `fov`,
`shift`. The module runs after `finish.js`: flat things go in `s<N>.js`, 3D in `s<N>.mjs`, data between them through `window`.
Characters are simple solids in code: no rig, no downloaded models. Move what is spoken about, not everything at once.

## Shader scene

Copy `engine/scenes/shader-example/` to `engine/scenes/<slug>/`, set size, `data-fps="60"` and length in `index.html`,
rewrite `FRAG` and `uniforms` in `scene.mjs`. The scene is `vec3 scene(vec2 uv, float t)`, linear color; colors come as `uBg`,
`uFg`, `uAcc`, `uMid`. Everything that moves is a function of `t` in `uniforms(t)` or in GLSL: it runs per subframe, that is
what makes the blur.

**Music first.** Build the scene on the track, never move the track under the picture:

```
python engine/beats.py track.mp3 engine/scenes/<slug>/beats.json --sheet marks.png --click check.wav
```

Look at the sheet, listen to the clicks, fix the JSON by hand. `markTimes(beats, "hit")`, `pulse`, `since`, `count` from
`lib/motion.mjs` turn the marks into motion. Rough flight first, details after: geometry and camera in `--draft`, then materials.
Preview: `python engine/serve.py`, `/scenes/<slug>/index.html?play` or `#t=2.5`.

## Commands

```
node engine/render3d.mjs <id or page> --still=1.2,4 [--spp=1]      one frame before spending a render; spp=1 is without subframes
node engine/render3d.mjs <id or page> --draft                      half size, few subframes -> <name>-draft.mp4
node engine/render3d.mjs <id or page> --from=12.4 --to=15          redraw a stretch, keep other frames
node engine/render3d.mjs <id or page>                              final -> engine/renders/<project>/<name>-video.mp4
node engine/render3d.mjs scenes/<slug>/index.html --audio=track.mp3   final with the track under it
python engine/vertical.py render <id> [--music track.mp3]          vertical: render3d, then the usual mix
```

`<id>` is a composition, `<page>` a path under `engine/`. The last lines of the output give the frames, seconds and file: report
that time. A failed run continues from the last frame; a changed scene starts over, `--from` keeps what is drawn. Side by side:
`compare.py stack`. Before any full render, render 2-3 seconds and multiply. Chapters of horizontal videos: `render.sh` still uses
HyperFrames; a 3D chapter renders here and is not wired into that script.

`verify.py` and the contact sheets work on three.js compositions through a software renderer: right layout, no subframes.
Shader pages have no timeline: check them with `--still` and read the frames yourself.

## Standard

- **Keep, it comes free with subframes:** motion blur (three.js shutter 180 degrees = `0.5` of a frame, 45-90 degrees where text
  must read; shaders 1.5 frames at 60 fps), depth of field on the view target, soft shadows from a jittered key light, smooth edges.
- **Subframes:** 16 for three.js, 8 for shaders, 8 is the floor for a final. **Size:** 1080p class, canvas at 1x.
- **Scene:** repeats through `InstancedMesh`, few shadow lights, up to about 1.5 million triangles. Assets only with a free
  license you can name (CC0), stored locally. One soft key light, a weak fill; paper white no brighter than about 0.8.
- **Determinism:** time only from `t`. No `Date.now`, `Math.random`, `requestAnimationFrame` or state carried between frames: frames
  render out of order and subframes step back in time. A pseudo-random needs a hash of an index.

## What we don't do

Path tracing, mirror floors and gloss everywhere, more than 16 subframes, a 2x canvas, parallel render processes (one video card:
they only get in each other's way), text inside 3D that must be read, eternal rotation and camera drift without a reason.

## Pitfalls

- One `drive()` per composition. Several 3D pieces: one `stage()`, one `drive(0, end)`, hide the canvas between them.
- Before a sharp camera start put a key with `stop: true`, otherwise the spline bends through walls.
- `fromTo(..., { immediateRender: false })` shows before its time: hide with `gsap.set(..., { opacity: 0 })`.
- A property changed from the module (opacity of a label) must not also be tweened in `s<N>.js`: two owners flicker.
- A color in `scene.background` hides everything in `#world` under the canvas and can clear the accumulation buffer: build a wall
  from a mesh, as `engine/scenes/sketch/s1.mjs` does, and keep the background transparent.
- Sky and stars: `depthTest: false`, `renderOrder` below 0; near plane about `dist * 0.012`.
- `gl.finish()` does not wait for the video card; the renderer reads one pixel instead. Keep that if you change capture.
- A seek to where the timeline already stands draws nothing: the renderer steps to a neighbour frame first.
- Never return `TL` from `page.evaluate`: it serializes without end.
- A NaN in one subframe spreads over the frame: guard `pow`, `sqrt`, `normalize` of zero in shaders.
- A double image in a shader `--draft` on fast motion is 2 subframes, not a bug; judge motion blur on a stretch at full `spp`.
- A shader that compiles on Metal may fail elsewhere: GLSL ES 3.00, explicit floats, loops with a constant bound.

## After the render, before showing

No frames from another moment or frozen frames, the camera passes through nothing, the mouth closes between words, nothing readable
sits under the platform UI. Then the `review` skill as usual.
