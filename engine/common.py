#!/usr/bin/env python3
"""Shared paths, config and tool lookup for every script in engine/.

  python3 engine/common.py chrome     # prints the Chrome binary the scripts will use
  python3 engine/common.py hf         # prints the pinned HyperFrames version

Nothing here depends on the operating system: Chrome, fonts and caches are found by environment
variables first (CHROME_PATH), then by the usual locations of each OS.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # engine/
ROOT = HERE.parent
STYLE = ROOT / "style"
VIDEOS = ROOT / "videos"
VERTICAL = ROOT / "vertical"
BUILD = HERE / "build"
RENDERS = HERE / "renders"
SCENES = HERE / "scenes"
SR = 48000


def load_env():
    """Variables from .env in the repository root into os.environ (existing values win)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("\"'")
            if k and not k.startswith("#") and v and k not in os.environ:
                os.environ[k] = v


load_env()


def config():
    """style/config.json: the person's language, voice, channel, captions, fps."""
    p = STYLE / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


CFG = config()
FPS = int(CFG.get("fps", 25))
LANG = CFG.get("language", "en")


def hf_version():
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["config"]["hyperframes"]


HF = ["node", str(HERE / "hf.mjs")]   # the HyperFrames CLI, pinned in package.json


def chrome():
    """Path to a Chrome / Chromium binary. CHROME_PATH first, then the usual places."""
    cands = [os.environ.get("CHROME_PATH")]
    if sys.platform == "darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium",
                  str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    elif sys.platform.startswith("win"):
        for base in [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]:
            if base:
                cands += [str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                          str(Path(base) / "Chromium/Application/chrome.exe")]
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        cands.append(shutil.which(name))
    # the browser Puppeteer downloaded for HyperFrames
    cache = Path(os.environ.get("PUPPETEER_CACHE_DIR", Path.home() / ".cache" / "puppeteer"))
    if cache.exists():
        for pat in ["chrome/*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                    "chrome/*/chrome-linux*/chrome", "chrome/*/chrome-win*/chrome.exe"]:
            cands += [str(p) for p in sorted(cache.glob(pat))]
    for c in cands:
        if c and Path(c).exists():
            return c
    sys.exit("Chrome not found: install Google Chrome or Chromium, or set CHROME_PATH in .env")


def chrome_cmd(*extra):
    """Headless Chrome with its own temporary profile (a sandboxed or read-only home must not break it)."""
    import tempfile
    return [chrome(), "--headless=new", "--disable-gpu", "--enable-unsafe-swiftshader", "--allow-file-access-from-files",
            "--no-first-run", "--no-default-browser-check", f"--user-data-dir={tempfile.mkdtemp(prefix='hf-chrome-')}", *extra]


def sounds():
    """style/sound/sounds.json with defaults for a missing or partial file."""
    p = STYLE / "sound" / "sounds.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    strip = lambda x: {k: v for k, v in (x or {}).items() if k != "_"}
    return {"gain": strip(d.get("gain")), "alias": strip(d.get("alias")), "attack": strip(d.get("attack")),
            "main": d.get("main", []), "quiet": d.get("quiet", []), "gap": float(d.get("gap", 1.2)),
            "vary_db": float(d.get("vary_db", 1.5)), "vary_semitones": float(d.get("vary_semitones", 0.3))}


def norm(w):
    """A word key for matching speech to the script: lowercase, letters and digits only."""
    return re.sub(r"[^\w+#/-]", "", w.lower())


def ffmpeg_filter_file(args_before, fc_path, args_after):
    """ffmpeg with a long filter graph read from a file: `-/filter_complex` on ffmpeg 7+,
    `-filter_complex_script` on older builds."""
    import subprocess
    for opt in (["-/filter_complex", str(fc_path)], ["-filter_complex_script", str(fc_path)]):
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args_before, *opt, *args_after], capture_output=True, text=True)
        if r.returncode == 0:
            return
        last = r.stderr
    sys.exit(f"ffmpeg failed:\n{last[-2000:]}")


def duration(path):
    import subprocess
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout)


GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js"


def ensure_vendor():
    """engine/lib/vendor/gsap.min.js: compositions load GSAP locally (a CDN at render time means timeouts).
    Downloaded once by setup.sh or here, kept out of git."""
    dst = HERE / "lib" / "vendor" / "gsap.min.js"
    if dst.exists():
        return dst
    import requests
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(GSAP_URL, timeout=60)
    r.raise_for_status()
    dst.write_bytes(r.content)
    return dst


def sync_style():
    """style/tokens.css and style/fonts/ -> engine/lib/, so compositions reach them by a relative path
    inside the HyperFrames project (engine/)."""
    lib = HERE / "lib"
    src = STYLE / "tokens.css"
    if src.exists():
        shutil.copy(src, lib / "tokens.css")
    for d in ("fonts", "assets"):
        if (STYLE / d).exists():
            shutil.copytree(STYLE / d, lib / d, dirs_exist_ok=True)
    ensure_vendor()


def slot(name):
    """Contents of style/<name>.html for a template slot, empty when the style has none."""
    p = STYLE / f"{name}.html"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def project_dir(kind, project):
    """videos/<slug>/ or vertical/ for the project."""
    return VIDEOS / project if kind == "video" else VERTICAL


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "chrome"
    print(chrome() if what == "chrome" else hf_version())
