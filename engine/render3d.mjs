#!/usr/bin/env node
/* Render of 3D and shader scenes on the video card. HyperFrames is for flat compositions: on heavy WebGL it mixes up
   frames and times out. This script seeks the page frame by frame and takes a screenshot of each, so the flat text of a
   mixed frame stays in the picture. Frames are kept in engine/build/frames3d/<name>/, a failed run continues.

     node engine/render3d.mjs <composition id or page> [options]
     node engine/render3d.mjs sketch-s1-yt                                 # three.js composition, final quality
     node engine/render3d.mjs scenes/shader-example/index.html --draft     # shader page, half size, fewer subframes
     node engine/render3d.mjs --doctor                                     # what WebGL this machine gives the browser

     --draft             half size, 4 subframes for 3D, 2 for shaders; output <name>-draft.mp4
     --from=S --to=S     redraw only this stretch; the other frames stay. If frames are still missing the file holds
                         only this stretch (<name>-<from>-<to>.mp4), otherwise the whole video is assembled.
     --still=S[,S]       single PNG frames, no video (a frame before spending a render)
     --spp=N             subframes per frame; 1 means none
     --audio=FILE        put this sound under the video (a music track, a voice wav)
     --out=FILE          output path; default engine/renders/<project>/<name>-video.mp4
     --timeout=S         one frame may take this long before the browser restarts (default 180)
     --allow-software    accept a software renderer instead of a video card: very slow, for a test only

   Pages declare size, fps and length in #root data attributes and set window.ready; three.js scenes run through the
   timeline (TL), shader pages through window.seek(t). Run in the foreground, outside any sandbox that hides the GPU. */
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { basename, dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".svg": "image/svg+xml", ".hdr": "application/octet-stream", ".glb": "model/gltf-binary", ".mp4": "video/mp4", ".webm": "video/webm" };

export function parseArgs(argv) {
  const opt = {};
  for (const a of argv) {
    if (!a.startsWith("--")) { opt.target = a; continue; }
    const [k, v] = a.slice(2).split("=");
    opt[k] = v ?? true;
  }
  return opt;
}

/** A composition id or a path to a page under engine/ -> file, address, name and project of the outputs. */
export function locate(target, cwd = process.cwd(), here = HERE) {
  const candidates = [resolve(here, `${target}.html`), resolve(cwd, target), resolve(here, target)];
  let file = candidates.find((p) => existsSync(p));
  if (file && statSync(file).isDirectory()) file = join(file, "index.html");
  if (!file || !existsSync(file)) throw new Error(`No composition or page: ${target}`);
  const path = relative(here, file);
  if (path.startsWith("..")) throw new Error(`The page must be inside engine/: ${file}`);
  const page = basename(file) === "index.html";
  const name = page ? basename(dirname(file)) : basename(file, ".html");
  return { file, path: path.split(sep).join("/"), name, project: page ? name : name.replace(/-(?:s|ch)\d+(?:-\w+)?$/, "") };
}

/** Size, fps and length from the #root data attributes of a page. */
export function pageSpec(html) {
  const root = html.match(/<[^>]*id="root"[^>]*>/)?.[0] ?? "";
  const num = (k) => +(root.match(new RegExp(`data-${k}="([\\d.]+)"`))?.[1] ?? NaN);
  const spec = { width: num("width"), height: num("height"), fps: num("fps"), duration: num("duration") };
  if (Object.values(spec).some(Number.isNaN)) throw new Error('The page needs #root with data-width, data-height, data-fps and data-duration');
  return spec;
}

/** Frames this run draws: [first, last) out of a total, from --from/--to in seconds. */
export function frameRange(opt, fps, duration) {
  const total = Math.round(duration * fps);
  const first = opt.from != null ? Math.max(0, Math.round(+opt.from * fps)) : 0;
  const last = opt.to != null ? Math.min(total, Math.round(+opt.to * fps)) : total;
  if (!(first < last)) throw new Error(`Empty stretch: --from=${opt.from} --to=${opt.to} of ${duration} s`);
  return { total, first, last };
}

