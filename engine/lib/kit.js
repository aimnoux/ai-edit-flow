/* The editing kit: timing by the words of the voice, scenes, typography, emphasis, lists, chapter title,
   sound cues. Global names used by scenes/<project>/*.js. Everything is deterministic: no random, no Date.
   Looks come from CSS variables in lib/tokens.css (copied from style/tokens.css); nothing here picks a color. */

const TL = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });
const TM = window.TIMING;
const D = TM.dur;
const FPS = TM.fps || 25;
const CHAPTER = TM.chapter || { num: "1", title: "", index: 1, count: 1 };
/* Motion tokens: entries are short, the frame stands still by default, a big transition and a sound belong
   to the main action only. Enter: UI 0.3 s, a large object 0.5 s. Exit shorter than enter, but not a click. */
const EASE = { enter: "expo.out", exit: "power3.in", move: "power3.inOut", drift: "sine.inOut", sheen: "power2.inOut", settle: "power2.out",
  camQuick: "power2.inOut", camMain: "sine.inOut", soft: "power3.out" };
const DUR = { micro: 0.3, base: 0.45, enter: 0.6, slow: 1.2, exit: 0.4 };
const NS = "http://www.w3.org/2000/svg";
const CUES = [];
const SCENES = [];   // [start, end] of every scene, for review.py
const STAGE = document.getElementById("stage");
const HUD = document.getElementById("hud");
const hash = (i, k) => { const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453; return x - Math.floor(x); };

function el(tag, cls, parent, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  if (parent) parent.appendChild(e);
  return e;
}
function svg(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const a in attrs) e.setAttribute(a, attrs[a]);
  if (parent) parent.appendChild(e);
  return e;
}
function at(e, x, y, w, h) {
  Object.assign(e.style, { position: "absolute", left: x + "px", top: y + "px" });
  if (w != null) e.style.width = w + "px";
  if (h != null) e.style.height = h + "px";
  return e;
}
/** A sound cue for the mix: name from style/sound/, time, volume 0..1, len = cut the sound to len seconds. */
function sfx(name, t, vol = 1, len = 0) { if (t >= 0 && t < D) CUES.push({ name, t: +t.toFixed(3), vol, ...(len ? { len } : {}) }); }

/* ---------- Time by the voice ----------
   Blocks are the script's `### N.M`; words carry start/end seconds relative to this composition. */
