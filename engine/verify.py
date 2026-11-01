#!/usr/bin/env python3
"""Verify built compositions with one short, agent-friendly report.

  python engine/verify.py example-ch1
  python engine/verify.py --project example
  python engine/verify.py example-s1-yt --video engine/renders/example/example-s1-yt.mp4
  python engine/verify.py example-ch1 --chapter 2 6 --force --json

Runs strict composition/HyperFrames checks and prepares cached frame-review inputs. Optional --video
also checks streams, dimensions, frame rate and duration with ffprobe. Human approval is explicit and
separate. No render, paid API, automatic code fix or desktop browser is started.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BUILD, HERE  # noqa: E402


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


class Composition(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.root = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == "root":
            self.root = attrs


def probe_video(video, composition):
    """Validate the final file against the full composition, even when reviewing only a range."""
    attrs = Composition(composition.read_text(encoding="utf-8")).root
    if not attrs:
        raise ValueError("Composition is missing #root metadata")
    expected = {k: float(attrs[f"data-{k}"]) for k in ("duration", "fps", "width", "height")}
    if any(v <= 0 for v in expected.values()):
        raise ValueError("Composition has non-positive duration, fps or dimensions")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(f"ffprobe failed: {r.stderr[-600:]}")
    d = json.loads(r.stdout)
    videos = [s for s in d.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    audio = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise ValueError(f"Expected one video stream; found {len(videos)}")
    if not audio:
        raise ValueError("Final video has no audio stream")
    v = videos[0]
    for dimension in ("width", "height"):
        if int(v[dimension]) != expected[dimension]:
            raise ValueError(f"Video {dimension} is {v[dimension]}, expected {expected[dimension]:g}")
    fps = float(Fraction(v.get("avg_frame_rate") or v.get("r_frame_rate", "0/1")))
    if abs(fps - expected["fps"]) > 0.01:
        raise ValueError(f"Video frame rate is {fps:g}, expected {expected['fps']:g}")
    duration = float(d["format"]["duration"])
    tolerance = max(0.1, 2 / expected["fps"])
    if abs(duration - expected["duration"]) > tolerance:
        raise ValueError(f"Video duration is {duration:.3f}s, expected {expected['duration']:.3f}s")
    return {"path": str(video.resolve()), "duration": duration, "width": v["width"], "height": v["height"],
            "fps": fps, "audio_streams": len(audio)}


def valid_id(value):
    if value in (".", "..") or not re.fullmatch(r"[\w.-]+", value):
        raise argparse.ArgumentTypeError("Use a composition/project name, without paths or wildcards")
    return value


def verify(ids, chapter=None, video=None, force=False, strict=False):
    # Keep the root report small; complete checker stdout and tracebacks live in per-composition logs.
    from review import run_review
    from review_cache import fingerprint
    selection = {"ids": ids, "chapter": chapter, "video": str(video.resolve()) if video else None}
    key = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()[:12]
    label = ids[0] if len(ids) == 1 else "project"
    out = BUILD / "verify" / f"{label}-{key}"
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for cid in ids:
        log = out / f"{cid}.log"
        item = {"id": cid, "status": "failed", "log": str(log.resolve())}
        with log.open("w", encoding="utf-8") as stream, redirect_stdout(stream), redirect_stderr(stream):
            try:
                result = run_review(cid, chapter=chapter, video=video, force=force)
                findings = result.get("findings", [])
                errors = [x for x in findings if "(error)" in x.lower() or "(critical)" in x.lower()]
                warnings = [x for x in findings if "(warning)" in x.lower()]
                item.update(cache=result["status"], fingerprint=result["fingerprint"], review_input=result["input"],
                            sheets=result["sheets"], conclusion=result["conclusion"],
                            warnings=len(warnings), errors=len(errors), findings=findings)
                if not result.get("reusable", True):
                    raise RuntimeError("Untracked dependencies prevent reusable visual approval: "
                                       + "; ".join(result.get("cache_notes", []))[:400])
                if errors:
                    raise RuntimeError("Composition checks reported errors")
                if video:
                    item["video"] = probe_video(video, HERE / f"{cid}.html")
                if fingerprint(cid, chapter, video)["fingerprint"] != result["fingerprint"]:
                    raise RuntimeError("Review inputs changed during verification; rerun verification")
                item["status"] = "failed" if strict and warnings else "passed"
                if strict and warnings:
                    item["error"] = "Warnings require attention (--strict)"
                if result["conclusion"].get("verdict") == "fail":
                    item["status"] = "failed"
                    item["error"] = "Visual review failed; address the recorded findings"
                item["ready_to_show"] = item["status"] == "passed" and result["conclusion"].get("verdict") == "pass"
            except Exception as exc:
                traceback.print_exc()
                item["error"] = str(exc)[:600]
            except SystemExit as exc:
                # A checker may use sys.exit for a dependency/input failure; keep a report for the caller.
                traceback.print_exc()
                item["error"] = str(exc)[:600] or "Checker exited before completing"
        items.append(item)
    report = {"status": "passed" if all(i["status"] == "passed" for i in items) else "failed",
              "ready_to_show": all(i.get("ready_to_show", False) for i in items),
              "scope": "automated checks; visual approval is reported separately", "items": items,
              "report": str((out / "report.json").resolve())}
    atomic_json(out / "report.json", report)
    return report


def compact_report(report):
    """Keep stdout bounded even when a checker produced hundreds of findings or sheets."""
    result = {k: v for k, v in report.items() if k != "items"}
    result["items"] = []
    for item in report["items"]:
        brief = {k: v for k, v in item.items() if k not in {"findings", "sheets"}}
        brief["findings_preview"] = [x[:200] for x in item.get("findings", [])[:3]]
        brief["sheet_count"] = len(item.get("sheets", []))
        result["items"].append(brief)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", type=valid_id)
    ap.add_argument("--project", type=valid_id)
    ap.add_argument("--chapter", nargs=2, type=float, metavar=("START", "END"))
    ap.add_argument("--video", type=Path)
    ap.add_argument("--force", action="store_true", help="Regenerate review inputs and require a new visual verdict")
    ap.add_argument("--strict", action="store_true", help="Exit nonzero on warnings too")
    ap.add_argument("--json", action="store_true", help="Print one JSON report, no checker logs")
    a = ap.parse_args()
    if bool(a.ids) == bool(a.project):
        ap.error("Choose composition ids OR --project")
    ids = a.ids or sorted(p.stem for p in HERE.glob(f"{a.project}-*.html"))
    if not ids:
        ap.error("No compositions found: build the project first")
    if (a.chapter or a.video) and len(ids) != 1:
        ap.error("--chapter and --video require exactly one composition")
    if a.chapter and not (0 <= a.chapter[0] < a.chapter[1] < float("inf")):
        ap.error("Require 0 <= START < END, both finite")
    result = verify(ids, chapter=a.chapter, video=a.video, force=a.force, strict=a.strict)
    if a.json:
        print(json.dumps(compact_report(result), ensure_ascii=False))
    else:
        for item in result["items"]:
            if item["status"] == "passed":
                verdict = item['conclusion'].get('verdict') or item['conclusion']['status']
                print(f"{item['id']}: PASS · review {item['cache']} · visual verdict {verdict} · {item['warnings']} warnings")
            else:
                print(f"{item['id']}: FAIL · {item.get('error', 'see log')}")
            for line in item.get("findings", [])[:3]:
                print("  " + line[:200])
            if item.get("review_input"):
                print("  review: " + item["review_input"])
            print("  log: " + item["log"])
        print("report: " + result["report"])
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