/** Why this browser cannot render, or null. `info` comes from probe() in the page. */
export function gpuProblem(info, allowSoftware = false) {
  const where = "3D and shader renders need a video card and WebGL2. Run outside a sandbox, VM or remote session; " +
    "macOS is the tested platform, Windows and Linux are not verified.";
  if (!info.webgl2) return `No WebGL2 in the rendering browser. ${where}`;
  if (!info.floatTargets) return `WebGL2 has no float render targets (${info.renderer}). ${where}`;
  if (!allowSoftware && /swiftshader|llvmpipe|software|microsoft basic/i.test(info.renderer)) {
    return `No video card: the browser fell back to the software renderer ${info.renderer}. ${where} --allow-software renders anyway, very slowly.`;
  }
  return null;
}

const probe = () => {
  const gl = document.createElement("canvas").getContext("webgl2");
  if (!gl) return { webgl2: false };
  const debug = gl.getExtension("WEBGL_debug_renderer_info");
  return { webgl2: true, renderer: gl.getParameter(debug ? debug.UNMASKED_RENDERER_WEBGL : gl.RENDERER), floatTargets: !!gl.getExtension("EXT_color_buffer_float") };
};

function browserPath() {
  const r = spawnSync(process.execPath, [join(HERE, "hf.mjs"), "browser", "path"], { encoding: "utf8", windowsHide: true });
  if (r.status !== 0) throw new Error((r.stderr || "Dedicated browser lookup failed; run bash setup.sh").trim());
  return r.stdout.trim();
}

function serve() {
  const server = createServer((req, res) => {
    const file = resolve(HERE, "." + decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!file.startsWith(HERE + sep) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "content-type": MIME[extname(file).toLowerCase()] || "application/octet-stream", "cache-control": "no-store" });
    res.end(readFileSync(file));
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

const GPU = ["--no-first-run", "--no-default-browser-check", "--disable-breakpad", "--disable-crash-reporter", "--enable-webgl", "--use-gl=angle",
  ...(process.platform === "darwin" ? ["--use-angle=metal"] : []), "--enable-gpu-rasterization", "--ignore-gpu-blocklist", "--disable-gpu-watchdog",
  "--disable-gpu-vsync", "--disable-frame-rate-limit", "--disable-background-timer-throttling", "--disable-renderer-backgrounding"];

async function launch(extra = []) {
  const { default: puppeteer } = await import("puppeteer-core");
  // Without userDataDir Puppeteer makes a temporary profile and removes it on close.
  const browser = await puppeteer.launch({ executablePath: browserPath(), headless: true, protocolTimeout: 3600_000, args: [...GPU, ...extra] }).catch((error) => {
    throw new Error(`The rendering browser did not start. Inside an agent sandbox run this command outside it.\n${error.message.split("\n").slice(0, 6).join("\n")}`);
  });
  const pid = browser.process()?.pid;
  if (pid && process.platform !== "win32") {   // a killed node must not leave a GPU browser behind
    const python = [process.env.VIRTUAL_ENV && join(process.env.VIRTUAL_ENV, "bin/python3"), join(ROOT, ".venv/bin/python3"), "python3", "python"]
      .find((p) => p && (!p.includes(sep) || existsSync(p)));
    const guard = spawn(python, [join(HERE, "process_guard.py"), String(pid)], { detached: true, stdio: ["pipe", "ignore", "ignore"] });
    guard.on("error", () => {});
    guard.stdin.on("error", () => {});
    guard.unref();
    guard.stdin.unref?.();
    browser.once("disconnected", () => guard.stdin.end());
  }
  return browser;
}

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));
const within = (promise, ms, what) => Promise.race([promise, new Promise((_, no) => setTimeout(() => no(new Error(`hung: ${what}`)), ms).unref())]);

async function open(url, spec, scale, extra, allowSoftware) {
  const browser = await launch(extra);
  try {
    const page = await browser.newPage();
    const problem = gpuProblem(await page.evaluate(probe), allowSoftware);
    if (problem) throw new Error(problem);
    page.sceneErrors = [];
    page.on("pageerror", (e) => page.sceneErrors.push(String(e.message || e)));
    page.on("requestfailed", (r) => { if (!r.url().endsWith("/favicon.ico")) page.sceneErrors.push(`resource ${r.url()}: ${r.failure()?.errorText}`); });
    page.on("response", (r) => { if (r.status() >= 400 && !r.url().endsWith("/favicon.ico")) page.sceneErrors.push(`HTTP ${r.status()}: ${r.url()}`); });
    await page.setViewport({ width: spec.width, height: spec.height, deviceScaleFactor: scale });
    await page.goto(url, { waitUntil: "load" });
    const deadline = Date.now() + 300_000;
    for (;;) {
      if (page.sceneErrors.length) throw new Error(page.sceneErrors.join("; "));
      if (await page.evaluate("!!window.ready && !(window.__pending > 0) && document.fonts.status === 'loaded'")) break;
      if (Date.now() > deadline) throw new Error("The scene never became ready: a three.js scene must call drive(), a shader page shaderScene()");
      await sleep(100);
    }
    return { browser, page };
  } catch (error) { await browser.close(); throw error; }
}