function norm(s) { return s.toLowerCase().replace(/[^\p{L}\p{N}+#/-]/gu, ""); }
function paras(id) { const p = TM.blocks[id]; if (!p) throw new Error("no block " + id); return p; }
/** Start and end of a block. */
function B(id) { const p = paras(id); return { s: p[0].s, e: p[p.length - 1].e }; }
/** Paragraph k of a block. */
function P(id, k) { return paras(id)[k]; }
function words(id) { return paras(id).flatMap((p) => p.words); }
/** The second a phrase starts in a block (words compared by prefix, so endings don't matter); nth = which occurrence. */
function W(id, phrase, nth = 0, end = false) {
  const ws = words(id);
  const toks = phrase.split(/\s+/).map(norm).filter(Boolean);
  let found = 0;
  for (let i = 0; i + toks.length <= ws.length; i++) {
    if (toks.every((t, j) => ws[i + j].n.startsWith(t) || (ws[i + j].n.length >= 3 && t.startsWith(ws[i + j].n)))) {
      if (found++ === nth) return end ? ws[i + toks.length - 1].e : ws[i].s;
    }
  }
  // live speech drifts from the script: position of the phrase in the paragraph text -> share of its duration
  const t = est(id, toks, nth, end);
  if (t != null) return t;
  if (toks.length > 1) return W(id, toks[0], nth, end);
  throw new Error(`phrase "${phrase}" not found in ${id}`);
}
/** Estimate from the script text: the phrase is in the paragraph, time is proportional to its place among the words.
    Every estimate is logged to window.EST so it can be checked. */
function est(id, toks, nth = 0, end = false) {
  let found = 0;
  for (const p of paras(id)) {
    if (!p.text) return null;
    const tw = p.text.split(/\s+/).map(norm).filter(Boolean);
    for (let i = 0; i + toks.length <= tw.length; i++) {
      if (toks.every((t, j) => tw[i + j].startsWith(t) || (tw[i + j].length >= 3 && t.startsWith(tw[i + j])))) {
        if (found++ !== nth) continue;
        const k = end ? i + toks.length : i;
        const t = p.s + (k / tw.length) * (p.e - p.s);
        (window.EST = window.EST || []).push(`${id} "${toks.join(" ")}" ~ ${t.toFixed(1)}`);
        return t;
      }
    }
  }
  return null;
}
/** The second a phrase ends. */
const WE = (id, phrase, nth = 0) => W(id, phrase, nth, true);
/** A trigger word of the script ([word]) in a block. */
function TR(id, w, nth = 0) {
  const all = paras(id).flatMap((p) => p.triggers).filter((x) => x.w === w);
  if (!all[nth]) {
    const t = est(id, w.split(/\s+/).map(norm).filter(Boolean), nth);
    if (t != null) return t;
    throw new Error(`trigger "${w}" not found in ${id}`);
  }
  return all[nth].t;
}

/* ---------- Scenes ---------- */
/** A scene from s to e seconds. opt.enter: fade | zoom | punch | rise | cut; opt.exit: fade | up | cut; opt.z, opt.cls, opt.parent. */
function scene(s, e, opt = {}) {
  const sc = el("section", "scene " + (opt.cls || ""), opt.parent || STAGE);
  SCENES.push([+s.toFixed(3), +e.toFixed(3)]);
  sc._s = s; sc._e = e;
  if (opt.z) sc.style.zIndex = opt.z;
  TL.set(sc, { display: "block" }, s);
  TL.set(sc, { display: "none" }, e);
  const enter = opt.enter || "fade";
  if (enter === "fade") TL.fromTo(sc, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: EASE.settle }, s);
  else if (enter === "zoom") TL.fromTo(sc, { opacity: 0, scale: 1.03 }, { opacity: 1, scale: 1, duration: 0.45, ease: EASE.enter }, s);
  else if (enter === "punch") TL.fromTo(sc, { opacity: 0 }, { opacity: 1, duration: 0.15, ease: EASE.settle }, s);
  else if (enter === "rise") TL.fromTo(sc, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: EASE.enter }, s);
  const exit = opt.exit || "fade";
  sc._exit = exit;
  if (exit === "fade") TL.to(sc, { opacity: 0, duration: DUR.exit, ease: EASE.exit }, e - DUR.exit);
  else if (exit === "up") TL.to(sc, { opacity: 0, y: -40, duration: DUR.exit, ease: EASE.exit }, e - DUR.exit);
  return sc;
}
/** A plain cut: no fade in or out. */
function cut(s, e, opt = {}) { return scene(s, e, Object.assign({ enter: "cut", exit: "cut" }, opt)); }

/* ---------- Typography ----------
   rich(parent, "There is a [chemist] and a [physicist]") - every word in its own mask, [word] is an accent. */
function rich(parent, text, cls = "", style = {}) {
  const box = el("div", cls, parent);
  Object.assign(box.style, style);
  const out = { box, words: [], acc: [] };
  text.split("\n").forEach((ln, li) => {
    const row = el("div", "", box);
    const re = /\[([^\]]+)\]|(\S+)/g;
    let m;
    while ((m = re.exec(ln))) {
      const accent = !!m[1];
      const wrap = el("span", "line w", row);
      wrap.setAttribute("data-layout-allow-overflow", "");   // the mask hides the word on purpose: not a layout bug
      wrap.style.marginRight = "0.26em";
      const inn = el("span", "in" + (accent ? " acc-text" : ""), wrap, (m[1] || m[2]).replace(/_/g, " "));
      out.words.push(inn);
      if (accent) out.acc.push(wrap);
      wrap.dataset.row = li;
    }
  });
  return out;
}
/** A line rises from under its mask. The whole line at once; a cascade only by opt.stagger (lists). */
function reveal(ins, t, opt = {}) {
  const list = Array.isArray(ins) ? ins : [ins];
  TL.fromTo(list, { yPercent: 115 }, { yPercent: 0, duration: opt.dur || DUR.base, ease: EASE.enter, stagger: opt.stagger ?? 0 }, t);
  if (opt.sfx) sfx(opt.sfx, t, opt.vol || 0.8);   // sound only when asked: a tick on every line is a sign of slop
}
function hideUp(ins, t, opt = {}) {
  const list = Array.isArray(ins) ? ins : [ins];
  TL.to(list, { yPercent: -115, duration: opt.dur || DUR.exit, ease: EASE.exit, stagger: opt.stagger ?? 0 }, t);
}
/** Word by word in sync with the voice: each word of the text comes up when it is spoken.
    Words are matched to speech by their first 4 letters; skipped words in speech are fine. */
