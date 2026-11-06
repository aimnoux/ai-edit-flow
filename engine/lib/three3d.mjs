/* three.js scenes for the kit. A 3D scene is scenes/<project>/s<N>.mjs next to s<N>.js: build.py adds the import map
   and the module to the composition by itself. s<N>.js stays an ordinary flat scene; the canvas lies in #world, so
   stage, captions and overlay stay sharp on top of it (the mixed frame).

     const st = stage({ reach: 4 });                 // canvas, scene, camera, key light, floor, fill
     st.scene.add(thing);                            // colors through color("--acc"), never literals
     drive(0, D, (t) => { aim(st.camera, cam(t)); st.renderer.render(st.scene, st.camera); });

   Time comes only from the timeline: no rAF, no clocks, no random. `?cine` (set by render3d.mjs) makes every frame
   the mean of N subframes: time inside the shutter (motion blur), camera on a point of the lens (depth of field),
   a subpixel shift (smooth edges), key light on a point of a sphere (soft shadows). Scenes do not change for it:
   drive() calls render once per subframe and renderer.render accumulates. */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { clamp, ease, halton, mouth, speakerWords, talking } from "./motion.mjs";

export { THREE, RoundedBoxGeometry, clamp, ease, mouth, speakerWords, talking };

const query = new URLSearchParams(location.search);
const CINE = query.has("cine"), DRAFT = query.has("draft");
let cine = null;

// render3d.mjs waits for textures, models and fonts through this counter
window.__pending = 0;
const manager = THREE.DefaultLoadingManager, start = manager.itemStart, end = manager.itemEnd;
manager.itemStart = (url) => { window.__pending++; start.call(manager, url); };
manager.itemEnd = (url) => { window.__pending--; end.call(manager, url); };

/** A style token as a color: color("--acc"). The look lives in style/tokens.css, scenes pick roles from it. */
export function color(name) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) throw new Error(`No token ${name} in lib/tokens.css`);
  return new THREE.Color(value);
}

/** Scene on a transparent canvas in #world. Options: reach (radius of the thing: light and shadow follow it), fov,
    shift (pixels to lift the center of view; 9:16 lifts it into the safe zone), fill (ambient), light (key power),
    exposure, floor: false (no shadow catcher), env (strength of reflections on metal), parent; for ?cine spp, shutter
    (share of a frame, 0.5 = 180 degrees), dof (lens radius as a share of the focus distance), soft (key light radius
    as a share of reach). */
