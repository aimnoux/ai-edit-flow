/* Vertical video 1080x1920: dense editing, something new in the frame every 0.7-1.5 s, by content and cuts
   on the word, not by shaking. Loaded after kit.js; scenes are scenes/<project>/s<N>.js.
   Also: embedded captions (liveCaptions) and the platform ending (platformEnding). */

const VX = 500;   // center of graphics: the right edge belongs to the platform buttons
const PLATFORM = TM.platform || "yt";

/** Centered text, words rise in sync with the voice (follow). [word] is an accent. */
function vtext(sc, text, y, size, opt = {}) {
  const r = rich(sc, text, "vt", { top: y + "px", fontSize: size + "px", fontWeight: opt.weight || 600, letterSpacing: "-0.035em", lineHeight: 1.05 });
  if (opt.dim) r.box.style.color = "var(--text-2)";
  if (opt.id) follow(r, opt.id, opt.from || text.replace(/[\[\]_]/g, " ").split(/\s+/).filter(Boolean)[0], { nth: opt.nth || 0 });
  else if (opt.t != null) reveal(r.words, opt.t, { sfx: false });
  return r;
}
/** One big word: a short entry with a little scale, no blur, no flash. */
function slam(sc, text, t, opt = {}) {
  const d = el("div", "slam" + (opt.acc === false ? "" : " glow"), sc);
  el("span", opt.acc === false ? "" : "acc-text", d, text);
  Object.assign(d.style, { top: (opt.y ?? 520) + "px", fontSize: (opt.size || 170) + "px" });
  gsap.set(d, { opacity: 0 });
  TL.fromTo(d, { opacity: 0, scale: 1.06 }, { opacity: 1, scale: 1, duration: 0.4, ease: EASE.soft, immediateRender: false }, t - 0.05);
  if (opt.out != null) TL.to(d, { opacity: 0, scale: 0.95, duration: DUR.exit, ease: EASE.exit }, opt.out - DUR.exit);
  if (opt.sfx) sfx(opt.sfx, t, 0.4);
  return d;
}
/** A short shake of a target (use once, on the climax). */
function shake(target, t, amp = 14) {
  [amp, -amp * 0.8, amp * 0.5, -amp * 0.3, 0].forEach((x, k) => TL.to(target, { x, duration: 0.05, ease: "none" }, t + k * 0.05));
}
/** "+1" that floats up and fades. */
function plusUp(sc, text, x, y, t, size = 56) {
  const d = el("div", "plus", sc, text);
  at(d, x, y); d.style.fontSize = size + "px";
  gsap.set(d, { opacity: 0 });
  TL.fromTo(d, { opacity: 0, y: 20, scale: 0.8 }, { opacity: 1, y: -30, scale: 1, duration: 0.25, ease: EASE.settle, immediateRender: false }, t);
  TL.to(d, { opacity: 0, y: -110, duration: 0.5, ease: "power2.in" }, t + 0.4);
  return d;
}
/** A chip with a label, slides in from the side. */
function chip(sc, text, x, y, t, opt = {}) {
  const d = el("div", "vchip", sc, text);
  at(d, x, y);
  if (opt.size) d.style.fontSize = opt.size + "px";
  gsap.set(d, { opacity: 0 });
  TL.fromTo(d, { opacity: 0, x: opt.dx ?? -40 }, { opacity: 1, x: 0, duration: 0.45, ease: EASE.soft, immediateRender: false }, t);
  return d;
}
/** A card: small label, large value. */
function vcard(sc, k, v, x, y, w, t) {
  const c = el("div", "vcard", sc);
  at(c, x, y, w);
  el("div", "k", c, k);
  el("div", "v", c, v);
  gsap.set(c, { opacity: 0 });
  TL.fromTo(c, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: EASE.soft, immediateRender: false }, t);
  return c;
}