function follow(r, id, phrase, opt = {}) {
  const ws = words(id);
  const start = W(id, phrase, opt.nth || 0);
  let cur = ws.findIndex((w) => w.s === start);
  let last = start;
  r.words.forEach((inn) => {
    const key = norm(inn.textContent).slice(0, 4);
    let t = last;
    if (key) {
      for (let j = cur; j < Math.min(ws.length, cur + 6); j++) {
        if (ws[j].n.startsWith(key) || key.startsWith(ws[j].n.slice(0, 4))) { t = ws[j].s; cur = j + 1; break; }
      }
    }
    last = t;
    TL.fromTo(inn, { yPercent: 115 }, { yPercent: 0, duration: 0.4, ease: EASE.enter }, t - 0.04);
  });
}

/* ---------- Emphasis: one thing lit at a time ----------
   glow() puts the style's --glow (filter) or --glow-box (box-shadow) on a target and takes it off the previous one.
   A style without glow (`--glow: none`) gets a brightness lift instead. */
const CSSV = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const GLOW_ON = CSSV("--glow"), BOX_ON = CSSV("--glow-box");
const zeroFilter = (v) => v.replace(/drop-shadow\([^)]*\)/g, "drop-shadow(0px 0px 0px rgba(0,0,0,0))");
const zeroBox = (v) => v.split(/,(?![^(]*\))/).map(() => "0 0 0px rgba(0,0,0,0)").join(", ");
const GLOW_OFF = GLOW_ON && GLOW_ON !== "none" ? zeroFilter(GLOW_ON) : "brightness(1)";
const BOX_OFF = BOX_ON && BOX_ON !== "none" ? zeroBox(BOX_ON) : "none";
let LAST_GLOW = null;
function glow(target, t, opt = {}) {
  if (LAST_GLOW && LAST_GLOW.el !== target && LAST_GLOW.t < t) unglow(LAST_GLOW.el, t, LAST_GLOW.mode);
  const mode = opt.box ? "box" : "halo";
  if (mode === "box" && BOX_OFF !== "none") TL.fromTo(target, { boxShadow: BOX_OFF }, { boxShadow: BOX_ON, duration: 0.4, ease: EASE.settle, immediateRender: false }, t);
  else if (mode === "halo" && GLOW_ON && GLOW_ON !== "none") TL.fromTo(target, { filter: GLOW_OFF }, { filter: GLOW_ON, duration: 0.4, ease: EASE.settle, immediateRender: false }, t);
  else TL.fromTo(target, { filter: "brightness(1)" }, { filter: "brightness(1.3)", duration: 0.3, ease: EASE.settle, immediateRender: false }, t);
  if (opt.sfx) sfx(opt.sfx, t, opt.vol || 0.8);
  LAST_GLOW = { el: target, t, mode };
}
function unglow(target, t, mode) {
  if (mode === "box" && BOX_OFF !== "none") TL.to(target, { boxShadow: BOX_OFF, duration: 0.35 }, t);
  else if (mode === "halo" && GLOW_ON && GLOW_ON !== "none") TL.to(target, { filter: GLOW_OFF, duration: 0.35 }, t);
  else TL.to(target, { filter: "brightness(1)", duration: 0.25 }, t);
  if (LAST_GLOW && LAST_GLOW.el === target) LAST_GLOW = null;
}
/** Accent words of rich() light up at their times. */
function accents(r, times, opt = {}) {
  r.acc.forEach((w, k) => { if (times[k] != null) glow(w, times[k], { sfx: opt.sfx, vol: 0.6 }); });
}

