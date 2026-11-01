#!/usr/bin/env python3
"""Shared paths, config and tool lookup for every script in engine/.

  python3 engine/common.py chrome     # prints the Chrome binary the scripts will use
  python3 engine/common.py hf         # prints the pinned HyperFrames version
  python3 engine/common.py vendor     # fetches the pinned GSAP library once (setup)

Browser tools use only a dedicated Chrome Headless Shell, never the person's desktop browser.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
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
    """Resolve an isolated headless shell; no fallback to a desktop Chrome installation."""
    names = {"chrome-headless-shell", "chrome-headless-shell.exe"}

    def usable(path):
        p = Path(path).expanduser().resolve()
        return p if p.name.lower() in names and p.is_file() and os.access(p, os.X_OK) else None

    for key in ("CHROME_PATH", "HYPERFRAMES_BROWSER_PATH", "PRODUCER_HEADLESS_SHELL_PATH"):
        if os.environ.get(key):
            p = usable(os.environ[key])
            if not p:
                raise RuntimeError(f"{key} must point to a dedicated chrome-headless-shell binary, not desktop Chrome")
            return str(p)
    caches = [Path.home() / ".cache" / "hyperframes" / "chrome",
              Path(os.environ.get("PUPPETEER_CACHE_DIR", Path.home() / ".cache" / "puppeteer"))]
    for cache in caches:
        for name in sorted(names):
            for candidate in sorted(cache.glob(f"chrome-headless-shell/**/{name}"), reverse=True):
                p = usable(candidate)
                if p:
                    return str(p)
    raise RuntimeError("Dedicated browser not found. Run node engine/hf.mjs browser ensure (or bash setup.sh)")


def run_chrome(*extra, timeout=180):
    """Run only our browser in a temporary profile and reap its process group, including on timeout."""
    browser = chrome()  # validate before allocating a profile or starting any process
    with tempfile.TemporaryDirectory(prefix="aef-headless-") as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--enable-unsafe-swiftshader",
               "--allow-file-access-from-files", "--no-first-run", "--no-default-browser-check",
               "--disable-breakpad", "--disable-crash-reporter", f"--user-data-dir={profile}", *extra]
        opts = {"start_new_session": True} if os.name != "nt" else {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **opts)
        guard = None
        try:
            if os.name != "nt":
                guard = subprocess.Popen([sys.executable, str(HERE / "process_guard.py"), str(p.pid)],
                                         stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         start_new_session=True)
            stdout, stderr = p.communicate(timeout=timeout)
            if p.returncode:
                raise RuntimeError(f"Dedicated browser failed ({p.returncode}): {stderr[-1500:]}")
            return subprocess.CompletedProcess(cmd, p.returncode, stdout, stderr)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Dedicated browser timed out after {timeout}s") from exc
        finally:
            if os.name == "nt":
                if p.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            p.communicate()
            if guard:
                guard.stdin.close()
                guard.wait(timeout=10)


def run_hf(*args, timeout=None):
    """Allow the CLI wrapper to stop its owned browser before enforcing a Python timeout."""
    opts = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    p = subprocess.Popen([*HF, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **opts)
    guard = None
    try:
        if os.name != "nt":
            # Closing the runner's pipe kills its wrapper; that wrapper's guardian then reaps Chrome.
            guard = subprocess.Popen([sys.executable, str(HERE / "process_guard.py"), str(p.pid)],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        stdout, stderr = p.communicate(timeout=timeout)
        return subprocess.CompletedProcess(p.args, p.returncode, stdout, stderr)
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
        if os.name != "nt":
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if guard:
            guard.stdin.close()
            guard.wait(timeout=10)


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
    for opt in (["-/filter_complex", str(fc_path)], ["-filter_complex_script", str(fc_path)]):
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args_before, *opt, *args_after], capture_output=True, text=True)
        if r.returncode == 0:
            return
        last = r.stderr
        # Retry only for an unsupported option, never hide a real input/filter error.
        if not re.search(r"(?:Unrecognized option|Option not found|Error splitting the argument list)", last):
            break
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
    try:
        print(chrome() if what == "chrome" else ensure_vendor() if what == "vendor" else hf_version())
    except RuntimeError as exc:
        sys.exit(str(exc))
