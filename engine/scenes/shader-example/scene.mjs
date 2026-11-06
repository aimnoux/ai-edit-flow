/* A neutral shader scene to copy: a ball hops across a plane on the hits of the track, the camera swings wider on the
   drop. Everything that moves is a function of time and marks; the picture is built around the music, never the other
   way round. New scene: copy this folder to engine/scenes/<slug>/ and rewrite FRAG and uniforms.

   Preview:  python engine/serve.py, then /scenes/<slug>/index.html?play or #t=2.5
   Render:   node engine/render3d.mjs scenes/<slug>/index.html --draft */
import { shaderScene } from "../../lib/shader.mjs";
import { clamp, count, ease, markTimes, pulse } from "../../lib/motion.mjs";

const beats = await (await fetch("beats.json")).json();
const hits = markTimes(beats, "hit"), drop = markTimes(beats, "drop")[0] ?? Infinity;

const FRAG = /* glsl */ `
uniform vec3 uBall;     // center of the ball
uniform float uSquash;  // squash on landing, 0..1
uniform float uOrbit;   // camera azimuth
uniform float uDrop;    // 0 before the drop, 1 after

float sdScene(vec3 p, out float id) {
  vec3 q = p - uBall;
  q.y /= 1.0 - 0.35 * uSquash;
  q.xz /= 1.0 + 0.18 * uSquash;
  float ball = length(q) - 0.7, ground = p.y;
  id = ball < ground ? 1.0 : 0.0;
  return min(ball, ground);
}
float sd(vec3 p) { float id; return sdScene(p, id); }

vec3 normalAt(vec3 p) {
  vec2 e = vec2(0.001, 0.0);
  return normalize(vec3(sd(p + e.xyy) - sd(p - e.xyy), sd(p + e.yxy) - sd(p - e.yxy), sd(p + e.yyx) - sd(p - e.yyx)));
}

float shadow(vec3 p, vec3 l) {
  float k = 1.0, d = 0.03;
  for (int i = 0; i < 40 && d < 12.0; i++) {
    float h = sd(p + l * d);
    k = min(k, 10.0 * h / d);
    d += clamp(h, 0.02, 0.5);
    if (k < 0.001) break;
  }
  return clamp(k, 0.0, 1.0);
}

vec3 scene(vec2 uv, float t) {
  vec3 target = vec3(uBall.x * 0.5, 0.8, 0.0);
  vec3 eye = target + vec3(sin(uOrbit) * 7.0, 2.6 + 1.4 * uDrop, cos(uOrbit) * 7.0);
  vec3 w = normalize(target - eye), u = normalize(cross(w, vec3(0.0, 1.0, 0.0))), v = cross(u, w);
  vec3 rd = normalize(uv.x * u + uv.y * v + 1.4 * w);

  float d = 0.0, id = 0.0;
  bool hit = false;
  for (int i = 0; i < 120; i++) {
    float h = sdScene(eye + rd * d, id);
    if (h < 0.0008 * d) { hit = true; break; }
    d += h;
    if (d > 60.0) break;
  }
  if (!hit) return uBg;

  vec3 p = eye + rd * d, n = normalAt(p), l = normalize(vec3(-0.5, 0.9, 0.4));
  float diffuse = max(dot(n, l), 0.0) * shadow(p + n * 0.002, l);
  float tile = mod(floor(p.x) + floor(p.z), 2.0);
  vec3 albedo = id > 0.5 ? mix(uFg, uAcc, uDrop) : uMid * (0.35 + 0.3 * tile);
  vec3 c = albedo * (0.12 + 1.5 * diffuse);
  if (id > 0.5) c += 0.5 * pow(max(dot(reflect(rd, n), l), 0.0), 40.0) * uFg;
  return mix(c, uBg, 1.0 - exp(-0.0025 * d * d));
}
`;

/* The ball jumps from one spot to the next between two hits and lands exactly on a hit. */
const spot = (i) => [-2.4, 1.6, -0.8, 2.4, 0.0][i % 5];
function ball(t) {
  const i = count(hits, t), a = i ? hits[i - 1] : 0, b = i < hits.length ? hits[i] : a + 1;
  const u = clamp((t - a) / (b - a));
  return [spot(i) + (spot(i + 1) - spot(i)) * ease.inOut(u), 0.7 + 1.9 * 4 * u * (1 - u), 0];
}

shaderScene({
  frag: FRAG,
  uniforms: (t) => ({
    uBall: ball(t),
    uSquash: pulse(hits, t, 0.12),
    uOrbit: 0.35 * Math.sin(t * 0.6) + 0.9 * ease.out3(clamp((t - drop) / 1.5)),
    uDrop: clamp((t - drop) / 0.2),
  }),
});
