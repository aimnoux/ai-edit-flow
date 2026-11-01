#!/usr/bin/env python3
"""Offline portable pipeline contracts. No sibling checkout, browser, credentials or network."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mix import env_follow
from review_cache import reviewer_binding
from tts_elevenlabs import parse_blocks, strip_triggers

SCRIPT = """# Fixture
### 1.1 Opening
First [two words]
wrapped.

Second paragraph.
> Editor note.
Third [cue].
| not | speech |
## 2. Chapter
Not spoken.
### 2.1
Last [word].
"""


def report():
    blocks = parse_blocks(SCRIPT)
    paragraphs = [{"block": block, "paragraphs": paragraphs} for block, paragraphs in blocks.items()]
    triggers = []
    for block, paras in blocks.items():
        for i, paragraph in enumerate(paras):
            text, cues = strip_triggers(paragraph)
            triggers.append({"block": block, "para": i, "text": text,
                             "triggers": [{"word": word, "offset": offset} for word, offset in cues]})
    envelope_lengths = [{"input": n, "output": len(env_follow(np.zeros(n)))}
                        for n in (0, 1, 479, 480, 481, 960)]
    fingerprint = "a" * 64
    verdict = reviewer_binding(f"Fingerprint: {fingerprint}\nVerdict: PASS\n", fingerprint) == "pass"
    for text, expected in ((f"Fingerprint: {'b' * 64}\nVerdict: PASS", fingerprint),
                           (f"Fingerprint: {fingerprint}\nVerdict: PASS\nVerdict: FAIL", fingerprint)):
        try:
            reviewer_binding(text, expected)
            verdict = False
        except ValueError:
            pass
    return {"schema": 1, "contracts": {"script_paragraphs": paragraphs, "trigger_offsets": triggers,
                                       "envelope_lengths": envelope_lengths, "review_verdict_binding": verdict}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("Offline contracts: " + ", ".join(result["contracts"]))
    if not result["contracts"]["review_verdict_binding"] or any(
            x["input"] != x["output"] for x in result["contracts"]["envelope_lengths"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