/* ---------- Lists ---------- */
/** A numbered list; item i rises at times[i], the previous item dims. */
function list(parent, items, times, opt = {}) {
  const box = el("div", "list", parent);
  Object.assign(box.style, { position: "absolute", left: (opt.x ?? 1040) + "px", top: (opt.y ?? 250) + "px", width: (opt.w ?? 760) + "px" });
  const rows = [];
  items.forEach((it, i) => {
    const r = el("div", "item", box);
    const k = el("span", "line", r); el("span", "in k", k, String(i + 1).padStart(2, "0"));
    const v = el("span", "line", r); const vi = el("span", "in v", v, it);
    k.setAttribute("data-layout-allow-overflow", ""); v.setAttribute("data-layout-allow-overflow", "");
    if (opt.size) vi.style.fontSize = opt.size + "px";
    TL.fromTo([k.firstChild, vi], { yPercent: 115 }, { yPercent: 0, duration: DUR.base, ease: EASE.enter, stagger: 0.04 }, times[i]);
    TL.to(vi, { color: CSSV("--fg"), duration: 0.3 }, times[i]);
    if (i) TL.to(rows[i - 1].vi, { color: CSSV("--text-2"), duration: 0.3 }, times[i]);
    rows.push({ r, vi, v });
  });
  return { box, rows };
}

/* ---------- Chapter title and progress ---------- */
/** A chapter title card from s to e: a small label (number), the name, a sub line. Defaults come from CHAPTER. */
function chapterTitle(s, e, name = CHAPTER.title, sub = "", label = String(CHAPTER.index).padStart(2, "0")) {
  const sc = scene(s, e, { cls: "ctitle", enter: "cut", exit: "fade" });
  const eb = el("div", "eyebrow", sc);
  const e2 = el("span", "mono", eb, label);
  const h = el("h1", "hero", sc);
  const l = el("span", "line", h); const inn = el("span", "in", l, name);
  const sb = el("p", "sub line", sc); const si = el("span", "in", sb, sub);
  l.setAttribute("data-layout-allow-overflow", ""); sb.setAttribute("data-layout-allow-overflow", "");
  TL.from(e2, { opacity: 0, duration: DUR.base, ease: EASE.settle }, s + 0.1);
  TL.fromTo(inn, { yPercent: 115 }, { yPercent: 0, duration: DUR.enter, ease: EASE.enter }, s + 0.2);
  TL.fromTo(si, { yPercent: 115 }, { yPercent: 0, duration: DUR.base, ease: EASE.enter }, s + 0.5);
  return sc;
}
/** Progress of the video on the HUD: `count` segments, segment `idx` fills from s to e. */
function progress(s, e, idx = CHAPTER.index, count = CHAPTER.count) {
  const bar = el("div", "hud-prog", HUD);
  const segs = [...Array(count)].map(() => { const it = el("i", "", bar); return el("b", "", it); });
  segs.forEach((b, i) => gsap.set(b, { scaleX: i < idx - 1 ? 1 : 0, opacity: i < idx - 1 ? 0.55 : 1 }));
  TL.set(bar, { opacity: 0 }, 0);
  TL.to(bar, { opacity: 1, duration: 0.6 }, s);
  TL.fromTo(segs[idx - 1], { scaleX: 0 }, { scaleX: 1, duration: e - s, ease: "none" }, s);
  TL.to(bar, { opacity: 0, duration: 0.4 }, e);
  return bar;
}