/* ---------- Artifacts of a story: interfaces rebuilt in code ---------- */
/** A chat window: title, message bubbles. say(role, text, t0, t1) types a message from t0 to t1 (role: user | bot). */
function chatWindow(sc, x, y, w, h, title = "Chat") {
  const box = el("div", "chat", sc); at(box, x, y, w, h);
  el("div", "chat-head", box, `<i></i><b>${title}</b>`);
  const view = el("div", "chat-view", box);
  const body = el("div", "chat-body", view);
  gsap.set(box, { opacity: 0 });
  const api = {
    box, body,
    show(t) { TL.fromTo(box, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.45, ease: EASE.soft, immediateRender: false }, t); return api; },
    say(role, text, t0, t1, opt = {}) {
      const b = el("div", "msg " + role, body);
      const tx = el("div", "tx", b, "");
      gsap.set(b, { opacity: 0 });
      TL.to(b, { opacity: 1, duration: 0.12 }, t0 - 0.05);
      if (opt.instant) TL.set(tx, { textContent: text }, t0); else typeText(tx, text, t0, t1, null, { stream: role === "bot", sound: opt.sound });
      if (opt.scroll) TL.to(body, { y: opt.scroll, duration: 0.35, ease: EASE.move }, t0 - 0.1);
      return b;
    },
  };
  return api;
}
/** A document sheet (a letter, a ruling): centered lines, room for a stamp below. */
function docSheet(sc, x, y, w, lines, t) {
  const d = el("div", "doc", sc); at(d, x, y, w);
  lines.forEach((l, i) => el("div", i === 0 ? "dl dh" : "dl", d, l));
  gsap.set(d, { opacity: 0 });
  TL.fromTo(d, { opacity: 0, y: 80, rotation: -2 }, { opacity: 1, y: 0, rotation: 0, duration: 0.6, ease: EASE.soft, immediateRender: false }, t);
  return d;
}
/** A stamp slammed on top of something: the climax, the one hit with a sound in the video. */
function stamp(sc, text, x, y, t, opt = {}) {
  const s = el("div", "stamp", sc, text); at(s, x, y);
  if (opt.size) s.style.fontSize = opt.size + "px";
  gsap.set(s, { opacity: 0 });
  TL.fromTo(s, { opacity: 0, scale: 2.4, rotation: -14 }, { opacity: 1, scale: 1, rotation: -8, duration: 0.22, ease: "power4.in", immediateRender: false }, t - 0.2);
  shake(sc, t, 10); sfx(opt.sfx || "stamp", t, 0.7);
  return s;
}
/** A meme frame: one phrase on top for the whole video (up to ~30 characters), captions off, the stage not masked. */
function memeFrame(text, size) {
  window.NO_CAPS = true;
  document.documentElement.classList.add("nocaps");
  const d = el("div", "topcap", HUD, text);
  if (size) d.style.fontSize = size + "px";
  return d;
}

/* ---------- Captions ---------- */
// words a caption line must not end on; the style's list (config.json captions.weak) replaces this English default
const WEAK_DEFAULT = ["a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "by", "for", "with", "from", "as", "if", "than", "that",
  "is", "are", "was", "were", "be", "it", "its", "my", "your", "our", "their", "his", "her", "this", "these", "those", "not", "no", "so", "very"];
/** Live captions: phrases of 3-4 words at the bottom of the frame, the spoken word lights up. Vertical only.
    opt.skip = [[a, b], ...] stretches without captions. */