/** Draw moment t. readPixels waits for the video card; gl.finish does not on ANGLE. */
const drawn = (t) => `(() => { if (window.seek) window.seek(${t}); else TL.seek(${t}, false);
  const C = window.__cine; if (!C) return null;
  C.gl.readPixels(0, 0, 1, 1, C.gl.RGBA, C.gl.UNSIGNED_BYTE, new Uint8Array(4));
  return { t: C.last && C.last.t, range: C.range }; })()`;

async function capture(page, spec, t, frameMs, format, what) {
  const fail = () => { if (page.sceneErrors.length) throw new Error(page.sceneErrors.join("; ")); };
  fail();
  const last = await within(page.evaluate(drawn(t)), frameMs, `${what} draw`);
  // The picture must belong to this moment, not stay from the previous seek.
  if (last && t >= last.range[0] && t <= last.range[1] && Math.abs(last.t - t) > 1e-4) throw new Error(`${what}: drew moment ${last.t}, expected ${t}`);
  fail();
  const shot = await within(page.screenshot({ type: format, ...(format === "jpeg" ? { quality: 95 } : {}), clip: { x: 0, y: 0, width: spec.width, height: spec.height } }), frameMs, `${what} screenshot`);
  fail();
  return shot;
}

function hashTree(hash, path) {
  if (!existsSync(path)) return;
  if (statSync(path).isDirectory()) {
    for (const name of readdirSync(path).sort()) if (name !== "vendor") hashTree(hash, join(path, name));
  } else hash.update(relative(HERE, path)).update(readFileSync(path));
}

/** Frames stay valid while the page, its scene folder, the libraries and the settings stay the same. */
function fingerprint(where, settings) {
  const hash = createHash("sha256").update(JSON.stringify(settings));
  hash.update(readFileSync(where.file));
  hashTree(hash, join(HERE, "lib"));
  hashTree(hash, join(HERE, "scenes", where.project));
  return hash.digest("hex");
}

