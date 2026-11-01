/* Example, chapter 2: three cards that land on their words, a typed answer, a counter. */
(function () {
  const first = B("2.1").s, tEnd = Math.max(first - 0.1, 0.8);
  chapterTitle(0, tEnd, CHAPTER.title, "cards on trigger words");
  progress(first, D);

  const s1 = scene(tEnd, B("2.2").s - 0.1);
  const names = ["stranger", "friend", "every day"];
  names.forEach((n, i) => {
    const c = el("div", "card", s1, `<div class="mono">0${i + 1}</div><div class="h2">${n}</div>`);
    at(c, 128 + i * 580, 400, 520);
    stampIn(c, TR("2.1", ["stranger", "friend", "every"][i]));
  });

  const s2 = scene(B("2.2").s - 0.1, D);
  const box = el("div", "h2", s2); at(box, 128, 420, 1600);
  typeText(box, "the word is the same, the distance is not", W("2.2", "the word"), WE("2.2", "not"), null, { stream: true });
  const n = el("div", "hero", s2); at(n, 128, 600);
  countUp(n, 1, 3, TR("2.2", "trick"), 0.8);
})();
