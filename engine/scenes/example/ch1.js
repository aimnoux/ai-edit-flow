/* Example, chapter 1: a title, then the words of the script as they are spoken. No style: tokens only. */
(function () {
  // chapter title for the head of the chapter: from 0 to a bit before the first word
  const first = B("1.1").s, tEnd = Math.max(first - 0.1, 0.8);
  chapterTitle(0, tEnd, CHAPTER.title, "timing by the voice");
  progress(first, D);

  // 1.1: the word "hello" large, three variants under it on the trigger "three"
  const s1 = scene(tEnd, B("1.2").s - 0.1);
  const hello = rich(s1, "hello", "hero", { position: "absolute", left: "128px", top: "380px" });
  reveal(hello.words, TR("1.1", "hello"));
  glow(hello.words[0], TR("1.1", "hello"));
  list(s1, ["formal", "short", "everyday"], [TR("1.1", "three"), TR("1.1", "three") + 0.2, TR("1.1", "three") + 0.4], { x: 1040, y: 420 });

  // 1.2: one line that follows the voice word by word
  const s2 = scene(B("1.2").s - 0.1, D);
  const line = rich(s2, "who you are [talking] to", "h1", { position: "absolute", left: "128px", top: "440px" });
  follow(line, "1.2", "who");
  accents(line, [TR("1.2", "talking")]);
})();