/* ---------- Appearances inside a thing: not everything fades in ----------
   Like in a product: a status lands as a stamp, a number opens with a wipe, a caption rises from its line mask. */
/** A stamp: lands at once with a small scale settle, no fade. */
function stampIn(node, t, opt = {}) {
  gsap.set(node, { opacity: 0 });
  TL.set(node, { opacity: 1 }, t);
  TL.fromTo(node, { scale: opt.from ?? 1.1 }, { scale: 1, duration: opt.dur ?? 0.3, ease: EASE.soft, transformOrigin: opt.origin || "50% 50%", immediateRender: false }, t);
}
/** A wipe from left to right (clip-path). */
function wipe(node, t, opt = {}) {
  gsap.set(node, { opacity: 1, clipPath: "inset(0% 100% 0% 0%)" });
  TL.fromTo(node, { clipPath: "inset(0% 100% 0% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: opt.dur ?? 0.5, ease: EASE.settle, immediateRender: false }, t);
}
/** A caption rising from under its line mask. The node's content moves into an inner span; a node whose
    textContent is later changed through TL.set is not for this (use stampIn). */
function lineIn(node, t, opt = {}) {
  let inn = node._lineIn;
  if (!inn) {
    inn = document.createElement("span");
    inn.style.display = "inline-block";
    while (node.firstChild) inn.appendChild(node.firstChild);
    node.appendChild(inn);
    Object.assign(node.style, { overflow: "hidden", paddingBottom: "0.12em", marginBottom: "-0.12em" });
    node.setAttribute("data-layout-allow-overflow", "");
    node._lineIn = inn;
  }
  gsap.set(node, { opacity: 1 });
  TL.fromTo(inn, { yPercent: 115 }, { yPercent: 0, duration: opt.dur ?? 0.55, ease: EASE.soft }, t);
}
/** Text typed letter by letter from t0 to t1 (prepared states, no callbacks: frames render out of order). */
function typeText(node, text, t0, t1, steps, opt = {}) {
  if (opt.stream) return streamText(node, text, t0, t1, opt);
  const n = Math.max(2, steps || Math.min(48, Math.ceil(text.length / 2)));
  TL.set(node, { textContent: "" }, Math.max(0, t0 - 0.01));
  if (opt.sound) sfx(opt.sound, t0, 0.45, t1 - t0 + 0.1);
  for (let k = 1; k <= n; k++) TL.set(node, { textContent: text.slice(0, Math.round((text.length * k) / n)) }, t0 + ((t1 - t0) * k) / n);
}
/** Text arriving as a stream, like an AI answer: the whole text is laid out at once as invisible words so lines
    never jump; words arrive in bursts with the rhythm of a real answer, each one lands grey and fills with color
    in 0.27 s; opt.caret is a class for the cursor after the last word. */
const STREAM_GAPS = [0.167, 0.1, 0, 0.367, 0, 0.167, 0.133, 0.1, 0.1, 0.133, 0.167, 0.133, 0, 0.233, 0.167, 0.1, 0, 0.133,
  0.133, 0.1, 0.167, 0.133, 0.1, 0.133, 0.167, 0.1, 0.133, 0.1, 0.133];
function streamText(node, text, t0, t1, opt = {}) {
  const ws0 = text.split(/(?<=\s)/);
  node.innerHTML = ws0.map((w) => `<span class="iw">${w.replace(/ /g, "&nbsp;").replace(/&nbsp;$/, " ")}</span>` +
    (opt.caret ? `<span class="tt-caret"><i class="${opt.caret}"></i></span>` : "")).join("");
  const ink = getComputedStyle(node).color;
  const ws = [...node.querySelectorAll(".iw")], cs = [...node.querySelectorAll(".tt-caret i")];
  let acc = 0; const at_ = [0];
  for (let i = 1; i < ws.length; i++) at_.push((acc += STREAM_GAPS[i % STREAM_GAPS.length]));
  const k = acc > 0 ? Math.max(0.2, (t1 - t0 - 0.27) / acc) : 1;
  gsap.set(ws, { opacity: 0 }); if (cs.length) gsap.set(cs, { opacity: 0 });
  ws.forEach((w, i) => {
    const t = t0 + at_[i] * k;
    TL.set(w, { opacity: 1 }, t);
    TL.fromTo(w, { color: opt.fresh || CSSV("--text-2") || "#888" }, { color: ink, duration: 0.2667, ease: "none", immediateRender: false }, t);
    if (cs[i]) { TL.set(cs[i], { opacity: 1 }, t); if (i + 1 < ws.length) TL.set(cs[i], { opacity: 0 }, t0 + at_[i + 1] * k); }
  });
  if (cs.length) TL.set(cs[cs.length - 1], { opacity: 0 }, t1 + (opt.caretHold ?? 0.3));
  if (opt.sound) sfx(opt.sound, t0, 0.4);
}

/* ---------- Small things ---------- */
/** A number changing through prepared values (no callbacks). */
function countUp(node, from, to, t, dur, fmt = (v) => String(v), steps = 24) {
  node.style.fontVariantNumeric = "tabular-nums";   // digits of one width: the counter doesn't shiver
  for (let k = 0; k <= steps; k++) {
    const v = from + (to - from) * (1 - Math.pow(1 - k / steps, 3));
    TL.set(node, { textContent: fmt(Math.round(v)) }, t + (dur * k) / steps);
  }
}
/** Everything on stage and on the HUD fades out by t + d. */
function clearStage(t, d = 0.45) {
  const kids = [...STAGE.children].filter((n) => n.tagName === "SECTION");
  const hudKids = [...HUD.children].filter((n) => !n.matches(".hud-prog, .caps"));
  TL.to([...kids, ...hudKids], { opacity: 0, duration: d, ease: EASE.exit }, t);
}
/** Measure layout inside a hidden scene: the scene is visible for the measurement. */
function measure(sc, fn) {
  const prev = sc.style.display;
  sc.style.display = "block";
  const v = fn();
  sc.style.display = prev;
  return v;
}
/** Rectangle of node in host coordinates (without the host's camera scale). */
function measureIn(host, node) {
  const sec = node.closest ? node.closest(".scene") : null;
  const get = () => {
    const hr = host.getBoundingClientRect(), nr = node.getBoundingClientRect();
    const k = host.offsetWidth ? hr.width / host.offsetWidth : 1;
    return { x: (nr.left - hr.left) / k, y: (nr.top - hr.top) / k, w: nr.width / k, h: nr.height / k };
  };
  return sec ? measure(sec, get) : get();
}
/** Camera inside a scene: move the scene so that point (px, py) of it sits at (cx, cy) of the frame at `scale`. */
function camTo(sc, t, scale, px, py, cx, cy, dur = 0.7, ease = EASE.camMain) {
  const root = document.getElementById("root");
  cx = cx ?? +root.dataset.width / 2; cy = cy ?? +root.dataset.height / 2;
  TL.to(sc, { scale, x: cx - px * scale, y: cy - py * scale, duration: dur, ease, transformOrigin: "0 0" }, t);
}
function camSet(sc, t, scale, px, py, cx, cy) {
  const root = document.getElementById("root");
  cx = cx ?? +root.dataset.width / 2; cy = cy ?? +root.dataset.height / 2;
  TL.set(sc, { scale, x: cx - px * scale, y: cy - py * scale, transformOrigin: "0 0" }, t);
}
