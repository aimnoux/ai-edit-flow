/* Example sketch, the flat layer: everything readable stays HTML above the 3D canvas. The name of whoever speaks rides
   on the head: s1.mjs moves it with pin() and owns its opacity. Captions and the ending come from the template. */
(function () {
  const sc = scene(0, D, { enter: "cut", exit: "cut" });
  const label = (name) => at(el("div", "vchip", sc, name), 0, 0);
  window.SKETCH_LABELS = { boss: label("boss"), dev: label("dev") };
  slam(sc, "AGENT", TR("1.3", "agent"), { y: 235, size: 170, out: B("end").s });
})();
