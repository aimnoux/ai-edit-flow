---
name: review
description: Review changed timing or layout before showing frames, or investigate a visual problem. Prepare cached evidence and obtain a fresh independent reviewer verdict when needed.
---

# Frame review

1. Run the shared verification command from `CLAUDE.md` for the changed composition or range. It
   prepares measurements and cached beat, seam and phone sheets. Use the emitted artifact paths.
   A machine pass is not visual approval: a pending verdict still needs a reviewer. Reuse an existing
   conclusion only when the command reports it current for the same inputs and scope.
2. When review is needed, start a **fresh subagent** (Agent tool, no history). Give it only
   [references/checklist.md](references/checklist.md), `REVIEW-INPUT.md`, the sheets, this stretch's
   script and the style layer of `style/visual.md`. The builder does not load the full checklist.
   The reviewer judges what a viewer sees; give it no code or builder explanation.
3. Save its complete answer, including the `Fingerprint:` copied from `REVIEW-INPUT.md` and an
   explicit `Verdict: PASS` or `Verdict: FAIL`, as `reviewer.md`, then
   attach it to the current fingerprint:

   ```
   python engine/review.py <id> [--chapter A B] [--video out.mp4] --record-review reviewer.md
   ```

   Use the same target, range and video as verification. This records the independent conclusion;
   generating sheets alone never supplies a verdict.
4. Fix P0, then worthwhile P1: text, timing, details. Verify changed inputs again; changed dependencies
   invalidate the prior verdict and require a current reviewer conclusion. `--force` explicitly invalidates
   the previous verdict even when inputs are unchanged.
5. New signs of slop go into the style layer as the next `S-` code; never renumber codes referenced
   by earlier reviews. Show the result only after the review requirement is satisfied.
