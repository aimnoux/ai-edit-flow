#!/usr/bin/env python3
"""Render one composition through a stable isolated index project, never a global engine/index.html.

python engine/render.py example-ch1 engine/renders/example/ch1.mp4 [HyperFrames render flags]
"""
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, HERE, run_hf
from review import project


def render(cid, output, *flags, timeout=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", cid) or not (HERE / f"{cid}.html").is_file():
        raise ValueError(f"Missing or invalid composition: {cid}")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stable project path preserves HyperFrames' segment-resume identity across invocations.
    staged = project(cid, BUILD / "render-projects" / cid, None)
    return run_hf("render", str(staged), "--output", str(output), *flags, timeout=timeout)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    result = render(sys.argv[1], sys.argv[2], *sys.argv[3:])
    print(result.stdout or "", end="")
    print(result.stderr or "", end="", file=sys.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
