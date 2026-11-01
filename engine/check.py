#!/usr/bin/env python3
"""Quick check of compositions without rendering: script errors in scenes and the number of sound cues.

  python3 engine/check.py <composition id> [...]        # e.g. example-ch1 example-ch2, or short-1-yt
  python3 engine/check.py --project example             # every example-*.html in engine/
  python3 engine/check.py --project example --hf        # plus the HyperFrames check (lint, layout, motion, craft)

Runs each composition in headless Chrome, reads the error collector of the template (data-err) and
the cue list finish.js writes. --hf adds the HyperFrames `check --json` findings (lint, layout, motion, contrast, craft) through a temporary project.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, chrome_cmd  # noqa: E402


def dom(cid, budget=4000):
    """DOM of a composition after its scripts ran (virtual time: the timeline is paused, nothing renders)."""
    return subprocess.run(chrome_cmd(
                           f"--virtual-time-budget={budget}", "--dump-dom", (HERE / f"{cid}.html").resolve().as_uri()),
                          capture_output=True, text=True, timeout=180).stdout


def check(cid):
    html = dom(cid)
    err = re.search(r'data-err="([^"]*)"', html)
    m = re.search(r'id="cues">(.*?)</script>', html, re.S)
    n = len(re.findall(r'"name":', m.group(1))) if m else 0
    sc = re.search(r'data-scenes="([^"]*)"', html)
    scenes = sc.group(1).count("[") - 1 if sc else 0
    return err.group(1) if err else None, n, max(scenes, 0)


def hf_findings(cid):
    """HyperFrames check on a temporary project around the composition (review.py builds it)."""
    import shutil
    from review import check as hf_check, project
    out = HERE / "build" / "check" / cid
    out.mkdir(parents=True, exist_ok=True)
    proj = project(cid, out, None)
    try:
        return hf_check(proj)
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if a != "--hf"]
    hf = "--hf" in sys.argv
    if not args:
        sys.exit(__doc__)
    if args[0] == "--project":
        ids = sorted(p.stem for p in HERE.glob(f"{args[1]}-*.html"))
    else:
        ids = args
    bad = 0
    for cid in ids:
        if not (HERE / f"{cid}.html").exists():
            print(f"{cid}: no such composition in engine/")
            bad += 1
            continue
        err, n, scenes = check(cid)
        bad += bool(err)
        print(f"{cid}: {'ERROR ' + err if err else 'ok'} · scenes {scenes} · sound cues {n}")
        if hf and not err:
            for line in hf_findings(cid) or ["- hyperframes check: no findings"]:
                print("  " + line)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