/** ffmpeg arguments: frames first..first+count of a folder, optionally with sound from the same moment. */
export function encodeArgs(dir, fps, first, count, out, audio) {
  const args = ["-v", "error", "-y", "-framerate", String(fps), "-start_number", String(first), "-i", join(dir, "f%05d.jpg")];
  if (audio) args.push("-ss", String(first / fps), "-i", audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-shortest");
  return [...args, "-frames:v", String(count), "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out];
}

function assemble(...job) {
  mkdirSync(dirname(job[4]), { recursive: true });
  const r = spawnSync("ffmpeg", encodeArgs(...job), { stdio: "inherit" });
  if (r.error) throw r.error;
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${r.signal || r.status}`);
}

async function main() {
  const opt = parseArgs(process.argv.slice(2));
  const extra = opt["allow-software"] ? ["--enable-unsafe-swiftshader"] : [];
  if (opt.doctor) {
    const browser = await launch(extra);
    const info = await (await browser.newPage()).evaluate(probe);
    await browser.close();
    const problem = gpuProblem(info, !!opt["allow-software"]);
    console.log(JSON.stringify(info));
    if (problem) throw new Error(problem);
    return;
  }
  if (!opt.target) { console.log(readFileSync(fileURLToPath(import.meta.url), "utf8").split("*/")[0].replace("#!/usr/bin/env node\n/* ", "")); process.exit(1); }

  const where = locate(opt.target);
  const spec = pageSpec(readFileSync(where.file, "utf8"));
  const fps = spec.fps, draft = !!opt.draft, scale = draft ? 0.5 : 1, frameMs = +(opt.timeout || 180) * 1000;
  const tag = where.name + (draft ? "-draft" : "") + (opt.spp ? `-spp${opt.spp}` : "");
  const dir = join(HERE, "build/frames3d", tag);
  mkdirSync(dir, { recursive: true });
  const server = await serve();
  const url = `http://127.0.0.1:${server.address().port}/${where.path}?cine${draft ? "&draft" : ""}${opt.spp ? `&spp=${opt.spp}` : ""}`;
  const reopen = () => open(url, spec, scale, extra, !!opt["allow-software"]);
  const started = Date.now();
  let session;
  try {
    session = await reopen();
    if (opt.still) {
      for (const s of String(opt.still).split(",").map(Number)) {
        await session.page.evaluate(drawn(s + 1 / fps));   // a timeline already at this moment would not redraw
        const file = join(dir, `still-${s.toFixed(3)}.png`);
        writeFileSync(file, await capture(session.page, spec, s, frameMs, "png", `${s} s`));
        console.log(file);
      }
      return;
    }

    const { total, first, last } = frameRange(opt, fps, spec.duration);
    const frame = (f) => join(dir, `f${String(f).padStart(5, "0")}.jpg`);
    const frames = () => readdirSync(dir).filter((x) => /^f\d+\.jpg$/.test(x));
    const stamp = join(dir, ".fingerprint"), print = fingerprint(where, { ...spec, draft, spp: opt.spp ?? null });
    const stretch = opt.from != null || opt.to != null;
    if (stretch) {
      for (let f = first; f < last; f++) rmSync(frame(f), { force: true });
      if (!existsSync(stamp)) writeFileSync(stamp, print);
    } else {
      if ((existsSync(stamp) ? readFileSync(stamp, "utf8") : "") !== print && frames().length) {
        console.log("the scene changed: old frames removed (--from keeps them and redraws a stretch)");
        frames().forEach((x) => rmSync(join(dir, x)));
      }
      writeFileSync(stamp, print);
    }
    frames().filter((x) => +x.slice(1, 6) >= total).forEach((x) => rmSync(join(dir, x)));   // a longer version left a tail

    const info = await session.page.evaluate("window.__cine ? window.__cine.spp : 1");
    console.log(`${where.name}: frames ${first}-${last - 1} of ${total}, ${spec.width * scale}x${spec.height * scale}, ${fps} fps, ${info} subframes`);
    let fresh = true, restarts = 0, drew = 0;
    for (let f = first; f < last; f++) {
      if (existsSync(frame(f))) continue;
      const t = f / fps, t0 = Date.now();
      try {
        // First frame of a run: the timeline may already stand here and a seek would not redraw. Never return TL through
        // evaluate: it serializes without end.
        if (fresh) { await within(session.page.evaluate(`void (${drawn((f + 1) / fps)})`), frameMs, `f${f} seek`); fresh = false; }
        writeFileSync(frame(f), await capture(session.page, spec, t, frameMs, "jpeg", `f${f}`));
        drew++;
      } catch (error) {
        if (!error.message.startsWith("hung") || ++restarts > 5) throw error;
        console.log(`${error.message} after ${((Date.now() - t0) / 1000).toFixed(0)} s, restarting the browser (${restarts})`);
        session.browser.process()?.kill("SIGKILL");
        session = await reopen();
        fresh = true;
        f--;
        continue;
      }
      if (drew % 25 === 1) console.log(`f${f} ${t.toFixed(2)} s: ${((Date.now() - t0) / 1000).toFixed(2)} s per frame`);
    }
    const seconds = (Date.now() - started) / 1000;
    console.log(`${drew} frames in ${seconds.toFixed(1)} s${drew ? `, ${(seconds / drew).toFixed(2)} s per frame` : ""}`);

    const whole = Array.from({ length: total }, (_, f) => f).every((f) => existsSync(frame(f)));
    const a = whole ? 0 : first, n = whole ? total : last - first;
    const base = join(HERE, "renders", where.project, where.name);
    const out = opt.out ? resolve(opt.out) : whole ? `${base}-${draft ? "draft" : "video"}.mp4` : `${base}-${(first / fps).toFixed(2)}-${(last / fps).toFixed(2)}${draft ? "-draft" : ""}.mp4`;
    assemble(dir, fps, a, n, out, opt.audio && resolve(opt.audio));
    console.log(out);
  } finally {
    await session?.browser.close().catch(() => {});
    server.closeAllConnections?.();
    server.close();
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => { console.error(error.message); process.exit(1); });
}
