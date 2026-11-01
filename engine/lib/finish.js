/* Runs last in every composition: registers the root timeline for HyperFrames, filters the sound cues,
   publishes scene bounds for review.py, seeks to #t= for previews and contact sheets. */
(function () {
  const id = document.getElementById("root").dataset.compositionId;
  window.__timelines = window.__timelines || {};
  window.__timelines[id] = TL;
  CUES.sort((a, b) => a.t - b.t);
  // Sound diet: `quiet` cues never play, between the rest at least `gap` seconds; when two collide, a `main`
  // cue (a hit, a stamp: the main action) wins over the other. Rules: style/sound/sounds.json via TIMING.sfx.
  const rules = TM.sfx || {};
  const QUIET = new Set(rules.quiet || []), MAIN = new Set(rules.main || []);
  const GAP = window.SFX_GAP ?? rules.gap ?? 1.2, kept = [];
  CUES.filter((q) => !QUIET.has(q.name)).forEach((q) => {
    const prev = kept[kept.length - 1];
    if (prev && q.t - prev.t < GAP) { if (MAIN.has(q.name) && !MAIN.has(prev.name)) kept[kept.length - 1] = q; return; }
    kept.push(q);
  });
  document.getElementById("cues").textContent = JSON.stringify(kept);
  document.documentElement.dataset.scenes = JSON.stringify(SCENES);
  const m = location.hash.match(/t=([\d.]+)/);
  TL.seek(m ? +m[1] : 0);
})();
