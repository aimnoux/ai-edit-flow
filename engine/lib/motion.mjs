/* Pure timing helpers shared by 3D and shader scenes: no DOM, no clocks, no random. Same input, same frame. */

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const ease = {
  inOut: (x) => (x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2),
  sine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
  expo: (x) => (x >= 1 ? 1 : 1 - 2 ** (-10 * x)),
  out3: (x) => 1 - (1 - x) ** 3,
};

/** Low-discrepancy sequence: i-th sample in base b, 0..1. Subframes use it for jitter, lens and light positions. */
export function halton(i, b) {
  let f = 1, r = 0;
  while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); }
  return r;
}

/** All words of one speaker from the composition timing: speakerWords(TM.blocks, "boss"). */
export function speakerWords(blocks, who) {
  return Object.values(blocks).flat().filter((p) => p.who === who).flatMap((p) => p.words).sort((a, b) => a.s - b.s);
}

const VOWELS = /[aeiouyаеёиоуыэюя]/gi;
/** Mouth opening 0..1 over time from word timestamps: one opening per syllable, closed between words.
    mouth(speakerWords(TM.blocks, "boss")) returns a function of seconds, safe to call on subframe times. */
export function mouth(words, { lead = 0.03, tail = 0.06 } = {}) {
  const spans = words.map((w) => ({ s: w.s - lead, e: w.e + tail, n: Math.max(1, (w.w.match(VOWELS) || []).length) }));
  return (t) => {
    let open = 0;
    for (const { s, e, n } of spans) {
      if (t <= s || t >= e) continue;
      const u = (t - s) / (e - s);
      open = Math.max(open, Math.sin(Math.PI * ((u * n) % 1)) ** 0.7 * (0.6 + 0.4 * Math.sin(Math.PI * u)));
    }
    return open;
  };
}

/** Who is talking, as a smooth 0..1 over whole phrases: for a head turn, a light, a camera. Pauses shorter than `gap`
    keep it up; the edges take `fade` seconds. */
export function talking(words, { gap = 0.5, fade = 0.3 } = {}) {
  const runs = [];
  for (const { s, e } of words) {
    const last = runs[runs.length - 1];
    if (last && s - last.e < gap) last.e = e; else runs.push({ s, e });
  }
  return (t) => Math.max(0, ...runs.map(({ s, e }) => ease.sine(clamp((t - s + fade) / fade)) * ease.sine(clamp((e + fade - t) / fade))));
}

/** Times of the music marks with this name from beats.json (engine/beats.py): markTimes(beats, "hit"). */
export const markTimes = (beats, name) => beats.marks.filter((m) => m.name === name).map((m) => m.t).sort((a, b) => a - b);

/** Seconds since the last mark, Infinity before the first one. */
export function since(times, t) {
  let last = -Infinity;
  for (const x of times) { if (x > t) break; last = x; }
  return t - last;
}

/** How many marks already passed: the index of the current section of a track. */
export function count(times, t) {
  let n = 0;
  for (const x of times) { if (x > t) break; n++; }
  return n;
}

/** A hit: 1 on the mark, decaying over `decay` seconds, 0 before the first mark. */
export const pulse = (times, t, decay = 0.35) => Math.exp(-since(times, t) / decay);