function liveCaptions(opt = {}) {
  if (window.NO_CAPS) return;
  const root = document.getElementById("root");
  if (+root.dataset.width >= +root.dataset.height) throw new Error("embedded captions are for vertical video only");
  const cfg = TM.captions || {};
  const max = opt.max || cfg.max_words || 4;
  const weak = new Set((cfg.weak && cfg.weak.length ? cfg.weak : WEAK_DEFAULT).map((w) => w.toLowerCase()));
  const skip = opt.skip || [];
  const layer = el("div", "caps", HUD);
  const chunks = [];
  Object.values(TM.blocks).flat().sort((a, b) => a.s - b.s).forEach((p) => {
    let cur = [];
    const ws = p.words.filter((w) => !/^[—–-]+$/.test(w.w));   // a lone dash is not a caption
    ws.forEach((w, i) => {
      cur.push(w);
      if (/[.,!?:;»"]$/.test(w.w)) { chunks.push(cur); cur = []; }
      else if (cur.length >= max) {
        // a line doesn't end on a weak word and doesn't split a capitalized two-word name: the word moves to the next line
        const cap = (x) => x && /^\p{Lu}/u.test(x.w);
        const tail = cur.length > 1 && (weak.has(norm(w.w)) || (cap(w) && cap(ws[i + 1]))) ? cur.pop() : null;
        chunks.push(cur); cur = tail ? [tail] : [];
      }
    });
    if (cur.length) chunks.push(cur);
  });
  chunks.forEach((ws, k) => {
    const s = ws[0].s - 0.06;
    const nextS = k + 1 < chunks.length ? chunks[k + 1][0].s - 0.06 : Infinity;
    const e = Math.min(ws[ws.length - 1].e + 0.35, nextS);
    if (skip.some(([a, b]) => s < b && e > a)) return;
    const c = el("div", "cap", layer);
    c.style.display = "none";
    ws.forEach((w) => {
      const sp = el("span", "", c, w.w.replace(/[.,:;]+$/, "").replace(/^[«"]|[»"]$/g, ""));
      TL.to(sp, { opacity: 1, duration: 0.08 }, w.s - 0.02);
    });
    TL.set(c, { display: "inline-block" }, s);
    TL.fromTo(c, { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.18, ease: "power2.out", immediateRender: false }, s);
    TL.set(c, { display: "none" }, e);
  });
}

/* ---------- Platform ending ---------- */
const PLATFORM_UI = {
  yt: { btn: "Subscribe", done: "Subscribed", like: "Like", btnBg: "#f1f1f1", btnFg: "#0f0f0f" },
  ig: { btn: "Follow", done: "Following", like: "Like", btnBg: "#0095f6", btnFg: "#fff" },
  tt: { btn: "Follow", done: "Following", like: "Like", btnBg: "#fe2c55", btnFg: "#fff" },
};
const ICON = {
  like: (s) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v11H3V10h4zm0 0 4-7c1.5 0 2.5 1 2.5 2.5V9H20a2 2 0 0 1 2 2.3l-1.3 7.4A2 2 0 0 1 18.7 21H7"/></svg>`,
  heart: (s) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 21s-7.5-4.6-9.5-9.3C1.2 8.4 3.3 5 6.8 5c2 0 3.4 1.1 5.2 3 1.8-1.9 3.2-3 5.2-3 3.5 0 5.6 3.4 4.3 6.7C19.5 16.4 12 21 12 21z"/></svg>`,
};
/** The ending of a vertical video: on the ending block (`end`) the last frame dims and blurs and one button of the
    platform appears in the middle: Like if the ending text asks for a like, Follow/Subscribe if it asks to subscribe;
    it is pressed on the first trigger word of the ending. Nothing for an ending that asks neither (a plain closing
    line). A scene can draw its own call with window.END_CTA = ({ tIn, tTap, sub, like, ui }) => ... . */
function platformEnding() {
  if (!TM.blocks.end) return;
  const be = B("end");
  const text = paras("end").map((p) => p.text).join(" ").toLowerCase();
  const sub = /subscri|follow/.test(text), like = /\blike\b|heart|thumb/.test(text);
  if (!(sub || like)) return;
  const ui = PLATFORM_UI[PLATFORM] || PLATFORM_UI.yt;
  const ch = TM.channel || {};
  const trig = paras("end").flatMap((p) => p.triggers)[0];
  const tIn = be.s + 0.05, tTap = Math.min(trig ? trig.t : be.s + 1.2, D - 1.6);   // the pressed state holds at least 1.6 s
  if (window.END_CTA) { window.END_CTA({ tIn, tTap, sub, like, ui }); sfx("tap", tTap + 0.04, 0.6); return; }
  const dim = el("div", "end-dim");
  dim.setAttribute("data-layout-allow-occlusion", "");   // dimming the last frame is the intent
  HUD.insertBefore(dim, HUD.querySelector(".caps"));   // captions stay readable above the dim
  gsap.set(dim, { opacity: 0 });
  TL.to(dim, { opacity: 1, duration: 0.4, ease: "power2.out" }, tIn);
  const name = ch.name || ch.handle || "";
  const avatar = ch.avatar ? `style="background-image:url(lib/${ch.avatar})"` : "";
  const btn = el("div", "end-cta " + (sub ? "sub" : "like"), HUD,
    sub ? `<i class="ec-av" ${avatar}>${ch.avatar ? "" : (name[0] || "").toUpperCase()}</i><b class="ec-name">${name}</b>
        <span class="ec-btn" style="background:${ui.btnBg};color:${ui.btnFg}"><span class="a">${ui.btn}</span><span class="b">${ui.done}</span></span>`
        : `<i class="ec-ring">${(PLATFORM === "yt" ? ICON.like : ICON.heart)(150)}</i><b class="ec-lbl">${ui.like}</b>`);
  btn.setAttribute("data-layout-allow-occlusion", "");   // the button sits over the dimmed last frame on purpose
  // the last frame of the story stays under the button on purpose: its text may be covered
  STAGE.querySelectorAll(".scene").forEach((sc) => { if (sc._e >= be.s) sc.querySelectorAll("*").forEach((n) => n.setAttribute("data-layout-allow-occlusion", "")); });
  const kids = [...btn.children];
  gsap.set(kids, { opacity: 0, y: 40, scale: 0.85 });
  TL.to(kids, { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "back.out(1.6)", stagger: 0.08 }, tIn + 0.1);
  const key = btn.querySelector(sub ? ".ec-btn" : ".ec-ring");
  const tp = el("div", "tap", HUD); at(tp, 540, sub ? 1010 : 810); gsap.set(tp, { opacity: 0, scale: 0.4, zIndex: 5 });
  TL.to(tp, { opacity: 1, scale: 1, duration: 0.16 }, tTap); TL.to(tp, { opacity: 0, duration: 0.3 }, tTap + 0.22);
  sfx("tap", tTap + 0.04, 0.6);
  TL.to(key, { scale: 0.9, duration: 0.07, ease: "power2.in" }, tTap);
  TL.to(key, { scale: 1, duration: 0.35, ease: "back.out(3)" }, tTap + 0.07);
  TL.set(btn, { attr: { class: btn.className + " on" } }, tTap + 0.07);
}
