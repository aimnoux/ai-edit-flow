/* A whole world in one fragment shader, no geometry. The page is scenes/<slug>/index.html, the scene writes
     vec3 scene(vec2 uv, float t)     uv: y from -0.5 to 0.5, x by aspect; returns linear color
   and calls shaderScene({ frag, uniforms }). Size, fps and length come from #root data attributes, colors from
   style tokens as uBg, uFg, uAcc, uMid. uniforms(t) returns extra values for one moment: called per subframe, so
   anything that moves there gets motion blur. Always available in GLSL: uT, uRes.

   The renderer calls window.seek(t). Every frame is the mean of spp subframes spread over the shutter with Halton
   pixel jitter (smooth edges), accumulated in half float, then ACES and sRGB once. Query: ?cine turns subframes on (the
   renderer sets it), &spp=N, &shutter=F (frames), &draft for half size, ?play to watch in a browser, #t=2.5 to open a moment. */
import { clamp, halton } from "./motion.mjs";

const query = new URLSearchParams(location.search);
const VS = "#version 300 es\nin vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }";
const HEAD = `#version 300 es
precision highp float;
uniform vec2 uRes, uJit;
uniform float uT;
uniform vec3 uBg, uFg, uAcc, uMid;
out vec4 fragColor;
#line 1
`;
const MAIN = `
void main(){ fragColor = vec4(scene((gl_FragCoord.xy + uJit - 0.5 * uRes) / uRes.y, uT), 1.0); }`;
const OUT = `#version 300 es
precision highp float;
uniform sampler2D uA;
out vec4 fragColor;
vec3 aces(vec3 x){ return clamp(x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
vec3 srgb(vec3 c){ return mix(12.92 * c, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
float dither(vec2 p){ return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))) - 0.5; }
void main(){ vec3 c = srgb(aces(max(texelFetch(uA, ivec2(gl_FragCoord.xy), 0).rgb, 0.0))); fragColor = vec4(c + dither(gl_FragCoord.xy) / 255.0, 1.0); }`;

function token(name) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!value) throw new Error(`No token ${name} in lib/tokens.css`);
  const paint = document.createElement("canvas").getContext("2d");
  paint.fillStyle = value;
  paint.fillRect(0, 0, 1, 1);
  return [...paint.getImageData(0, 0, 1, 1).data].slice(0, 3).map((v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
}

export function shaderScene({ frag, uniforms = () => ({}), spp = 8, shutter = 1.5 }) {
  const root = document.getElementById("root"), { width, height, fps, duration } = root.dataset;
  const S = query.has("draft") ? 0.5 : 1, W = width * S, H = height * S;
  const N = +query.get("spp") || (query.has("cine") ? (query.has("draft") ? 2 : spp) : 1);
  const SHUTTER = (+query.get("shutter") || shutter) / +fps;
  const cv = document.getElementById("c");
  Object.assign(cv, { width: W, height: H });
  Object.assign(cv.style, { display: "block", width: width + "px", height: height + "px" });
  const gl = cv.getContext("webgl2", { preserveDrawingBuffer: true, antialias: false, alpha: false });
  if (!gl || !gl.getExtension("EXT_color_buffer_float")) throw new Error("WebGL2 with float render targets is required: this needs a video card");

  const program = (src) => {
    const p = gl.createProgram();
    for (const [type, text] of [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, src]]) {
      const s = gl.createShader(type);
      gl.shaderSource(s, text);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error("Shader: " + gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.bindAttribLocation(p, 0, "a");
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error("Shader: " + gl.getProgramInfoLog(p));
    return p;
  };
  const world = program(HEAD + frag + MAIN), output = program(OUT);
  const at = (name) => gl.getUniformLocation(world, name);
  const set = (name, v) => { const f = gl[`uniform${v.length || 1}fv`]; f.call(gl, at(name), v.length ? v : [v]); };

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const acc = gl.createTexture(), fbo = gl.createFramebuffer();
  gl.bindTexture(gl.TEXTURE_2D, acc);
  gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA16F, W, H);
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, acc, 0);
  gl.viewport(0, 0, W, H);
  gl.useProgram(world);
  set("uRes", [W, H]);
  for (const [name, css] of [["uBg", "--bg"], ["uFg", "--fg"], ["uAcc", "--acc"], ["uMid", "--mid"]]) set(name, token(css));
  const C = window.__cine = { gl, range: [0, +duration], last: null, spp: N };

  window.seek = (t) => {
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(world);
    gl.enable(gl.BLEND);
    gl.blendColor(0, 0, 0, 1 / N);
    gl.blendFunc(gl.CONSTANT_ALPHA, gl.ONE);
    for (let s = 0; s < N; s++) {
      const tt = clamp(t + ((s + 0.5) / N - 0.5) * SHUTTER, 0, +duration);
      set("uT", tt);
      set("uJit", N > 1 ? [halton(s + 1, 2) - 0.5, halton(s + 1, 3) - 0.5] : [0, 0]);
      for (const [name, v] of Object.entries(uniforms(tt))) set(name, v);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    gl.disable(gl.BLEND);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.useProgram(output);
    gl.bindTexture(gl.TEXTURE_2D, acc);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    C.last = { t };
  };
  const moment = location.hash.match(/t=([\d.]+)/);
  window.seek(moment ? +moment[1] : 0);
  if (query.has("play")) requestAnimationFrame(function loop(ms) { window.seek((ms / 1000) % +duration); requestAnimationFrame(loop); });
  window.ready = true;
}
