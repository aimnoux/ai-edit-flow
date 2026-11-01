/* Example vertical 1: a big word on the hook, three chips, a stamp on the twist, the platform ending comes from
   lib/vertical.js on block 1.8 / 1.9. No style: tokens only. */
(function () {
  const s1 = cut(0, B("1.2").s - 0.05);
  slam(s1, "three", TR("1.1", "three"), { y: 520, size: 220 });
  vtext(s1, "words for hello", 820, 90, { t: TR("1.1", "three") + 0.3 });

  const s2 = cut(B("1.2").s - 0.05, B("1.3").s - 0.05);
  ["stranger", "friend", "every day"].forEach((n, i) => chip(s2, n, 120, 520 + i * 150, W("1.2", ["one for a", "one for a", "and one"][i], i < 2 ? i : 0)));

  const s3 = cut(B("1.3").s - 0.05, D);
  const d = docSheet(s3, 120, 420, 840, ["CONVERSATION", "pick the wrong word", "and it is over"], B("1.3").s);
  stamp(s3, "OVER", 420, 700, TR("1.3", "started"));
})();