export function stage(opt = {}) {
  const root = document.getElementById("root");
  const W = +root.dataset.width, H = +root.dataset.height, fps = +root.dataset.fps, S = DRAFT ? 0.5 : 1;
  const canvas = document.createElement("canvas");
  Object.assign(canvas.style, { position: "absolute", inset: "0", width: W + "px", height: H + "px" });
  (opt.parent || document.getElementById("world")).appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W * S, H * S, false);
  renderer.setClearColor(0, 0);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = opt.exposure ?? 1;
  const scene = new THREE.Scene();
  const r = opt.reach || 6, light = color("--light");
  const key = new THREE.SpotLight(light, opt.light ?? 12 * r * r, r * 7, Math.PI / 6, 0.45, 1.4);
  key.position.set(-0.55 * r, 2.2 * r, 0.8 * r);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.0002;
  key.shadow.radius = 4;
  key.shadow.camera.near = r;
  key.shadow.camera.far = r * 4;
  scene.add(key, key.target);
  scene.add(new THREE.HemisphereLight(light, color("--s2"), opt.fill ?? 0.45));
  if (opt.env) {
    scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment()).texture;
    scene.environmentIntensity = opt.env;
  }
  let floor = null;
  if (opt.floor !== false) {
    floor = new THREE.Mesh(new THREE.PlaneGeometry(r * 8, r * 8), new THREE.ShadowMaterial({ opacity: 0.55 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
  }
  const camera = new THREE.PerspectiveCamera(opt.fov || 38, W / H, 0.05, r * 15);
  const shift = opt.shift ?? (H > W ? 280 : 0);
  if (shift) camera.setViewOffset(W, H, 0, shift, W, H);
  const st = { renderer, scene, key, floor, camera, W, H, S, fps, r };
  if (CINE) cine = makeCine(st, opt);
  return st;
}

/** A camera position: target, distance, azimuth (radians, 0 = from the front), elevation (degrees). */
export const view = (target, dist, az, el) => ({ target, dist, az, el: (el * Math.PI) / 180 });

/** Camera through keys [t, view, stop] with a Hermite spline: speed changes smoothly. A key that is a peak in a channel
    stops that channel, others are limited so the camera never overshoots. stop: true before a sharp start. */
export function spline(keys) {
  const n = keys.length, T = keys.map((k) => k[0]);
  const X = keys.map(([, v]) => [v.target.x, v.target.y, v.target.z, v.dist, v.az, v.el]);
  const M = X.map((x, i) => x.map((_, j) => {
    if (i === 0 || i === n - 1 || keys[i][2]) return 0;
    const d0 = (X[i][j] - X[i - 1][j]) / (T[i] - T[i - 1]), d1 = (X[i + 1][j] - X[i][j]) / (T[i + 1] - T[i]);
    if (d0 * d1 <= 0) return 0;
    const m = (X[i + 1][j] - X[i - 1][j]) / (T[i + 1] - T[i - 1]);
    return Math.sign(m) * Math.min(Math.abs(m), 3 * Math.abs(d0), 3 * Math.abs(d1));
  }));
  return (t) => {
    if (t <= T[0]) return keys[0][1];
    if (t >= T[n - 1]) return keys[n - 1][1];
    let i = 0;
    while (t >= T[i + 1]) i++;
    const h = T[i + 1] - T[i], u = (t - T[i]) / h;
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
    const v = X[i].map((a, j) => a * h00 + M[i][j] * h10 * h + X[i + 1][j] * h01 + M[i + 1][j] * h11 * h);
    return { target: new THREE.Vector3(v[0], v[1], v[2]), dist: v[3], az: v[4], el: v[5] };
  };
}

/** Point the camera at a view; depth of field focuses on its target. */
export function aim(camera, v) {
  camera.userData.focus = v.dist;
  const c = Math.cos(v.el);
  camera.position.set(v.target.x + v.dist * Math.sin(v.az) * c, v.target.y + v.dist * Math.sin(v.el), v.target.z + v.dist * Math.cos(v.az) * c);
  camera.lookAt(v.target);
  camera.updateMatrixWorld();
}

const projected = new THREE.Vector3();
/** A flat label follows a point of the 3D scene: pixels of the frame, the text itself stays sharp HTML. */
export function pin(st, node, point, dx = 0, dy = 0) {
  projected.copy(point).project(st.camera);
  node.style.left = ((projected.x + 1) / 2) * st.W + dx + "px";
  node.style.top = ((1 - projected.y) / 2) * st.H + dy + "px";
}

/** Scene time from the timeline: render(t) runs on every seek between t0 and t1. One drive() per composition. */
export function drive(t0, t1, render) {
  const P = { t: t0 }, within = (t) => render(clamp(t, t0, t1));
  const go = cine ? (t) => cine.frame(t, within) : within;
  if (cine) cine.range = [t0, t1];
  TL.fromTo(P, { t: t0 }, { t: t1, duration: t1 - t0, ease: "none", immediateRender: false, onUpdate: () => go(P.t) }, t0);
  go(clamp(TL.time(), t0, t1));
  window.ready = true;
}

/** Subframe accumulation on top of stage(). Buffers are linear half float: tone mapping and sRGB happen once on output,
    transparency survives, so the page under the canvas shows through. */
function makeCine(st, opt) {
  const R = st.renderer, W = st.W * st.S, H = st.H * st.S;
  const N = +query.get("spp") || (DRAFT ? 4 : opt.spp || 16);
  const LENS = opt.dof ?? 0.003, SOFT = (opt.soft ?? 0.12) * st.r, SHUTTER = (opt.shutter ?? 0.5) / st.fps;
  const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType });
  const acc = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, depthBuffer: false });
  const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = (m) => { const q = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), m); q.frustumCulled = false; return new THREE.Scene().add(q); };
  const vs = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }";
  const add = new THREE.ShaderMaterial({ uniforms: { map: { value: rt.texture }, w: { value: 1 / N } }, vertexShader: vs,
    fragmentShader: "uniform sampler2D map; uniform float w; varying vec2 vUv; void main(){ gl_FragColor = texture2D(map, vUv) * w; }",
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneFactor,
    depthTest: false, depthWrite: false, toneMapped: false });
  // Color in the buffer is premultiplied (the scene draws on a transparent clear): divide, tone map, multiply back.
  const out = new THREE.ShaderMaterial({ uniforms: { map: { value: acc.texture } }, vertexShader: vs, fragmentShader: `uniform sampler2D map; varying vec2 vUv;
    void main(){ vec4 c = texture2D(map, vUv); float a = clamp(c.a, 0.0, 1.0); gl_FragColor = vec4(c.a > 1e-4 ? c.rgb / c.a : vec3(0.0), a);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
      gl_FragColor.rgb *= a; }`, blending: THREE.NoBlending, depthTest: false, depthWrite: false });
  const addScene = quad(add), outScene = quad(out), draw = R.render.bind(R);
  const right = new THREE.Vector3(), up = new THREE.Vector3(), eye = new THREE.Vector3(), lamp = new THREE.Vector3(), ball = new THREE.Vector3();
  const C = { mode: "pass", i: 0, range: [0, 0], gl: R.getContext(), last: null, spp: N };
  window.__cine = C;
  R.render = (scene, camera) => {
    if (C.mode === "pass") return draw(scene, camera);
    if (C.mode === "skip") return;
    const i = C.i, focus = camera.userData.focus || 5, A = focus * LENS;
    // Lens and subpixel shift: the camera moves on the pupil, the frustum moves back, the focus plane stays put.
    const rr = Math.sqrt(halton(i + 1, 2)), a = 2 * Math.PI * halton(i + 1, 3), lx = A * rr * Math.cos(a), ly = A * rr * Math.sin(a);
    eye.copy(camera.position);
    right.setFromMatrixColumn(camera.matrixWorld, 0);
    up.setFromMatrixColumn(camera.matrixWorld, 1);
    camera.position.addScaledVector(right, lx).addScaledVector(up, ly);
    camera.updateMatrixWorld();
    const P = camera.projectionMatrix.elements, jx = (halton(i + 1, 5) - 0.5) * 1.2, jy = (halton(i + 1, 7) - 0.5) * 1.2;
    P[8] += -P[0] * lx / focus + (2 * jx) / W;
    P[9] += -P[5] * ly / focus + (2 * jy) / H;
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    // Soft shadow: the key light sits on a random point of a ball of its size.
    const z = 2 * halton(i + 1, 13) - 1, v = halton(i + 1, 17), w = Math.cbrt(halton(i + 1, 19)), q = Math.sqrt(1 - z * z);
    lamp.copy(st.key.position);
    st.key.position.add(ball.set(q * Math.cos(2 * Math.PI * v), q * Math.sin(2 * Math.PI * v), z).multiplyScalar(w * SOFT));
    st.key.updateMatrixWorld();
    R.setRenderTarget(rt);
    draw(scene, camera);
    R.setRenderTarget(acc);
    if (i === 0) R.clear();
    R.autoClear = false;   // otherwise render clears the buffer and only the last subframe survives
    draw(addScene, ortho);
    R.autoClear = true;
    R.setRenderTarget(null);
    camera.position.copy(eye);
    camera.updateMatrixWorld();
    camera.updateProjectionMatrix();
    st.key.position.copy(lamp);
    st.key.updateMatrixWorld();
  };
  C.frame = (t, render) => {
    C.mode = "acc";
    for (let i = 0; i < N; i++) { C.i = i; render(t + ((i + halton(i + 1, 11)) / N - 0.5) * SHUTTER); }
    C.mode = "skip";
    render(t);   // scene state and pinned labels end at the exact moment of the frame
    C.mode = "pass";
    R.setRenderTarget(null);
    draw(outScene, ortho);
    C.last = { t };
  };
  return C;
}
